"""Build the synthetic two-session corpora used by the SXR-CLI-02 evidence runs.

Nothing here reads live session data: every transcript is written from the
literals below into a caller-supplied temporary root, and the Claude/Codex
discovery roots plus the sxr cache are redirected into that same root.
"""

import json
import os
from pathlib import Path

CLAUDE_IDS = (
    "aaaa1111-2222-3333-4444-555566667777",
    "bbbb1111-2222-3333-4444-555566667777",
)
CODEX_STAMPS = (
    ("2026-07-24T16-58-24-019f9510", "019f9510-5499-7000-8000-00000000aaaa"),
    ("2026-07-25T09-10-11-019f9511", "019f9511-5499-7000-8000-00000000bbbb"),
)


def _claude_records(tag: str, stamp: str) -> list[dict]:
    """One Claude session: two human prompts, two tool calls, one failing result."""
    return [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}:00Z",
            "message": {"role": "user", "content": f"{tag} first human prompt"},
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}:01Z",
            "isMeta": True,
            "message": {"role": "user", "content": f"{tag} injected rules"},
        },
        {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}:02Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "id": f"{tag}-a",
                        "input": {"command": "false"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "id": f"{tag}-b",
                        "input": {"file_path": "/tmp/x"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}:03Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"{tag}-a",
                        "is_error": True,
                        "content": f"{tag} boom",
                    }
                ],
            },
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}:04Z",
            "message": {"role": "user", "content": f"{tag} second human prompt"},
        },
    ]


def _codex_records(tag: str, session_id: str, stamp: str) -> list[dict]:
    """One Codex rollout with the same shape as the Claude fixture."""

    def message(text: str, kinds: list[str] | None = None) -> dict:
        payload: dict = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        }
        if kinds is not None:
            payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
        return {"type": "response_item", "timestamp": f"{stamp}:00Z", "payload": payload}

    return [
        {
            "type": "session_meta",
            "timestamp": f"{stamp}:00Z",
            "payload": {"id": session_id, "cwd": "/w"},
        },
        message(f"{tag} first human prompt", ["user.text"]),
        message(f"{tag} injected rules", ["agents_md.instructions"]),
        {
            "type": "response_item",
            "timestamp": f"{stamp}:02Z",
            "payload": {
                "type": "function_call",
                "call_id": f"{tag}-a",
                "name": "shell",
                "arguments": json.dumps({"command": ["bash", "-lc", "false"]}),
            },
        },
        {
            "type": "response_item",
            "timestamp": f"{stamp}:03Z",
            "payload": {
                "type": "function_call_output",
                "call_id": f"{tag}-a",
                "output": json.dumps({"output": f"{tag} boom", "metadata": {"exit_code": 1}}),
            },
        },
        message(f"{tag} second human prompt", ["user.text"]),
    ]


def build(root: Path) -> dict[str, object]:
    """Write both providers' corpora under root and return the env they need."""
    from sxr.providers import claude_code

    project = root / ".claude" / "projects" / claude_code.flatten_cwd("/w")
    project.mkdir(parents=True, exist_ok=True)
    stamps = ("2026-07-24T16:58:24", "2026-07-25T09:10:11")
    claude_paths = []
    for ident, tag, stamp in zip(CLAUDE_IDS, ("alpha", "bravo"), stamps, strict=True):
        path = project / f"{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in _claude_records(tag, stamp)))
        claude_paths.append(path)

    codex_paths = []
    for (name, ident), tag, stamp in zip(CODEX_STAMPS, ("charlie", "delta"), stamps, strict=True):
        day = root / ".codex" / "sessions" / name[:4] / name[5:7] / name[8:10]
        day.mkdir(parents=True, exist_ok=True)
        path = day / f"rollout-{name}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in _codex_records(tag, ident, stamp)))
        codex_paths.append(path)

    return {
        "env": {
            "CLAUDE_CONFIG_DIR": str(root / ".claude"),
            "CODEX_HOME": str(root / ".codex"),
            "SXR_CACHE_DIR": str(root / "cache"),
        },
        "claude": claude_paths,
        "codex": codex_paths,
    }


def apply_env(root: Path) -> dict[str, object]:
    """Build the corpora and export their discovery roots into os.environ."""
    built = build(root)
    os.environ.update(built["env"])  # type: ignore[arg-type]
    os.environ.pop("SXR_NO_CACHE", None)
    return built
