"""Offset-bearing corpora for the SXR-CLI-08 timestamp captures.

Four sessions per provider, whose recorded start timestamps sort one way as
strings and another way as instants. That divergence is the whole defect, so the
fixture is built to make it unmissable:

    key        recorded start              UTC instant
    S1         2026-09-10T09:00:00+02:00   2026-09-10T07:00:00Z
    S2         2026-09-10T07:00:00Z        2026-09-10T07:00:00Z   same as S1
    S3         2026-09-10T08:00:00Z        2026-09-10T08:00:00Z
    S4         2026-09-11T00:30:00+02:00   2026-09-10T22:30:00Z   an earlier day

Sorted as strings, newest first: S4, S1, S3, S2. Sorted by instant: S4, S3, then
S1 and S2, which record the same moment and must land adjacent. So `@2` through
`@4` name different sessions depending on which comparison is used, and S4's
displayed date is a day later than the day whose UTC window contains it.

Match counts differ per session (1, 2, 3, 4) so `grep -c --sort matches` stays
distinguishable from `--sort started`, and S1 carries an offset-bearing *event*
timestamp so the time-of-day column is exercised too.
"""

import json
from pathlib import Path

CWD = "/w"
NEEDLE = "chronology"

# (short key, claude id, codex id, recorded start, offset event stamp, matches)
SESSIONS = [
    (
        "S1",
        "aaaaaaa1-0000-4000-8000-00000000000a",
        "01999991-aaaa-7000-8000-00000000000a",
        "2026-09-10T09:00:00+02:00",
        "2026-09-10T09:05:00+02:00",
        1,
    ),
    (
        "S2",
        "bbbbbbb2-0000-4000-8000-00000000000b",
        "01999992-bbbb-7000-8000-00000000000b",
        "2026-09-10T07:00:00Z",
        "2026-09-10T07:05:00Z",
        2,
    ),
    (
        "S3",
        "ccccccc3-0000-4000-8000-00000000000c",
        "01999993-cccc-7000-8000-00000000000c",
        "2026-09-10T08:00:00Z",
        "2026-09-10T08:05:00Z",
        3,
    ),
    (
        "S4",
        "ddddddd4-0000-4000-8000-00000000000d",
        "01999994-dddd-7000-8000-00000000000d",
        "2026-09-11T00:30:00+02:00",
        "2026-09-11T00:35:00+02:00",
        4,
    ),
]


def _claude_records(key: str, start: str, event_stamp: str, matches: int) -> list[dict]:
    """One session: a start record, a tool call, then `matches` matching lines."""

    def message(stamp: str, role: str, content) -> dict:
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=stamp,
            cwd=CWD,
            message=dict(role=role, content=content),
        )

    records = [
        dict(
            type="user",
            timestamp=start,
            cwd=CWD,
            message=dict(role="user", content=f"open {key}"),
        ),
        message(
            event_stamp,
            "assistant",
            [
                dict(
                    type="tool_use",
                    id=f"call-{key}",
                    name="Bash",
                    input=dict(command=f"git log {key}"),
                )
            ],
        ),
        message(
            event_stamp, "user", [dict(type="tool_result", tool_use_id=f"call-{key}", content="ok")]
        ),
    ]
    records += [
        message(event_stamp, "assistant", [dict(type="text", text=f"{NEEDLE} {key} note {n}")])
        for n in range(matches)
    ]
    return records


def _codex_records(ident: str, key: str, start: str, event_stamp: str, matches: int) -> list[dict]:
    """The same coverage on Codex shapes; `started` is session_meta's timestamp."""

    def item(stamp: str, payload: dict) -> dict:
        return dict(timestamp=stamp, type="response_item", payload=payload)

    def said(stamp: str, role: str, body: str) -> dict:
        """A Codex turn. Human turns are event_msg/user_message, which is the
        record the session title comes from; a response_item with role "user"
        is a valid record that yields no title."""
        if role == "user":
            return dict(
                timestamp=stamp,
                type="event_msg",
                payload=dict(type="user_message", message=body),
            )
        payload = dict(type="message", role=role, content=[dict(type="output_text", text=body)])
        return item(stamp, payload)

    records = [
        dict(
            timestamp=start,
            type="session_meta",
            payload=dict(id=ident, cwd=CWD, timestamp=start),
        ),
        said(start, "user", f"open {key}"),
        dict(
            timestamp=event_stamp,
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=f"call-{key}",
                    call_id=f"call-{key}",
                    command=["git", "log", key],
                    aggregated_output="ok",
                    exit_code=0,
                ),
            ),
        ),
    ]
    records += [said(event_stamp, "assistant", f"{NEEDLE} {key} note {n}") for n in range(matches)]
    return records


def claude(root: Path) -> list[Path]:
    """Four Claude sessions in one project directory."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    written = []
    for key, ident, _codex, start, stamp, matches in SESSIONS:
        path = project / f"{ident}.jsonl"
        body = _claude_records(key, start, stamp, matches)
        path.write_text("\n".join(json.dumps(r) for r in body) + "\n")
        written.append(path)
    return written


def codex(root: Path) -> list[Path]:
    """Four Codex rollouts, all filed under the recorded start's own date."""
    written = []
    for key, _claude, ident, start, stamp, matches in SESSIONS:
        directory = root / "sessions" / start[:4] / start[5:7] / start[8:10]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"rollout-{start[:10]}T00-00-00-{ident}.jsonl"
        body = _codex_records(ident, key, start, stamp, matches)
        path.write_text("\n".join(json.dumps(r) for r in body) + "\n")
        written.append(path)
    return written
