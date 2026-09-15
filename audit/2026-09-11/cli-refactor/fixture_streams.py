"""Corpora for SXR-CLI-24: enough of everything to make a stream split visible.

The slice is about which stream each line goes to, so the fixture has to make every
kind of line appear at once:

* Four sessions, so `-n 1` omits three and any command with a row allowance has
  something to report. Four is also enough for `list`'s `+N more` footer.
* Tool calls, one of them failing, so `tools` and `errors` have rows and `cmds`
  has an outcome to record.
* A `Skill` call with an input, because that footer is uncapped today.
* Long text, so trim notices fire and can be checked for their stream.
* One Claude physical line with two content blocks, so dedup stays checkable while
  records move between streams.
"""

import json
from pathlib import Path

CWD = "/w"
NEEDLE = "cadence"
LONG = " ".join(f"t{i:04d}bbbbbbbbbbbb" for i in range(40))


def _claude_records(index: int) -> list:
    """One session's records: prompts, tools, a failure, a Skill, long text."""
    stamp = f"2026-09-1{index}T08:%02d:00Z"
    records = [
        dict(
            type="user",
            timestamp=stamp % 0,
            cwd=CWD,
            message=dict(role="user", content=f"please {NEEDLE} step {index}"),
        ),
        dict(
            type="assistant",
            timestamp=stamp % 1,
            cwd=CWD,
            message=dict(
                role="assistant",
                content=[
                    dict(
                        type="tool_use",
                        id=f"t{index}a",
                        name="Bash",
                        input=dict(command=f"git status --short {index}"),
                    )
                ],
            ),
        ),
        dict(
            type="user",
            timestamp=stamp % 2,
            cwd=CWD,
            message=dict(
                role="user",
                content=[dict(type="tool_result", tool_use_id=f"t{index}a", content="clean")],
            ),
        ),
        dict(
            type="assistant",
            timestamp=stamp % 3,
            cwd=CWD,
            message=dict(
                role="assistant",
                content=[
                    dict(
                        type="tool_use",
                        id=f"t{index}b",
                        name="Read",
                        input=dict(file_path=f"/w/missing{index}.txt"),
                    )
                ],
            ),
        ),
        dict(
            type="user",
            timestamp=stamp % 4,
            cwd=CWD,
            message=dict(
                role="user",
                content=[
                    dict(
                        type="tool_result",
                        tool_use_id=f"t{index}b",
                        is_error=True,
                        content=f"ENOENT: no such file /w/missing{index}.txt {LONG}",
                    )
                ],
            ),
        ),
        dict(
            type="assistant",
            timestamp=stamp % 5,
            cwd=CWD,
            message=dict(
                role="assistant",
                content=[
                    dict(
                        type="tool_use",
                        id=f"t{index}c",
                        name="Skill",
                        input=dict(skill=f"skill-{index}"),
                    )
                ],
            ),
        ),
        # One physical line, two blocks: dedup must keep it a single record.
        dict(
            type="assistant",
            timestamp=stamp % 6,
            cwd=CWD,
            message=dict(
                role="assistant",
                content=[
                    dict(type="text", text=f"{NEEDLE} first block {LONG}"),
                    dict(type="text", text=f"{NEEDLE} second block {LONG}"),
                ],
            ),
        ),
    ]
    return records


def claude(root: Path) -> list[Path]:
    """Four Claude sessions in one project directory."""
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(4):
        ident = f"{'abcd'[index] * 4}0024-0000-4000-8000-00000000000{index}"
        path = project / f"{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in _claude_records(index)) + "\n")
        paths.append(path)
    return paths


def codex(root: Path) -> list[Path]:
    """The same four shapes on Codex, where one record is always one event."""
    paths = []
    for index in range(4):
        directory = root / "sessions" / "2026" / "09" / f"1{index}"
        directory.mkdir(parents=True, exist_ok=True)
        tag = "abcd"[index] * 4
        ident = f"0199240{index}-{tag}-7000-8000-00000000000{index}"
        stamp = f"2026-09-1{index}T08:%02d:00Z"
        records = [
            dict(
                timestamp=stamp % 0,
                type="session_meta",
                payload=dict(id=ident, cwd=CWD, timestamp=stamp % 0),
            ),
            dict(
                timestamp=stamp % 0,
                type="event_msg",
                payload=dict(type="user_message", message=f"please {NEEDLE} step {index}"),
            ),
            dict(
                timestamp=stamp % 1,
                type="response_item",
                payload=dict(
                    type="function_call",
                    name="shell",
                    call_id=f"c{index}a",
                    arguments=json.dumps(dict(command=["bash", "-lc", f"git status {index}"])),
                ),
            ),
            dict(
                timestamp=stamp % 2,
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id=f"c{index}a",
                    output=json.dumps(dict(output="clean", metadata=dict(exit_code=0))),
                ),
            ),
            dict(
                timestamp=stamp % 3,
                type="response_item",
                payload=dict(
                    type="function_call",
                    name="shell",
                    call_id=f"c{index}b",
                    arguments=json.dumps(dict(command=["bash", "-lc", f"cat missing{index}"])),
                ),
            ),
            dict(
                timestamp=stamp % 4,
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id=f"c{index}b",
                    output=json.dumps(
                        dict(output=f"ENOENT missing{index} {LONG}", metadata=dict(exit_code=1))
                    ),
                ),
            ),
            dict(
                timestamp=stamp % 5,
                type="response_item",
                payload=dict(
                    type="message",
                    role="assistant",
                    content=[dict(type="output_text", text=f"{NEEDLE} first block {LONG}")],
                ),
            ),
        ]
        path = directory / f"rollout-2026-09-1{index}T08-00-00-{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        paths.append(path)
    return paths
