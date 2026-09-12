"""Physical transcript selection and bounded reads of recent activity."""

import json
from dataclasses import replace
from pathlib import Path

CHUNK = 65536


def _reverse_lines(stream):
    """Read from the end in blocks, holding at most one record plus a block."""
    position = stream.seek(0, 2)
    pending = []
    while position:
        size = min(position, CHUNK)
        position -= size
        stream.seek(position)
        lines = stream.read(size).split(b"\n")
        if len(lines) == 1:
            pending.append(lines[0])
            continue
        yield b"".join([lines[-1], *reversed(pending)])
        yield from reversed(lines[1:-1])
        pending = [lines[0]]
    if pending:
        yield b"".join(reversed(pending))


def last_timestamp(path: Path) -> str:
    """Read the last recorded timestamp without building a transcript event list."""
    with path.open("rb") as stream:
        for raw in _reverse_lines(stream):
            try:
                record = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if (
                isinstance(record, dict)
                and isinstance(record.get("timestamp"), str)
                and record["timestamp"]
            ):
                return record["timestamp"]
    return ""


def physical_paths(ref, session_paths) -> list[Path]:
    """Include selected duplicate copies and Claude children; explicit files stay exact."""
    if ref.extra.get("explicit_file"):
        return [ref.path]
    paths = set()
    for source in dict.fromkeys([str(ref.path), *ref.extra.get("provenance", [])]):
        copy = replace(ref, path=Path(source))
        paths.update(session_paths(copy))
        if ref.provider == "claude" and ref.kind != "agent":
            directory = copy.path.parent / ref.id
            paths.update(
                p
                for p in directory.rglob("*.jsonl")
                if "subagents" in p.relative_to(directory).parts[:-1]
            )
    return sorted({path.resolve(strict=True) for path in paths})
