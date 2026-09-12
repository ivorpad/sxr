"""Build the synthetic corpora used by the SXR-CLI-03 show evidence runs.

Nothing here reads live session data. Both providers get one session carrying
every kind the selection pipeline distinguishes -- human text, thinking, a tool
call with a successful result, a tool call with a failing result, a provider meta
record, and one long text record so the character budget has something to trim.
Discovery roots and the sxr cache are redirected into the caller's temporary root.
"""

import json
import os
from pathlib import Path

CLAUDE_ID = "cccc1111-2222-3333-4444-555566667777"
CODEX_STAMP = ("2026-08-01T08-00-00-019f9520", "019f9520-5499-7000-8000-00000000cccc")
LONG_TEXT = "a long assistant answer that repeats itself. " * 1200 + "unique ending"


def _claude_records() -> list[dict]:
    """One Claude session: 9 physical records covering every selectable kind."""
    stamp = "2026-08-01T08:00:0"
    return [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}0Z",
            "message": {"role": "user", "content": "human ask one"},
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}1Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "weighing options"}],
            },
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}2Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "short answer"}]},
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}3Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Bash", "id": "ok-1", "input": {"command": "true"}}
                ],
            },
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}4Z",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "ok-1", "content": "fine"}],
            },
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}5Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "id": "bad-1",
                        "input": {"command": "false"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}6Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "bad-1",
                        "is_error": True,
                        "content": "exploded on purpose",
                    }
                ],
            },
        },
        {
            "type": "system",
            "cwd": "/w",
            "timestamp": f"{stamp}7Z",
            "content": "a system meta record",
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}8Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": LONG_TEXT}]},
        },
    ]


def _codex_records(session_id: str) -> list[dict]:
    """One Codex rollout with the same kind coverage as the Claude fixture."""
    stamp = "2026-08-01T08:00:0"

    def item(payload: dict, second: int) -> dict:
        return {"type": "response_item", "timestamp": f"{stamp}{second}Z", "payload": payload}

    def message(text: str, kinds: list[str]) -> dict:
        return {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"content_item_kinds": kinds},
        }

    return [
        {
            "type": "session_meta",
            "timestamp": f"{stamp}0Z",
            "payload": {"id": session_id, "cwd": "/w"},
        },
        item(message("human ask one", ["user.text"]), 0),
        item(
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "weighing options"}],
            },
            1,
        ),
        item(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "short answer"}],
            },
            2,
        ),
        item(
            {
                "type": "function_call",
                "call_id": "ok-1",
                "name": "shell",
                "arguments": json.dumps({"command": ["bash", "-lc", "true"]}),
            },
            3,
        ),
        item(
            {
                "type": "function_call_output",
                "call_id": "ok-1",
                "output": json.dumps({"output": "fine", "metadata": {"exit_code": 0}}),
            },
            4,
        ),
        item(
            {
                "type": "function_call",
                "call_id": "bad-1",
                "name": "shell",
                "arguments": json.dumps({"command": ["bash", "-lc", "false"]}),
            },
            5,
        ),
        item(
            {
                "type": "function_call_output",
                "call_id": "bad-1",
                "output": json.dumps(
                    {"output": "exploded on purpose", "metadata": {"exit_code": 1}}
                ),
            },
            6,
        ),
        {
            "type": "turn_context",
            "timestamp": f"{stamp}7Z",
            "payload": {"cwd": "/w", "model": "gpt-x"},
        },
        item(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": LONG_TEXT}],
            },
            8,
        ),
    ]


def build(root: Path) -> dict[str, object]:
    """Write both providers' corpora under root and return the env they need."""
    from sxr.providers import claude_code

    project = root / ".claude" / "projects" / claude_code.flatten_cwd("/w")
    project.mkdir(parents=True, exist_ok=True)
    claude = project / f"{CLAUDE_ID}.jsonl"
    claude.write_text("\n".join(json.dumps(r) for r in _claude_records()))

    name, ident = CODEX_STAMP
    day = root / ".codex" / "sessions" / name[:4] / name[5:7] / name[8:10]
    day.mkdir(parents=True, exist_ok=True)
    codex = day / f"rollout-{name}.jsonl"
    codex.write_text("\n".join(json.dumps(r) for r in _codex_records(ident)))

    return {
        "env": {
            "CLAUDE_CONFIG_DIR": str(root / ".claude"),
            "CODEX_HOME": str(root / ".codex"),
            "SXR_CACHE_DIR": str(root / "cache"),
        },
        "claude": claude,
        "codex": codex,
    }


def apply_env(root: Path) -> dict[str, object]:
    """Build the corpora and export their discovery roots into os.environ."""
    built = build(root)
    os.environ.update(built["env"])  # type: ignore[arg-type]
    os.environ.pop("SXR_NO_CACHE", None)
    return built
