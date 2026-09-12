"""Synthetic two-session corpora for the SXR-CLI-05 `cmds` captures.

The defect under test is scope, so both providers get two sessions whose tool
calls are distinguishable by session, and a pattern that matches in *both* —
that is the case where the old implicit all-sessions scope shows and the new
default does not. One command is long enough to show whether call text is
trimmed, and one non-shell tool call is present because `cmds` covers every
recorded tool, not only shells.
"""

import json
from pathlib import Path

CWD = "/w"
LONG = "git push origin " + "refs/heads/very-long-branch-name " * 12 + "--force-with-lease"


def _claude_records(stamp: str, marker: str) -> list[dict]:
    """Eight physical records: three tool calls with paired results, plus text."""

    def message(seq: int, role: str, content) -> dict:
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            cwd=CWD,
            message=dict(role=role, content=content),
        )

    def call(seq: int, call_id: str, tool: str, arguments: dict) -> dict:
        return message(
            seq, "assistant", [dict(type="tool_use", id=call_id, name=tool, input=arguments)]
        )

    def result(seq: int, call_id: str, body: str, failed: bool = False) -> dict:
        block = dict(type="tool_result", tool_use_id=call_id, content=body)
        return message(seq, "user", [dict(block, is_error=True) if failed else block])

    return [
        dict(type="user", timestamp=stamp, cwd=CWD, message=dict(role="user", content="start")),
        call(2, "call-a", "Bash", dict(command=f"git push origin {marker}")),
        result(3, "call-a", "pushed"),
        call(4, "call-b", "Read", dict(file_path=f"/w/{marker}.py")),
        result(5, "call-b", "contents"),
        call(6, "call-c", "Bash", dict(command=LONG)),
        result(7, "call-c", "rejected", failed=True),
        message(8, "assistant", [dict(type="text", text=f"done {marker}")]),
    ]


def _codex_records(ident: str, marker: str) -> list[dict]:
    """Seven physical records mirroring the Claude coverage on Codex shapes.

    Shell commands are `event_msg`/`item_completed` CommandExecution items, the
    shape Codex uses to record normalized command text; one non-shell
    `function_call` keeps `cmds`' all-tool coverage in the captures.
    """

    def item(seq: int, payload: dict) -> dict:
        return dict(
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z", type="response_item", payload=payload
        )

    def executed(seq: int, call_id: str, cmd, output: str, code: int = 0) -> dict:
        return dict(
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=call_id,
                    call_id=call_id,
                    command=cmd,
                    aggregated_output=output,
                    exit_code=code,
                ),
            ),
        )

    return [
        dict(
            timestamp="2026-09-01T12:00:00Z",
            type="session_meta",
            payload=dict(id=ident, cwd=CWD, timestamp="2026-09-01T12:00:00Z"),
        ),
        item(
            1,
            dict(type="message", role="user", content=[dict(type="input_text", text="start")]),
        ),
        executed(2, "call-a", ["git", "push", "origin", marker], "pushed"),
        item(
            3,
            dict(
                type="function_call",
                name="read_file",
                call_id="call-b",
                arguments=json.dumps(dict(path=f"/w/{marker}.py")),
            ),
        ),
        item(
            4,
            dict(
                type="function_call_output",
                call_id="call-b",
                output=json.dumps(dict(output="contents", metadata=dict(exit_code=0))),
            ),
        ),
        executed(6, "call-c", LONG.split(), "rejected", 1),
        item(
            8,
            dict(
                type="message",
                role="assistant",
                content=[dict(type="output_text", text=f"done {marker}")],
            ),
        ),
    ]


def claude(root: Path) -> list[Path]:
    """Two Claude sessions in one project directory, oldest first."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    written = []
    for ident, stamp, marker in [
        ("aaaaaaa1-0000-4000-8000-00000000000a", "2026-09-01T12:00:00Z", "alpha"),
        ("bbbbbbb2-0000-4000-8000-00000000000b", "2026-09-02T12:00:00Z", "beta"),
    ]:
        path = project / f"{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in _claude_records(stamp, marker)) + "\n")
        written.append(path)
    return written


def codex(root: Path) -> list[Path]:
    """Two Codex rollouts on separate days, oldest first."""
    written = []
    for day, (ident, marker) in enumerate(
        [
            ("01999991-aaaa-7000-8000-00000000000a", "alpha"),
            ("01999992-bbbb-7000-8000-00000000000b", "beta"),
        ],
        start=1,
    ):
        directory = root / "sessions" / "2026" / "09" / f"0{day}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"rollout-2026-09-0{day}T12-00-00-{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in _codex_records(ident, marker)) + "\n")
        written.append(path)
    return written
