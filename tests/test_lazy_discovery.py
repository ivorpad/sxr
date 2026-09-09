"""Discovery must not parse unrelated transcripts or repeat a selected read."""

import json
from collections import Counter
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.providers import claude_code, codex


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    provider = codex if request.param == "codex" else claude_code
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    directory = tmp_path / ("sessions" if provider is codex else "projects/project")
    directory.mkdir(parents=True)
    for index in (1, 2):
        identity = f"session-{index}"
        timestamp = f"2026-07-0{index}T00:00:00Z"
        if provider is codex:
            filename = f"rollout-{identity}.jsonl"
            records = [
                {
                    "type": "session_meta",
                    "timestamp": timestamp,
                    "payload": {"id": identity, "cwd": "/w"},
                },
                {
                    "type": "event_msg",
                    "timestamp": timestamp,
                    "payload": {"type": "user_message", "message": f"title {index}"},
                },
                {
                    "type": "response_item",
                    "timestamp": timestamp,
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "found needle"}],
                    },
                },
            ]
        else:
            filename = f"{identity}.jsonl"
            records = [
                {"type": "progress"},
                {
                    "type": "user",
                    "timestamp": timestamp,
                    "cwd": "/w",
                    "message": {"content": f"title {index}"},
                },
                {
                    "type": "assistant",
                    "timestamp": timestamp,
                    "message": {
                        "content": [
                            {"type": "text", "text": "found needle"},
                            {"type": "thinking", "thinking": "reason"},
                        ],
                        "usage": {"output_tokens": 7},
                    },
                },
            ]
        (directory / filename).write_text("\n".join(json.dumps(row) for row in records))
    calls = Counter()
    original = provider.parse

    def counted(path):
        calls[path.name] += 1
        return original(path)

    monkeypatch.setattr(provider, "parse", counted)
    return provider, calls


def invoke(provider, *args):
    return CliRunner().invoke(
        app, [f"--{provider.__name__.split('.')[-1].split('_')[0]}", "--path", "/w", *args]
    )


@pytest.mark.parametrize("selector", ["session-1", "@2"])
def test_path_never_parses_transcripts(corpus, monkeypatch, selector):
    provider, calls = corpus

    def unexpected(*args, **kwargs):
        raise AssertionError("path lookup loaded a summary")

    monkeypatch.setattr(provider, "_summarize", unexpected)
    result = invoke(provider, "path", selector)
    assert result.exit_code == 0, result.output
    assert "session-1.jsonl" in result.stdout
    assert not calls


@pytest.mark.parametrize("command", ["show", "stats", "prompts", "tools", "errors", "cmds"])
def test_selected_transcript_parsed_once(corpus, command):
    provider, calls = corpus
    result = invoke(provider, command, "session-1")
    assert result.exit_code in (0, 1), result.output
    assert sum(calls.values()) == 1
    assert "session-1" in next(iter(calls))
    if command == "stats":
        assert "messages\t" + ("1" if provider is codex else "2") in result.stdout


def test_count_reuses_events_for_summaries(corpus, monkeypatch):
    provider, calls = corpus
    records = Counter()
    original = provider._iter_records

    def counted(path):
        for seq, record in original(path):
            records[(path.name, seq)] += 1
            yield seq, record

    monkeypatch.setattr(provider, "_iter_records", counted)
    result = invoke(provider, "grep", "needle", "-c", "--json")
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert {row["title"] for row in rows} == {"title 1", "title 2"}
    assert all(row["matches"] == 1 for row in rows)
    assert list(calls.values()) == [1, 1]
    # Claude discovery needs the first two records. The remaining body is read once.
    assert all(count == 1 for (_, seq), count in records.items() if seq == 3)


def test_limited_list_summarizes_only_visible_sessions(corpus, monkeypatch):
    provider, _ = corpus
    summarized = []
    original = provider._summarize

    def counted(first, *args, **kwargs):
        summarized.append(first)
        return original(first, *args, **kwargs)

    monkeypatch.setattr(provider, "_summarize", counted)
    result = invoke(provider, "list", "-n", "1", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == "session-2"
    assert len(summarized) == 1


def test_names_and_time_handles_still_resolve(corpus):
    provider, _ = corpus
    result = invoke(provider, "path", "title 1")
    assert result.exit_code == 0 and "session-1.jsonl" in result.stdout
    result = invoke(provider, "--before", "@1", "path", "@1")
    assert result.exit_code == 0 and "session-1.jsonl" in result.stdout


def test_new_invocation_sees_appended_records(corpus):
    provider, _ = corpus
    path = provider.list_sessions("/w", lazy=True)[0].path
    initial = invoke(provider, "list", "--json").stdout
    row = (
        {"type": "response_item", "payload": {"type": "message", "content": []}}
        if provider is codex
        else {"type": "user", "message": {"content": "new"}}
    )
    with path.open("a") as stream:
        stream.write("\n" + json.dumps(row))
    after = invoke(provider, "list", "--json").stdout
    before_row, after_row = (json.loads(value.splitlines()[0]) for value in (initial, after))
    assert after_row["messages"] == before_row["messages"] + 1


def test_clean_loads_live_state_before_touching_a_file(corpus, monkeypatch):
    from sxr.secrets import clean

    provider, _ = corpus
    path = provider.list_sessions("/w", lazy=True)[0].path
    record = {"type": "progress", "timestamp": datetime.now(UTC).isoformat()}
    with path.open("a") as stream:
        stream.write("\n" + json.dumps(record))

    def unexpected(*args):
        raise AssertionError("clean attempted to process a live file")

    monkeypatch.setattr(clean, "_clean_file", unexpected)
    original = path.read_bytes()
    result = invoke(provider, "clean", "session-2", "--apply")
    assert result.exit_code == 1, result.output
    assert "skipped 1 (live) session" in result.stdout
    assert path.read_bytes() == original


def test_titles_are_refreshed_per_discovery(corpus):
    provider, _ = corpus
    path = provider.list_sessions("/w", lazy=True)[0].path
    for title in ("first name", "changed name"):
        if provider is codex:
            history = codex.sessions_root().parent / "history.jsonl"
            history.write_text(json.dumps({"session_id": "session-2", "text": title}))
        else:
            with path.open("a") as stream:
                stream.write("\n" + json.dumps({"type": "ai-title", "aiTitle": title}))
        result = invoke(provider, "list", "-n", "1", "--json")
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["title"] == title


def test_child_keeps_last_user_cwd_and_parent_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    project = tmp_path / "projects/project"
    agents = project / "parent/subagents"
    agents.mkdir(parents=True)
    (project / "parent.jsonl").write_text(
        json.dumps(
            {"type": "user", "cwd": "/w", "timestamp": "2026-01-01", "message": {"content": "hi"}}
        )
    )
    for name, cwd in (("changed", "/elsewhere"), ("empty", "")):
        rows = [
            {"type": "progress", "cwd": "/ignore", "timestamp": "2026-01-02"},
            {"type": "user", "cwd": cwd, "message": {"content": "child"}},
        ]
        (agents / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    result = invoke(claude_code, "--include-agents", "list", "--json")
    assert result.exit_code == 0, result.output
    rows = {r["id"]: r for r in map(json.loads, result.stdout.splitlines())}
    assert rows["parent/changed"]["cwd"] == "/elsewhere"
    assert rows["parent/empty"]["cwd"] == "/w"
