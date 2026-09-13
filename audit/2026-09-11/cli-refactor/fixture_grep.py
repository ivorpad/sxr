"""Synthetic corpora for the SXR-CLI-06 `grep` and `cmds` JSON captures.

The defects under test are about record identity and mode combinations, so the
fixture is built to make each one observable:

- One Claude physical record carries **two matching text blocks**, and another
  carries **two tool_use blocks**. Claude yields one event per content block and
  they share the line's sequence number, so raw `--json` can emit that one line
  twice. Codex yields exactly one event per physical record, so the duplication
  is not reachable there; both providers are captured anyway, because that
  asymmetry is itself worth pinning.
- Two matching events are adjacent, so `-C` windows overlap.
- The **newer** session has more matches than the older one, so `--sort matches`
  and `--sort started` produce different orders. With the counts the other way
  round both sorts would agree and the flag would look like it worked.
"""

import json
from pathlib import Path

CWD = "/w"
NEEDLE = "retry"


def _claude_records(marker: str, extra: int) -> list[dict]:
    """One session's physical records; extra adds plain matching lines."""

    def stamp(seq: int) -> str:
        return f"2026-09-{seq:02d}T12:{seq:02d}:00Z"

    def message(seq: int, role: str, content) -> dict:
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=stamp(seq),
            cwd=CWD,
            message=dict(role=role, content=content),
        )

    def text(seq: int, *bodies: str) -> dict:
        return message(seq, "assistant", [dict(type="text", text=body) for body in bodies])

    records = [
        dict(
            type="user",
            timestamp=stamp(1),
            cwd=CWD,
            message=dict(role="user", content=f"start {NEEDLE} {marker}"),
        ),
        # One line, two matching blocks: the raw-JSON duplication case.
        text(2, f"{NEEDLE} first block {marker}", f"{NEEDLE} second block {marker}"),
        # One line, two tool calls: the cmds raw-JSON duplication case.
        message(
            3,
            "assistant",
            [
                dict(
                    type="tool_use", id="call-a", name="Bash", input=dict(command=f"git {NEEDLE}")
                ),
                dict(
                    type="tool_use",
                    id="call-b",
                    name="Read",
                    input=dict(file_path=f"/w/{NEEDLE}.py"),
                ),
            ],
        ),
        message(
            4,
            "user",
            [
                dict(type="tool_result", tool_use_id="call-a", content="ok"),
                dict(type="tool_result", tool_use_id="call-b", content="ok"),
            ],
        ),
        # A second tool-bearing line, one call this time: three calls in two
        # physical records, so `cmds --json -n 2` can show two *distinct* ones.
        message(
            5,
            "assistant",
            [
                dict(
                    type="tool_use",
                    id="call-c",
                    name="Bash",
                    input=dict(command=f"git {NEEDLE} --again"),
                )
            ],
        ),
        message(6, "user", [dict(type="tool_result", tool_use_id="call-c", content="ok")]),
        # Adjacent hits, so -C windows overlap.
        text(7, f"adjacent {NEEDLE} one"),
        text(8, f"adjacent {NEEDLE} two"),
    ]
    records += [text(9 + n, f"{NEEDLE} extra {n} {marker}") for n in range(extra)]
    records.append(text(9 + extra, f"done {marker}"))
    return records


def _codex_records(ident: str, marker: str, extra: int) -> list[dict]:
    """The same coverage on Codex shapes, one event per physical record."""

    def stamp(seq: int) -> str:
        return f"2026-09-{seq:02d}T12:{seq:02d}:00Z"

    def item(seq: int, payload: dict) -> dict:
        return dict(timestamp=stamp(seq), type="response_item", payload=payload)

    def said(seq: int, role: str, body: str) -> dict:
        kind = "input_text" if role == "user" else "output_text"
        return item(seq, dict(type="message", role=role, content=[dict(type=kind, text=body)]))

    def executed(seq: int, call_id: str, cmd: list[str], output: str) -> dict:
        return dict(
            timestamp=stamp(seq),
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=call_id,
                    call_id=call_id,
                    command=cmd,
                    aggregated_output=output,
                    exit_code=0,
                ),
            ),
        )

    records = [
        dict(
            timestamp=stamp(1),
            type="session_meta",
            payload=dict(id=ident, cwd=CWD, timestamp=stamp(1)),
        ),
        said(1, "user", f"start {NEEDLE} {marker}"),
        said(2, "assistant", f"{NEEDLE} first block {marker}"),
        executed(3, "call-a", ["git", NEEDLE], "ok"),
        item(
            4,
            dict(
                type="function_call",
                name="read_file",
                call_id="call-b",
                arguments=json.dumps(dict(path=f"/w/{NEEDLE}.py")),
            ),
        ),
        executed(5, "call-c", ["git", NEEDLE, "--again"], "ok"),
        said(7, "assistant", f"adjacent {NEEDLE} one"),
        said(8, "assistant", f"adjacent {NEEDLE} two"),
    ]
    records += [said(9 + n, "assistant", f"{NEEDLE} extra {n} {marker}") for n in range(extra)]
    records.append(said(9 + extra, "assistant", f"done {marker}"))
    return records


# The newer session carries three extra matches, so the two --sort orders differ.
SESSIONS = [
    ("aaaaaaa1-0000-4000-8000-00000000000a", "01999991-aaaa-7000-8000-00000000000a", "alpha", 0),
    ("bbbbbbb2-0000-4000-8000-00000000000b", "01999992-bbbb-7000-8000-00000000000b", "beta", 3),
]


def claude(root: Path) -> list[Path]:
    """Two Claude sessions in one project directory, oldest first."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    written = []
    for ident, _codex_id, marker, extra in SESSIONS:
        path = project / f"{ident}.jsonl"
        body = _claude_records(marker, extra)
        path.write_text("\n".join(json.dumps(r) for r in body) + "\n")
        written.append(path)
    return written


def codex(root: Path) -> list[Path]:
    """Two Codex rollouts on separate days, oldest first."""
    written = []
    for day, (_claude_id, ident, marker, extra) in enumerate(SESSIONS, start=1):
        directory = root / "sessions" / "2026" / "09" / f"{day:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"rollout-2026-09-{day:02d}T12-00-00-{ident}.jsonl"
        body = _codex_records(ident, marker, extra)
        path.write_text("\n".join(json.dumps(r) for r in body) + "\n")
        written.append(path)
    return written
