"""Index candidates must preserve direct-search results across file and cache changes."""

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from sxr import index_records, index_store, search_index
from sxr.cli import app
from sxr.model import SessionRef
from test_index_records import record


@pytest.fixture
def transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    project = tmp_path / "projects/project"
    project.mkdir(parents=True)
    path = project / "one.jsonl"
    header = {
        "type": "user",
        "cwd": "/w",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": "a searchable title"},
    }
    path.write_bytes(json.dumps(header).encode() + b"\n" + record("old needle"))
    return SessionRef("claude", "one", path)


def test_warm_index_does_not_decode_unchanged_sources(transcript, monkeypatch):
    assert search_index.candidates([transcript], "needle", False) == {transcript.path}

    def unexpected(*args):
        raise AssertionError("unchanged transcript decoded again")

    monkeypatch.setattr(index_records, "read_update", unexpected)
    assert search_index.candidates([transcript], "absent", False) == set()
    assert search_index.candidates([transcript], "needle", False) == {transcript.path}


@pytest.mark.parametrize(
    "text,pattern",
    [
        ('escaped "quoted" text', '"quoted"'),
        ("İstanbul", "istanbul"),
        ("ıstanbul", "istanbul"),
        ("KELVIN", "kelvin"),
        ("ſession", "session"),
        ("Straße", "straße"),
        ("Σίγμα", "σίγμα"),
        ("你好世界", "你好世界"),
        ("first\nsecond", "first\nsecond"),
        ("before\0after", "after"),
        ("words OR literal", "words OR literal"),
        ("punctuation [abc]", "[abc]"),
    ],
)
def test_normalized_unicode_and_escaped_text_are_candidates(transcript, text, pattern):
    with transcript.path.open("ab") as stream:
        stream.write(record(text))
    assert search_index.candidates([transcript], pattern, True) == {transcript.path}


@pytest.mark.parametrize("pattern", ["a", "ab", "", "n.*dle", r"\bneedle\b", "a\0b", "\ud800ab"])
def test_unsupported_patterns_fall_back_without_creating_an_index(transcript, pattern):
    assert search_index.candidates([transcript], pattern, False) is None
    assert not index_store.index_path().exists()


def test_rewrite_replaces_old_candidates_and_append_keeps_existing_ones(transcript):
    refs = [transcript]
    assert search_index.candidates(refs, "old needle", True)
    with transcript.path.open("ab") as stream:
        stream.write(record("appended needle"))
    assert search_index.candidates(refs, "old needle", True)
    assert search_index.candidates(refs, "appended needle", True)
    transcript.path.write_bytes(record("rewritten file"))
    assert search_index.candidates(refs, "old needle", True) == set()
    assert search_index.candidates(refs, "appended needle", True) == set()
    assert search_index.candidates(refs, "rewritten file", True)


def test_trigram_candidates_are_checked_for_the_full_substring(transcript):
    with transcript.path.open("ab") as stream:
        stream.write(record("abc ... bcd ... cde ... def"))
    assert search_index.candidates([transcript], "abcdef", False) == set()


@pytest.mark.parametrize("body", [b"invalid compressed text", None])
def test_bad_compressed_cache_falls_back(transcript, body):
    assert search_index.candidates([transcript], "needle", False)
    with index_store.connect() as index, index.db:
        index.db.execute("UPDATE documents SET body=?", (body,))
    assert search_index.candidates([transcript], "needle", False) is None


def test_paths_keep_profiles_and_duplicate_ids_separate(transcript, tmp_path):
    copy = tmp_path / "different-profile.jsonl"
    copy.write_bytes(record("other profile"))
    second = SessionRef("claude", transcript.id, copy)
    assert search_index.candidates([transcript, second], "needle", False) == {transcript.path}
    assert search_index.candidates([transcript, second], "other profile", False) == {copy}


def test_deleted_sources_are_pruned(transcript):
    search_index.candidates([transcript], "needle", False)
    transcript.path.unlink()
    with index_store.connect() as index:
        index.prune()
        assert not index.matches("needle")
        assert index.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0


def test_cache_is_private_and_does_not_store_original_text(transcript):
    search_index.candidates([transcript], "needle", False)
    path = index_store.index_path()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    with index_store.connect() as index:
        assert all(row[0] is None for row in index.db.execute("SELECT body FROM terms"))


@pytest.mark.parametrize("failure", ["corrupt", "unwritable", "locked", "version", "disabled"])
def test_cache_failures_never_turn_into_empty_search_results(transcript, monkeypatch, failure):
    search_index.candidates([transcript], "needle", False)
    path = index_store.index_path()
    if failure == "corrupt":
        path.write_bytes(b"not a SQLite database")
    elif failure == "unwritable":
        monkeypatch.setenv("SXR_CACHE_DIR", str(transcript.path))
    elif failure == "version":
        monkeypatch.setattr(index_store, "FORMAT", 100)
    elif failure == "disabled":
        monkeypatch.setenv("SXR_NO_CACHE", "1")
    else:
        with sqlite3.connect(path) as db:
            db.execute("BEGIN EXCLUSIVE")
            assert search_index.candidates([transcript], "needle", False) is None
        return
    assert search_index.candidates([transcript], "needle", False) is None


@pytest.mark.parametrize(
    "args",
    [
        ["needle", "-c", "--all", "--json"],
        ["needle", "-C", "1"],
        ["needle", "--json"],
        ["needle", "-l"],
        ["Needle", "-i"],
        ["Needle"],
        ["absent", "-c"],
        ["n.*dle", "-c"],
    ],
)
def test_cold_and_warm_cli_outputs_equal_direct_reads(transcript, monkeypatch, args):
    sibling = transcript.path.with_name("two.jsonl")
    sibling.write_bytes(
        transcript.path.read_bytes().splitlines(keepends=True)[0] + record("zero-match session")
    )
    command = ["--path", "/w", "grep", *args]
    monkeypatch.setenv("SXR_NO_CACHE", "1")
    direct = CliRunner().invoke(app, command)
    monkeypatch.delenv("SXR_NO_CACHE")
    for _ in range(2):
        indexed = CliRunner().invoke(app, command)
        assert (indexed.exit_code, indexed.stdout, indexed.stderr) == (
            direct.exit_code,
            direct.stdout,
            direct.stderr,
        )


def test_index_command_builds_and_clears_corrupt_cache(transcript):
    result = CliRunner().invoke(app, ["--path", "/w", "index"])
    assert result.exit_code == 0, result.output
    index_store.index_path().write_bytes(b"corrupt")
    result = CliRunner().invoke(app, ["index", "--clear"])
    assert result.exit_code == 0, result.output
    assert not index_store.index_path().exists()


def test_unavailable_sqlite_extension_falls_back(transcript, monkeypatch):
    def unavailable(*args):
        raise sqlite3.OperationalError("no such module: fts5")

    monkeypatch.setattr(index_store, "_schema", unavailable)
    assert search_index.candidates([transcript], "needle", False) is None


def test_command_search_matches_direct_results(transcript, monkeypatch):
    row = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": "call",
                    "input": {"command": "git status"},
                }
            ]
        },
    }
    with transcript.path.open("ab") as stream:
        stream.write(json.dumps(row).encode() + b"\n")
    args = ["--path", "/w", "cmds", "--grep", "git status"]
    monkeypatch.setenv("SXR_NO_CACHE", "1")
    direct = CliRunner().invoke(app, args)
    monkeypatch.delenv("SXR_NO_CACHE")
    for _ in range(2):
        result = CliRunner().invoke(app, args)
        assert (result.exit_code, result.stdout, result.stderr) == (
            direct.exit_code,
            direct.stdout,
            direct.stderr,
        )


def test_clean_removes_an_index_created_during_the_rewrite(transcript, monkeypatch):
    from sxr.secrets import clean

    def rewrite(path, apply):
        assert search_index.candidates([transcript], "needle", False)
        return clean.FileResult(path.name, lines=1, replacements=1)

    monkeypatch.setattr(clean, "_clean_file", rewrite)
    assert clean.clean_view([transcript], lambda ref: [ref.path], apply=True) == 0
    assert not index_store.index_path().exists()


def test_clean_refuses_to_write_when_the_index_cannot_be_cleared(transcript):
    search_index.candidates([transcript], "needle", False)
    original = transcript.path.read_bytes()
    with sqlite3.connect(index_store.index_path()) as db:
        db.execute("BEGIN EXCLUSIVE")
        result = CliRunner().invoke(app, ["--path", "/w", "clean", "--apply"])
    assert result.exit_code == 2
    assert "cannot clear search index" in result.stderr
    assert transcript.path.read_bytes() == original


def test_appended_codex_outcome_preserves_canonical_search_results(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    path = sessions / "rollout-own.jsonl"
    meta = {
        "type": "session_meta",
        "timestamp": "2026-01-01",
        "payload": {"id": "own", "cwd": "/w"},
    }
    started = {
        "type": "event_msg",
        "payload": {
            "type": "item_started",
            "item": {"type": "CommandExecution", "id": "call", "command": "old command needle"},
        },
    }
    path.write_text("\n".join(map(json.dumps, [meta, started])) + "\n")
    scope = ["--codex", "--path", "/w", "grep", "-F", "-c", "--json"]
    assert CliRunner().invoke(app, [*scope, "old command needle"]).exit_code == 0
    completed = {
        "type": "event_msg",
        "payload": {
            "type": "item_completed",
            "item": {
                "type": "CommandExecution",
                "id": "call",
                "command": "corrected command",
                "aggregated_output": "new output needle",
                "exit_code": 7,
            },
        },
    }
    with path.open("a") as stream:
        stream.write(json.dumps(completed) + "\n")
    for query in ("old command needle", "corrected command", "new output needle"):
        indexed = CliRunner().invoke(app, [*scope, query])
        monkeypatch.setenv("SXR_NO_CACHE", "1")
        direct = CliRunner().invoke(app, [*scope, query])
        monkeypatch.delenv("SXR_NO_CACHE")
        assert (indexed.exit_code, indexed.stdout, indexed.stderr) == (
            direct.exit_code,
            direct.stdout,
            direct.stderr,
        )
