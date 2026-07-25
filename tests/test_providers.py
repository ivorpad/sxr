"""Provider parsing against miniature fixture files in tmp dirs."""

import json
from pathlib import Path

from sxr.providers import claude_code, codex

CLAUDE_RECORDS = [
    {
        "type": "user",
        "timestamp": "2026-07-02T12:11:03.000Z",
        "cwd": "/w",
        "gitBranch": "main",
        "message": {"role": "user", "content": "do the thing"},
    },
    {
        "type": "assistant",
        "timestamp": "2026-07-02T12:11:09.000Z",
        "message": {
            "model": "claude-fable-5",
            "usage": {"output_tokens": 7},
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "just test"}}
            ],
        },
    },
    {
        "type": "user",
        "timestamp": "2026-07-02T12:11:15.000Z",
        "cwd": "/w",
        "gitBranch": "main",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "is_error": True,
                    "content": "Exit code 1",
                }
            ],
        },
    },
    {"type": "ai-title", "aiTitle": "Fixture session"},
    {"type": "custom-title", "customTitle": "fixed-name"},
]


def _write_claude(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    project = tmp_path / ".claude" / "projects" / claude_code.flatten_cwd("/w")
    project.mkdir(parents=True)
    session = project / "aaaa1111-2222-3333-4444-555566667777.jsonl"
    session.write_text("\n".join(json.dumps(r) for r in CLAUDE_RECORDS))
    return session


def test_claude_flatten() -> None:
    # every non-alphanumeric becomes "-": separators, dots, underscores, spaces
    assert claude_code.flatten_cwd("/home/user/.claude") == "-home-user--claude"
    assert claude_code.flatten_cwd("/srv/my_app v2.0") == "-srv-my-app-v2-0"


def test_claude_list_and_parse(tmp_path: Path, monkeypatch) -> None:
    _write_claude(tmp_path, monkeypatch)
    refs = claude_code.list_sessions("/w")
    assert len(refs) == 1
    ref = refs[0]
    assert (ref.messages, ref.errors, ref.tokens) == (3, 1, 7)
    assert ref.title == "Fixture session"
    assert ref.name == "fixed-name"
    events = claude_code.parse(ref.path)
    tool = next(e for e in events if e.kind == "tool")
    result = next(e for e in events if e.kind == "result")
    assert tool.tag == "err" and result.tool == "Bash" and result.is_error


CODEX_RECORDS = [
    {
        "timestamp": "2026-07-24T16:58:24.000Z",
        "type": "session_meta",
        "payload": {
            "session_id": "019f9510-5499-72a0-80b1-782880a12e38",
            "cwd": "/w",
            "originator": "codex_exec",
            "source": "exec",
            "cli_version": "0.145.0",
        },
    },
    {
        "timestamp": "2026-07-24T16:58:25.000Z",
        "type": "turn_context",
        "payload": {"model": "gpt-5.6-sol", "effort": "high"},
    },
    {
        "timestamp": "2026-07-24T16:58:26.000Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        },
    },
    {
        "timestamp": "2026-07-24T16:58:27.000Z",
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "exec_command",
            "arguments": '{"cmd":"ls"}',
            "call_id": "c1",
        },
    },
    {
        "timestamp": "2026-07-24T16:58:28.000Z",
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": "c1",
            "output": json.dumps({"output": "boom", "metadata": {"exit_code": 2}}),
        },
    },
    {
        "timestamp": "2026-07-24T16:58:29.000Z",
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 4200}}},
    },
]


def _write_codex(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    day_dir = tmp_path / ".codex" / "sessions" / "2026" / "07" / "24"
    day_dir.mkdir(parents=True)
    rollout = day_dir / "rollout-2026-07-24T16-58-24-019f9510.jsonl"
    rollout.write_text("\n".join(json.dumps(r) for r in CODEX_RECORDS))
    return rollout


def test_codex_list_and_parse(tmp_path: Path, monkeypatch) -> None:
    _write_codex(tmp_path, monkeypatch)
    refs = codex.list_sessions("/w")
    assert len(refs) == 1
    ref = refs[0]
    assert ref.kind == "exec"
    assert (ref.messages, ref.errors, ref.tokens) == (1, 1, 4200)
    assert ref.model == "gpt-5.6-sol/high"
    events = codex.parse(ref.path)
    result = next(e for e in events if e.kind == "result")
    assert result.is_error and result.tool == "exec_command" and result.text == "boom"


def test_codex_ignores_other_cwd(tmp_path: Path, monkeypatch) -> None:
    _write_codex(tmp_path, monkeypatch)
    assert codex.list_sessions("/elsewhere") == []
