"""Incremental source reads for the search index; coordinates remain physical lines."""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from sxr.providers.claude_code import _record_events
from sxr.providers.codex_events import _record_event

CHUNK_CHARS = 262144
# Python's regex IGNORECASE also equates dotted/dotless I with ASCII i.
FOLD = str.maketrans({"İ": "i", "ı": "i", "\0": "\ufffd"})


def fold(text: str) -> str:
    """A case-insensitive candidate superset; the real regex checks final hits."""
    return text.translate(FOLD).casefold()


def signature(stat: os.stat_result) -> tuple[int, ...]:
    """Detect replacement, rewriting, truncation and metadata-preserving edits."""
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def record_text(seq: int, raw: bytes, provider: str) -> str:
    """Index pre-deduplication event text so later outcomes cannot introduce a miss."""
    try:
        record = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return ""
    events = [_record_event(seq, record)] if provider == "codex" else _record_events(seq, record)
    return fold("\n".join(event.text for event in events if event.text))


@dataclass
class Update:
    """A stable file snapshot and documents built from its changed suffix."""

    stamp: tuple[int, ...]
    digest: str
    offset: int
    lines: int
    append: bool
    documents: list[tuple[str, int, int, bool]]


def _prefix(stream, size: int):
    """Hash an old prefix before trusting an apparent append."""
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        chunk = stream.read(min(remaining, 1048576))
        if not chunk:
            break
        digest.update(chunk)
        remaining -= len(chunk)
    return digest


def _documents(stream, provider: str, offset: int, lines: int, digest, hashed: int):
    """Read new physical records; retain a separate, replaceable unfinished tail."""
    documents = []
    parts = []
    seen = set()
    chars = 0
    first = lines + 1
    stream.seek(offset)
    for seq, raw in enumerate(stream, lines + 1):
        start = stream.tell() - len(raw)
        digest.update(raw[max(0, hashed - start) :])
        text = record_text(seq, raw, provider)
        if text:
            key = hashlib.sha256(text.encode("utf-8")).digest()
            if key in seen:
                text = ""
            else:
                seen.add(key)
        complete = raw.endswith(b"\n")
        if not complete:
            if parts:
                documents.append(("\n".join(parts), first, seq - 1, False))
                parts = []
            if text:
                documents.append((text, seq, seq, True))
            break
        if text:
            parts.append(text)
            chars += len(text)
        offset, lines = stream.tell(), seq
        if chars >= CHUNK_CHARS:
            documents.append(("\n".join(parts), first, seq, False))
            parts, chars, first = [], 0, seq + 1
    if parts:
        documents.append(("\n".join(parts), first, lines, False))
    return documents, offset, lines


def read_update(path: Path, provider: str, previous: dict | None) -> Update | None:
    """Decode only an authenticated appended suffix; rebuild changed prefixes."""
    with path.open("rb") as stream:
        stamp = signature(os.fstat(stream.fileno()))
        append = False
        offset = lines = hashed = 0
        digest = hashlib.sha256()
        if previous:
            old = tuple(json.loads(previous["stamp"]))
            if stamp[:2] == old[:2] and stamp[2] > old[2]:
                digest = _prefix(stream, old[2])
                append = digest.hexdigest() == previous["digest"]
            if append:
                offset, lines, hashed = previous["offset"], previous["lines"], old[2]
            else:
                digest = hashlib.sha256()
        documents, offset, lines = _documents(stream, provider, offset, lines, digest, hashed)
        if stamp != signature(os.fstat(stream.fileno())) or stamp != signature(path.stat()):
            return None
    return Update(stamp, digest.hexdigest(), offset, lines, append, documents)
