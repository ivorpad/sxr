"""Path lookup skips evidence work while retaining fresh and complete source selection."""

import json

import pytest

from sxr.cli import app
from test_find import find, runner
from test_providers import _write_claude, _write_codex


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    return _write_claude(tmp_path, monkeypatch), _write_codex(tmp_path, monkeypatch)


def paths(query, *arguments):
    result = runner.invoke(app, ["find", query, "--paths", "--path", "/w", *arguments])
    assert result.exit_code in (0, 1), result.output
    return result.stdout.splitlines()


def test_path_only_clues_and_phrases_across_providers(corpus):
    claude, codex = corpus
    assert paths("thing test") == [str(claude)]
    assert paths("hello boom") == [str(codex)]
    assert paths("thing hello", "--any") == sorted(map(str, corpus))
    assert paths("thing hello") == []
    assert paths('"do the thing"') == [str(claude)]
    assert paths('"do thing"') == []


def test_paths_do_not_load_or_score_evidence(corpus, monkeypatch):
    import sxr.find_query as query

    find("thing")
    monkeypatch.setattr(query.zlib, "decompress", lambda *a: pytest.fail("loaded excerpt"))
    assert paths("thing") == [str(corpus[0])]


def test_path_limits_json_and_both_entry_points(corpus, capsys):
    from sxr.find_cli import main

    expected = sorted(map(str, corpus))
    assert paths("thing hello", "--any") == expected
    assert paths("thing hello", "--any", "-n", "1") == expected[:1]
    result = runner.invoke(
        app, ["find", "thing hello", "--any", "--paths", "--path", "/w", "--json"]
    )
    data = json.loads(result.stdout)
    assert data["paths"] == expected and data["total"] == 2 and data["complete"]
    assert "results" not in data
    assert main(["thing hello", "--any", "--paths", "--path", "/w", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == data


def test_paths_include_every_duplicate_source(corpus, tmp_path):
    _, codex = corpus
    archive = tmp_path / ".codex" / "archived_sessions" / "rollout-copy.jsonl"
    archive.parent.mkdir()
    archive.write_bytes(codex.read_bytes())
    assert paths("hello") == sorted([str(codex), str(archive)])


def test_paths_remain_current_after_edit_and_deletion(corpus):
    claude, _ = corpus
    assert paths("thing") == [str(claude)]
    claude.write_text(claude.read_text().replace("thing", "other"))
    assert paths("thing") == []
    assert paths("other") == [str(claude)]
    claude.unlink()
    assert paths("other") == []


def test_paths_report_missing_roots_and_concurrent_changes(corpus, tmp_path, monkeypatch):
    import sxr.find_service as service

    result = runner.invoke(
        app,
        [
            "find",
            "thing",
            "--paths",
            "--json",
            "--claude-root",
            str(tmp_path / "missing"),
        ],
    )
    assert result.exit_code == 2 and not json.loads(result.stdout)["complete"]
    original = service.search_paths

    def changing(*args):
        result = original(*args)
        corpus[0].unlink()
        return result

    monkeypatch.setattr(service, "search_paths", changing)
    result = runner.invoke(app, ["find", "thing", "--paths", "--path", "/w", "--json"])
    data = json.loads(result.stdout)
    assert result.exit_code == 2 and not data["complete"] and not data["paths"]
