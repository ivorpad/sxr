"""Explicit transcript paths bypass discovery and preserve provider identity."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.file_selection import reference
from sxr.providers import claude_code, codex
from test_providers import _write_claude, _write_codex

runner = CliRunner()


@pytest.mark.parametrize("writer,provider", [(_write_claude, claude_code), (_write_codex, codex)])
def test_explicit_file_bypasses_discovery_and_accepts_both_flag_positions(
    tmp_path, monkeypatch, writer, provider
):
    path = writer(tmp_path, monkeypatch)
    detected, ref = reference(path)
    assert detected is provider
    monkeypatch.setattr(provider, "list_sessions", lambda *a, **kw: pytest.fail("discovery"))
    for args in (["--file", str(path), "show", ref.id], ["show", ref.id, "--file", str(path)]):
        result = runner.invoke(app, [*args, "--around", "2"])
        assert result.exit_code == 0, result.output
        assert f"file:     {path}" in result.output
    bad = runner.invoke(app, ["--file", str(path), "show", "wrong-id"])
    assert bad.exit_code == 2
    mismatch = "--claude" if provider is codex else "--codex"
    assert runner.invoke(app, [mismatch, "--file", str(path), "show"]).exit_code == 2
    assert runner.invoke(app, ["--path", "/other", "show", "--file", str(path)]).exit_code == 2
    assert runner.invoke(app, ["--path", "/w", "show", "--file", str(path)]).exit_code == 0


@pytest.mark.parametrize("nested", [False, True])
def test_claude_child_identity_and_explicit_parent_scope(tmp_path, monkeypatch, nested):
    parent = _write_claude(tmp_path, monkeypatch)
    folder = parent.parent / parent.stem
    child = (
        folder / "fork" / "subagents" / "nested" / "agent-worker.jsonl"
        if nested
        else folder / "subagents" / "agent-worker.jsonl"
    )
    child.parent.mkdir(parents=True)
    child.write_text(
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-01-01T00:00:00Z",
                "message": {"content": "child"},
            }
        )
    )
    provider, ref = reference(child)
    assert ref.id == f"{parent.stem}/{child.stem}"
    assert ref.cwd == "/w" and ref.kind == "agent"
    shown = runner.invoke(app, ["show", ref.id, "--file", str(child), "--tail", "1"])
    assert shown.exit_code == 0 and '"child"' in shown.output
    assert provider.session_paths(reference(parent)[1]) == [parent]
    discovered = provider.list_sessions("/w")[0]
    if not nested:
        assert provider.session_paths(discovered) == [parent, child]
    children = provider.list_sessions("/w", include_agents=True)
    found = next(r for r in children if r.kind == "agent")
    assert found.id == ref.id and found.cwd == ref.cwd


def test_file_validation_and_profile_constraints(tmp_path, monkeypatch):
    path = _write_claude(tmp_path, monkeypatch)
    root = tmp_path / ".claude"
    for value in (tmp_path / "missing", tmp_path):
        assert runner.invoke(app, ["--file", str(value), "show"]).exit_code == 2
    empty = tmp_path / "empty.jsonl"
    empty.write_text('{"type": "unknown"}\nnot json')
    assert runner.invoke(app, ["--file", str(empty), "show"]).exit_code == 2
    for flags in (["--claude-root", str(root)], ["--claude", "--path", "/w"]):
        assert runner.invoke(app, [*flags, "--file", str(path), "show"]).exit_code == 0
    for flags in (["--claude-root", str(tmp_path / "wrong")], ["--archives"]):
        assert runner.invoke(app, [*flags, "--file", str(path), "show"]).exit_code == 2
    assert runner.invoke(app, ["--file", str(path), "show", "--file", str(empty)]).exit_code == 2
    alias = tmp_path / "alias with spaces.jsonl"
    alias.symlink_to(path)
    assert reference(alias)[1].path == path
    coverage = runner.invoke(app, ["--file", str(path), "path", "--coverage"])
    assert coverage.exit_code == 0 and "explicit file" in coverage.stderr


def test_archived_and_title_only_transcripts(tmp_path, monkeypatch):
    source = _write_codex(tmp_path, monkeypatch)
    archived = tmp_path / "archived_sessions" / "copy.jsonl"
    archived.parent.mkdir()
    archived.write_bytes(source.read_bytes())
    assert reference(archived)[1].extra["archived"]
    assert runner.invoke(app, ["--file", str(archived), "show", "--archives"]).exit_code == 0
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text(json.dumps({"type": "ai-title", "aiTitle": "old session"}))
    assert reference(legacy)[0] is claude_code
    assert runner.invoke(app, ["show", "--file", str(legacy), "--full"]).exit_code == 0


def test_codex_file_uses_its_own_history_profile(tmp_path, monkeypatch):
    path = _write_codex(tmp_path, monkeypatch)
    sid = reference(path)[1].id
    history = tmp_path / ".codex" / "history.jsonl"
    history.write_text(json.dumps({"session_id": sid, "text": "profile-specific title"}))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "unrelated"))
    result = runner.invoke(app, ["list", "--file", str(path)])
    assert result.exit_code == 0 and "profile-specific title" in result.output
    missing = runner.invoke(app, ["--file", str(path), "show", "--include-agents"])
    assert missing.exit_code == 2


@pytest.mark.parametrize("writer", [_write_claude, _write_codex])
@pytest.mark.parametrize(
    "command",
    [
        ["list", "--json"],
        ["show", "--full"],
        ["prompts", "--json"],
        ["errors"],
        ["tools", "--json"],
        ["stats", "--json"],
        ["path"],
        ["grep", "-c", "the|hello"],
        ["grep", "ls|test", "-C", "2"],
        ["cmds", "--json"],
        ["cmds", "--grep", "ls|test"],
        ["secrets", "--json"],
        ["clean"],
    ],
)
def test_file_scope_matches_all_session_views(tmp_path, monkeypatch, writer, command):
    path = writer(tmp_path, monkeypatch)
    provider, ref = reference(path)
    if command[0] == "prompts":
        command = [*command, ref.id]
    scoped = runner.invoke(app, [f"--{ref.provider}", "--path", "/w", *command])
    explicit = runner.invoke(app, ["--file", str(path), *command])
    assert (explicit.exit_code, explicit.stdout, explicit.stderr) == (
        scoped.exit_code,
        scoped.stdout,
        scoped.stderr,
    )
