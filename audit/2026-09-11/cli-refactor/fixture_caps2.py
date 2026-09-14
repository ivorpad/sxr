"""Corpora for SXR-CLI-07: enough matches, long enough, across enough sessions.

Every clause of this slice is about which of three independent caps stopped the
output, so the fixture makes each one distinguishable:

* Three sessions, two with matches and one with none, so `-c` prunes a row and
  `--include-zero` has something to restore. A fourth pattern matches nothing
  anywhere, which is the all-zero table.
* Six matches per matching session, so a row cap of 2 or 5 is visibly different
  from no row cap.
* Match text well over the 200-character per-match cap, so complete text is
  recognisable by its tail marker rather than by counting.
* Total match text over a small `--budget`, so the character stop and the row cap
  can be told apart: one omits whole matches mid-list, the other cuts at a count.
* One Claude line carrying two matching content blocks, so per-transcript dedup
  and physical-line identity stay checkable here too.
"""

import json
from pathlib import Path

CWD = "/w"
NEEDLE = "resonance"
ABSENT = "quernstone"


def long_text(marker: str, n: int) -> str:
    """Match text whose every 20 characters name their own offset, plus a tail."""
    body = " ".join(f"{marker}{i:04d}aaaaaaaaaaaa" for i in range(40))
    return f"{NEEDLE} hit {n} {body} ENDOF{marker}{n}"


def claude(root: Path) -> list[Path]:
    """Two matching sessions and one without, plus a two-block physical line."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, ident in enumerate(("aaaa0007", "bbbb0007", "cccc0007")):
        matches = index < 2
        stamp = f"2026-09-1{index}T07:%02d:00Z"
        records = [
            dict(
                type="user",
                timestamp=stamp % 0,
                cwd=CWD,
                message=dict(role="user", content=f"open seven {index}"),
            )
        ]
        for n in range(6):
            text = long_text("m", n) if matches else f"unrelated body {n}"
            records.append(
                dict(
                    type="assistant",
                    timestamp=stamp % (n + 1),
                    cwd=CWD,
                    message=dict(role="assistant", content=[dict(type="text", text=text)]),
                )
            )
        if matches:
            # One physical line, two matching blocks: dedup must keep it one record.
            records.append(
                dict(
                    type="assistant",
                    timestamp=stamp % 9,
                    cwd=CWD,
                    message=dict(
                        role="assistant",
                        content=[
                            dict(type="text", text=long_text("p", 90)),
                            dict(type="text", text=long_text("p", 91)),
                        ],
                    ),
                )
            )
        path = project / f"{ident}-0000-4000-8000-00000000000{index}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        paths.append(path)
    return paths


def codex(root: Path) -> list[Path]:
    """The same shape on Codex, where one record is always one event."""
    paths = []
    for index, tag in enumerate(("a", "b", "c")):
        directory = root / "sessions" / "2026" / "09" / f"1{index}"
        directory.mkdir(parents=True, exist_ok=True)
        ident = f"0199990{index}-{tag}{tag}{tag}{tag}-7000-8000-00000000000{index}"
        stamp = f"2026-09-1{index}T07:%02d:00Z"
        records = [
            dict(
                timestamp=stamp % 0,
                type="session_meta",
                payload=dict(id=ident, cwd=CWD, timestamp=stamp % 0),
            ),
            dict(
                timestamp=stamp % 0,
                type="event_msg",
                payload=dict(type="user_message", message=f"open seven {index}"),
            ),
        ]
        for n in range(6):
            text = long_text("m", n) if index < 2 else f"unrelated body {n}"
            records.append(
                dict(
                    timestamp=stamp % (n + 1),
                    type="response_item",
                    payload=dict(
                        type="message",
                        role="assistant",
                        content=[dict(type="output_text", text=text)],
                    ),
                )
            )
        path = directory / f"rollout-2026-09-1{index}T07-00-00-{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        paths.append(path)
    return paths
