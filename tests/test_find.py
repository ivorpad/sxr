"""Ranked retrieval starts with clues and returns verifiable source passages."""

import json
import shlex

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.index_store import clear, connect
from test_providers import CLAUDE_RECORDS, CODEX_RECORDS, _write_claude, _write_codex

runner = CliRunner()


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    claude = _write_claude(tmp_path, monkeypatch)
    codex = _write_codex(tmp_path, monkeypatch)
    return claude, codex


def find(query, *args):
    result = runner.invoke(app, ["find", query, "--path", "/w", "--json", *args])
    assert result.exit_code in (0, 1), result.output
    return json.loads(result.stdout)


def test_both_providers_and_clues_across_events(corpus):
    claude, codex = corpus
    result = find("thing test")
    assert result["complete"] and result["total"] == 1
    hit = result["results"][0]
    assert hit["path"] == str(claude)
    assert {e["seq"] for e in hit["evidence"]} == {1, 2}
    assert next(e for e in hit["evidence"] if e["seq"] == 2)["outcome"] == "err"
    zoom = runner.invoke(app, shlex.split(hit["follow_up"])[1:])
    assert zoom.exit_code == 0 and str(claude) in zoom.output
    result = find("hello boom")
    assert result["results"][0]["path"] == str(codex)
    assert result["total"] == 1


def test_exact_phrases_and_query_syntax_are_data(corpus):
    assert find('"do the thing"')["total"] == 1
    assert find('"do thing"')["total"] == 0
    assert find('hello "OR"')["total"] == 0
    assert find("thing hello", "--any")["total"] == 2
    assert find("thing hello")["total"] == 0
    assert find("unfindable-marker")["total"] == 0


def test_warm_inventory_and_retrieval_do_not_parse_transcripts(corpus, monkeypatch):
    import sxr.catalog as catalog
    from sxr.providers import claude_code, codex

    first = find("thing")
    monkeypatch.setattr(catalog, "_reference", lambda *a: pytest.fail("metadata reread"))
    for provider in (claude_code, codex):
        monkeypatch.setattr(provider, "parse", lambda *a: pytest.fail("transcript parsed"))
    assert find("thing") == first


def test_new_files_appends_rewrites_and_deleted_files(corpus):
    claude, codex = corpus
    assert find("newword")["total"] == 0
    record = dict(CLAUDE_RECORDS[0], message={"content": "newword"})
    with claude.open("a") as stream:
        stream.write("\n" + json.dumps(record))
    assert find("newword")["results"][0]["path"] == str(claude)
    claude.write_text(json.dumps(CLAUDE_RECORDS[0]))
    assert find("newword")["total"] == 0
    copy = codex.with_name("rollout-new-session.jsonl")
    records = [
        dict(CODEX_RECORDS[0], payload={"id": "new-session", "cwd": "/w"}),
        {"type": "event_msg", "payload": {"type": "user_message", "message": "newword"}},
    ]
    copy.write_text("\n".join(json.dumps(r) for r in records))
    assert find("newword")["results"][0]["id"] == "new-session"
    copy.unlink()
    assert find("newword")["total"] == 0


def test_child_archive_profile_and_duplicate_copy_coverage(corpus, tmp_path):
    claude, codex = corpus
    child = claude.parent / claude.stem / "fork" / "subagents" / "agent-kid.jsonl"
    child.parent.mkdir(parents=True)
    child.write_text(json.dumps(dict(CLAUDE_RECORDS[0], message={"content": "childword"})))
    assert find("childword")["results"][0]["id"] == f"{claude.stem}/agent-kid"
    root = tmp_path / ".codex" / "archived_sessions"
    root.mkdir()
    archive = root / "rollout-archive.jsonl"
    archive.write_bytes(codex.read_bytes())
    assert len(find("hello")["results"][0]["sources"]) == 2
    profile = tmp_path / "profile"
    alternate = profile / "projects" / "project" / "alternate.jsonl"
    alternate.parent.mkdir(parents=True)
    alternate.write_text(json.dumps(dict(CLAUDE_RECORDS[0], message={"content": "profileword"})))
    assert find("profileword")["total"] == 0
    assert find("profileword", "--claude-root", str(profile))["total"] == 1


def test_project_and_provider_filters(corpus):
    assert find("hello", "--claude")["total"] == 0
    assert find("thing", "--codex")["total"] == 0
    result = runner.invoke(app, ["find", "hello", "--path", "/other", "--json"])
    assert result.exit_code == 1 and json.loads(result.stdout)["total"] == 0
    result = runner.invoke(app, ["find", "hello", "--path", "/other", "--all-projects", "--json"])
    assert result.exit_code == 0
    assert find("hello", "--before", "2020-01-01")["total"] == 0


def test_cache_clear_removes_catalogue_and_passages(corpus):
    find("thing")
    with connect() as index:
        assert index.db.execute("SELECT count(*) FROM catalog").fetchone()[0] == 2
        assert index.db.execute("SELECT count(*) FROM passages").fetchone()[0] > 0
    clear()
    assert find("thing")["total"] == 1


def test_file_selection_applies_to_ranked_search(corpus):
    claude, codex = corpus
    result = runner.invoke(app, ["find", "thing", "--file", str(claude), "--json"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.stdout)
    assert body["coverage"][0]["searched"] == 1
    assert body["results"][0]["path"] == str(claude)
    wrong = runner.invoke(app, ["find", "hello", "--file", str(codex), "--claude"])
    assert wrong.exit_code == 2


def test_partial_coverage_is_not_reported_as_complete(corpus, tmp_path):
    result = runner.invoke(
        app,
        ["find", "thing", "--all-projects", "--json", "--claude-root", str(tmp_path / "missing")],
    )
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert not data["complete"] and data["errors"]


def test_only_displayed_results_load_passage_bodies(corpus, monkeypatch):
    import sxr.find_query as query

    calls = []
    original = query.zlib.decompress

    def decompress(data):
        calls.append(1)
        return original(data)

    monkeypatch.setattr(query.zlib, "decompress", decompress)
    result = find("thing hello", "--any", "-n", "1")
    assert result["total"] == 2 and len(result["results"]) == 1
    assert len(calls) == 1


def test_fast_cli_matches_typer_results(corpus, capsys):
    from sxr.find_cli import main

    direct = find("hello")
    code = main(["hello", "--path", "/w", "--json"])
    captured = capsys.readouterr()
    assert code == 0 and json.loads(captured.out) == direct


def test_cache_rebuild_preserves_late_tool_outcomes(corpus):
    claude, _ = corpus
    rows = claude.read_text().splitlines()
    claude.write_text("\n".join(rows[:2]))
    assert find("test")["results"][0]["evidence"][0]["outcome"] == ""
    with claude.open("a") as stream:
        stream.write("\n" + rows[2])
    assert find("test")["results"][0]["evidence"][0]["outcome"] == "err"


def test_actual_source_coordinates_and_multiblock_text(corpus):
    from sxr.providers import claude_code

    claude, _ = corpus
    record = dict(CLAUDE_RECORDS[1])
    record["message"] = {
        "content": [
            {"type": "text", "text": "blockword"},
            {"type": "text", "text": "differentword"},
        ]
    }
    with claude.open("a") as stream:
        stream.write("\n" + json.dumps(record))
    hit = find("differentword")["results"][0]["evidence"][0]
    events = claude_code.parse(claude)
    assert any(event.seq == hit["seq"] and hit["text"] in event.text for event in events)
