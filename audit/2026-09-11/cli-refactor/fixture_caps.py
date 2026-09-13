"""Long-text corpora for the SXR-CLI-21 compact-flag captures.

Every clause of this slice is about *how much* text a view prints, so the fixture
is built so that each cap is visible in the output length rather than inferred:

* Bodies are long enough that the 200-character default per-line cap and a
  smaller explicit one produce obviously different rows.
* A tool result carries a distinctive head and an equally distinctive tail, so a
  middle trim is recognisable and it is clear which end survived.
* One tool result is recorded as an error, so `errors` and `errors --compact` have
  something to print.
* The whole session is well over the 40,000-character default scan budget, so the
  default `show` path trims without being asked to, and `--budget 0` does not.

Text uses a repeating marker rather than filler so a truncated row still says
where it was cut.
"""

import json
from pathlib import Path

CWD = "/w"
NEEDLE = "threshold"


def body(marker: str, repeats: int) -> str:
    """Long text whose every 20 characters name their own position."""
    return " ".join(f"{marker}{n:04d}aaaaaaaaaaaa" for n in range(repeats))


HEAD_TAIL = f"HEADSTART {body('res', 60)} TAILFINISH"
LONG_TEXT = f"{NEEDLE} {body('txt', 60)}"
LONG_CMD = f"echo {body('cmd', 40)}"
BULK = [f"{NEEDLE} bulk {n} {body('blk', 120)}" for n in range(8)]


def claude(root: Path) -> Path:
    """One Claude session: long turns, a tool pair, an error pair, then bulk."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)

    def turn(role: str, content, stamp: str) -> dict:
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=stamp,
            cwd=CWD,
            message=dict(role=role, content=content),
        )

    stamp = "2026-09-10T07:%02d:00Z"
    records = [
        turn("user", f"open caps {LONG_TEXT}", stamp % 0),
        turn("assistant", [dict(type="text", text=LONG_TEXT)], stamp % 1),
        turn(
            "assistant",
            [dict(type="tool_use", id="ok1", name="Bash", input=dict(command=LONG_CMD))],
            stamp % 2,
        ),
        turn("user", [dict(type="tool_result", tool_use_id="ok1", content=HEAD_TAIL)], stamp % 3),
        turn(
            "assistant",
            [
                dict(
                    type="tool_use",
                    id="bad1",
                    name="Bash",
                    input=dict(command=f"{LONG_CMD} --fail"),
                )
            ],
            stamp % 4,
        ),
        turn(
            "user",
            [dict(type="tool_result", tool_use_id="bad1", content=HEAD_TAIL, is_error=True)],
            stamp % 5,
        ),
    ]
    records += [
        turn("assistant", [dict(type="text", text=text)], stamp % (6 + n))
        for n, text in enumerate(BULK)
    ]
    path = project / "cccccc21-0000-4000-8000-00000000021c.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def codex(root: Path) -> Path:
    """The same coverage on Codex shapes, one event per record."""
    directory = root / "sessions" / "2026" / "09" / "10"
    directory.mkdir(parents=True, exist_ok=True)
    ident = "01999921-cccc-7000-8000-00000000021c"
    stamp = "2026-09-10T07:%02d:00Z"

    def said(text: str, when: str) -> dict:
        payload = dict(
            type="message", role="assistant", content=[dict(type="output_text", text=text)]
        )
        return dict(timestamp=when, type="response_item", payload=payload)

    def command(call: str, output: str, code: int, when: str) -> dict:
        return dict(
            timestamp=when,
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=f"call-{code}",
                    call_id=f"call-{code}",
                    command=["bash", "-lc", call],
                    aggregated_output=output,
                    exit_code=code,
                ),
            ),
        )

    records = [
        dict(
            timestamp=stamp % 0,
            type="session_meta",
            payload=dict(id=ident, cwd=CWD, timestamp=stamp % 0),
        ),
        # A Codex human turn is event_msg/user_message; that record is the title.
        dict(
            timestamp=stamp % 0,
            type="event_msg",
            payload=dict(type="user_message", message=f"open caps {LONG_TEXT}"),
        ),
        said(LONG_TEXT, stamp % 1),
        command(LONG_CMD, HEAD_TAIL, 0, stamp % 2),
        command(f"{LONG_CMD} --fail", HEAD_TAIL, 1, stamp % 4),
    ]
    records += [said(text, stamp % (6 + n)) for n, text in enumerate(BULK)]
    path = directory / f"rollout-2026-09-10T07-00-00-{ident}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path
