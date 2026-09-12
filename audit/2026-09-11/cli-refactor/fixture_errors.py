"""Synthetic two-session corpora for the SXR-CLI-04 errors captures.

Both providers get two sessions that each record an error at the *same* physical
sequence, which is the case CMD-errors-typer's acceptance names. One error body
is long and multi-line so complete-text output is visibly different from the
trimmed form, and one tool failure is recorded twice (same tool_use_id) so
per-transcript dedup stays observable.
"""

import json
from pathlib import Path

CWD = "/w"
LONG = (
    "Traceback (most recent call last):\n"
    '  File "/w/app/main.py", line 118, in handler\n'
    "    payload = decode(body)\n"
    '  File "/w/app/codec.py", line 42, in decode\n'
    "    raise ValueError(unexpected token at offset 8175)\n"
    + "ValueError: "
    + "unexpected token " * 60
    + "\n"
    "The failure is at the END of this message, which middle trimming keeps but "
    "everything before it does not survive: exit status 65."
)


def _claude_records(stamp: str, marker: str) -> list[dict]:
    """Nine physical records: a matched tool failure, a repeat, and a long error."""

    def user(seq: int, blocks: list[dict]) -> dict:
        return dict(
            type="user",
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            cwd=CWD,
            message=dict(role="user", content=blocks),
        )

    def assistant(seq: int, blocks: list[dict]) -> dict:
        return dict(
            type="assistant",
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            cwd=CWD,
            message=dict(role="assistant", content=blocks),
        )

    return [
        dict(
            type="user",
            timestamp=stamp,
            cwd=CWD,
            message=dict(role="user", content=f"start {marker}"),
        ),
        assistant(2, [dict(type="text", text=f"working on {marker}")]),
        assistant(3, [dict(type="tool_use", id="call-a", name="Bash", input=dict(command="ls"))]),
        user(4, [dict(type="tool_result", tool_use_id="call-a", content="ok", is_error=False)]),
        assistant(5, [dict(type="tool_use", id="call-b", name="Read", input=dict(file_path="/x"))]),
        # seq 6 in both sessions: the same sequence carrying an error.
        user(
            6,
            [
                dict(
                    type="tool_result",
                    tool_use_id="call-b",
                    content=f"ENOENT: /x {marker}",
                    is_error=True,
                )
            ],
        ),
        # A second physical record for the same call id: dedup must drop it.
        user(
            7,
            [
                dict(
                    type="tool_result",
                    tool_use_id="call-b",
                    content="ENOENT: /x (repeat)",
                    is_error=True,
                )
            ],
        ),
        assistant(8, [dict(type="tool_use", id="call-c", name="Bash", input=dict(command="run"))]),
        user(9, [dict(type="tool_result", tool_use_id="call-c", content=LONG, is_error=True)]),
    ]


def _codex_records(ident: str, marker: str) -> list[dict]:
    """Ten physical records mirroring the Claude coverage on Codex shapes."""

    def item(seq: int, payload: dict) -> dict:
        return dict(
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z", type="response_item", payload=payload
        )

    return [
        dict(
            timestamp="2026-09-01T12:00:00Z",
            type="session_meta",
            payload=dict(id=ident, cwd=CWD, timestamp="2026-09-01T12:00:00Z"),
        ),
        item(
            1,
            dict(
                type="message",
                role="user",
                content=[dict(type="input_text", text=f"start {marker}")],
            ),
        ),
        item(
            2,
            dict(
                type="message",
                role="assistant",
                content=[dict(type="output_text", text=f"working on {marker}")],
            ),
        ),
        item(
            3,
            dict(
                type="function_call",
                name="shell",
                call_id="call-a",
                arguments=json.dumps(dict(command=["ls"])),
            ),
        ),
        item(
            4,
            dict(
                type="function_call_output",
                call_id="call-a",
                output=json.dumps(dict(output="ok", metadata=dict(exit_code=0))),
            ),
        ),
        item(
            5,
            dict(
                type="function_call",
                name="shell",
                call_id="call-b",
                arguments=json.dumps(dict(command=["cat", "/x"])),
            ),
        ),
        item(
            6,
            dict(
                type="function_call_output",
                call_id="call-b",
                output=json.dumps(dict(output=f"ENOENT: /x {marker}", metadata=dict(exit_code=1))),
            ),
        ),
        item(
            7,
            dict(
                type="function_call_output",
                call_id="call-b",
                output=json.dumps(dict(output="ENOENT: /x (repeat)", metadata=dict(exit_code=1))),
            ),
        ),
        item(
            8,
            dict(
                type="function_call",
                name="shell",
                call_id="call-c",
                arguments=json.dumps(dict(command=["run"])),
            ),
        ),
        item(
            9,
            dict(
                type="function_call_output",
                call_id="call-c",
                output=json.dumps(dict(output=LONG, metadata=dict(exit_code=65))),
            ),
        ),
    ]


def claude(root: Path) -> list[Path]:
    """Two Claude sessions under one project directory, oldest first."""
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
    # The first 13 characters differ, so short_id stays short. A colliding pair is
    # exercised by tests/test_errors_view.py instead, where the expansion is the point.
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
