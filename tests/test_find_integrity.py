"""Ranked retrieval must retain coverage and source meaning through cache changes."""

import json
import os

import pytest

from sxr.cli import app
from sxr.find_query import clues
from sxr.index_store import connect
from test_find import find, runner
from test_providers import CLAUDE_RECORDS, _write_claude, _write_codex


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    return _write_claude(tmp_path, monkeypatch), _write_codex(tmp_path, monkeypatch)


def test_long_tokens_and_phrases_are_not_split(corpus):
    claude, _ = corpus
    token = "x" * 2397 + "suffixword"
    phrase = "alpha" + " " * 5000 + "omega"
    record = dict(CLAUDE_RECORDS[0], message={"content": token + " " + phrase})
    claude.write_text(json.dumps(record))
    assert find("suffixword")["total"] == 0
    assert find(token)["total"] == 1
    assert find('"alpha omega"')["total"] == 1


def test_clues_never_silently_drop_requested_words(corpus):
    assert clues('"the" "or" and') == ["the", "or", "and"]
    assert find("the")["total"] == 1
    assert find("thing and")["total"] == 0


def test_child_scope_tracks_parent_metadata_rewrites(corpus):
    claude, _ = corpus
    child = claude.parent / claude.stem / "subagents" / "agent-kid.jsonl"
    child.parent.mkdir(parents=True)
    child.write_text(json.dumps(dict(CLAUDE_RECORDS[0], message={"content": "childword"})))
    assert find("childword")["total"] == 1
    claude.write_text(json.dumps(dict(CLAUDE_RECORDS[0], cwd="/changed")))
    assert find("childword")["total"] == 0
    result = runner.invoke(app, ["find", "childword", "--path", "/changed", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"][0]["cwd"] == "/changed"


def test_legacy_claude_exact_scope_uses_encoded_project(corpus):
    claude, _ = corpus
    record = dict(CLAUDE_RECORDS[0])
    record.pop("cwd")
    claude.write_text(json.dumps(record))
    assert find("thing")["total"] == 1
    result = runner.invoke(app, ["find", "thing", "--path", "/", "--recursive", "--json"])
    assert result.exit_code == 1


def test_replacement_preserving_size_and_mtime_invalidates_index(corpus):
    claude, _ = corpus
    assert find("thing")["total"] == 1
    old = claude.stat()
    replacement = claude.with_suffix(".replacement")
    replacement.write_text(claude.read_text().replace("thing", "other"))
    os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
    replacement.replace(claude)
    assert claude.stat().st_size == old.st_size
    assert find("thing")["total"] == 0
    assert find("other")["total"] == 1


def test_changes_during_search_are_explicit_and_not_returned(corpus, monkeypatch):
    import sxr.find_service as service

    claude, _ = corpus
    original = service.search

    def search(*args):
        result = original(*args)
        claude.unlink()
        return result

    monkeypatch.setattr(service, "search", search)
    result = runner.invoke(app, ["find", "thing", "--path", "/w", "--json"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert not data["complete"] and not data["results"]


def test_corrupt_cached_text_names_recovery(corpus):
    find("thing")
    with connect() as index, index.db:
        index.db.execute("UPDATE find_text SET text=x'00'")
    result = runner.invoke(app, ["find", "thing", "--path", "/w", "--json"])
    assert result.exit_code == 2
    assert "sxr index --clear" in result.output


def test_incomplete_codex_header_does_not_claim_complete_coverage(corpus):
    _, codex = corpus
    codex.write_text('{"type":')
    result = runner.invoke(app, ["find", "thing", "--path", "/w", "--json"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert not data["complete"] and data["results"]


def test_escaped_unicode_is_searchable_and_surrogates_are_preserved(corpus):
    claude, _ = corpus
    value = "caf\u00e9 \ud800 searchable"
    claude.write_text(json.dumps(dict(CLAUDE_RECORDS[0], message={"content": value})))
    assert find("cafe")["results"][0]["evidence"][0]["text"] == value
    result = runner.invoke(app, ["find", "searchable", "--path", "/w"])
    assert result.exit_code == 0 and "searchable" in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["-n", "-1", "word"],
        ['"torn'],
        ["--codex", "--claude", "x"],
        ["--since", "yesterday", "x"],
    ],
)
def test_usage_errors_match_both_entry_points(corpus, arguments, capsys):
    from sxr.find_cli import main

    result = runner.invoke(app, ["find", *arguments])
    assert result.exit_code == 2
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_coverage_and_root_flags_keep_the_same_results(corpus, capsys):
    from sxr.find_cli import main

    direct = find("hello")
    result = runner.invoke(app, ["--path", "/w", "--json", "find", "hello"])
    assert result.exit_code == 0 and json.loads(result.stdout) == direct
    assert main(["hello", "--path", "/w", "--json", "--coverage"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == direct and "files searched" in captured.err


def test_explicit_missing_archive_root_is_reported(corpus):
    result = runner.invoke(app, ["find", "hello", "--path", "/w", "--archives", "--json"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert not data["complete"] and "archived_sessions" in data["errors"][0]
