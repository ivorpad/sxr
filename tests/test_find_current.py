"""Agents should retrieve earlier evidence without indexing their own growing transcript."""

import json

import pytest

from sxr.cli import app
from test_find import find, runner
from test_providers import _write_claude, _write_codex


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    return _write_claude(tmp_path, monkeypatch), _write_codex(tmp_path, monkeypatch)


def test_current_codex_is_excluded_before_parsing(corpus, monkeypatch):
    from sxr.providers import codex

    _, source = corpus
    identity = json.loads(source.read_text().splitlines()[0])["payload"]["session_id"]
    monkeypatch.setenv("CODEX_THREAD_ID", identity)
    monkeypatch.setattr(codex, "parse", lambda *a: pytest.fail("current session parsed"))
    result = find("hello")
    assert result["complete"] and result["total"] == 0
    assert sum(r["excluded"] for r in result["coverage"]) == 1
    assert find("thing")["total"] == 1


def test_current_override_and_explicit_file(corpus, monkeypatch):
    _, source = corpus
    identity = json.loads(source.read_text().splitlines()[0])["payload"]["session_id"]
    monkeypatch.setenv("CODEX_THREAD_ID", identity)
    assert find("hello", "--include-current")["total"] == 1
    result = runner.invoke(app, ["find", "hello", "--file", str(source), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"][0]["id"] == identity


def test_explicit_exclusion_accepts_claude_and_exact_ids(corpus):
    source, _ = corpus
    assert find("thing", "--exclude-session", source.stem)["total"] == 0
    assert find("thing", "--exclude-session", source.stem[:8])["total"] == 1
    assert find("thing", "--include-current", "--exclude-session", source.stem)["total"] == 0


def test_thread_id_takes_precedence_over_legacy_session_id(corpus, monkeypatch):
    _, source = corpus
    identity = json.loads(source.read_text().splitlines()[0])["payload"]["session_id"]
    monkeypatch.setenv("CODEX_SESSION_ID", identity)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    assert find("hello")["total"] == 0
    monkeypatch.setenv("CODEX_THREAD_ID", "another-thread")
    assert find("hello")["total"] == 1


def test_fast_cli_keeps_exclusion_and_override_semantics(corpus, monkeypatch, capsys):
    from sxr.find_cli import main

    claude, source = corpus
    identity = json.loads(source.read_text().splitlines()[0])["payload"]["session_id"]
    monkeypatch.setenv("CODEX_THREAD_ID", identity)
    args = [
        "thing hello",
        "--any",
        "--path",
        "/w",
        "--json",
        "--include-current",
        "--exclude-session",
        claude.stem,
    ]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in result["results"]] == [identity]
