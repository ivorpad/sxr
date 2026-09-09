"""Disposable byte positions and canonical deltas, without transcript text copies."""

import json
import os

from sxr.index_records import signature
from sxr.model import Event
from sxr.views_read import _selected

FIELDS = ("ts", "role", "kind", "text", "tool", "is_error", "tag")


def schema(db):
    """Keep read snapshots separate from the trigram index's file versions."""
    with db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS read_files (id INTEGER PRIMARY KEY, "
            "path TEXT, provider TEXT, stamp TEXT, format INTEGER, total INTEGER, "
            "header TEXT, UNIQUE(path,provider))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS read_events (file INTEGER, ordinal INTEGER, "
            "seq INTEGER, part INTEGER, offset INTEGER, length INTEGER, kind TEXT, "
            "is_error INTEGER, tag TEXT, patch TEXT, PRIMARY KEY(file,ordinal))"
        )


def _record(provider, seq, record):
    """Decode one physical record using the authoritative provider converter."""
    if hasattr(provider, "_record_events"):
        events = provider._record_events(seq, record)
    else:
        events = [provider._record_event(seq, record)]
    for event in events:
        event.raw["line"] = record
    return events


def _patch(before, after):
    """Store only fields altered by whole-session canonicalization."""
    changed = {
        key: getattr(after, key) for key in FIELDS if getattr(before, key) != getattr(after, key)
    }
    changed["raw"] = {
        k: v
        for k, v in after.raw.items()
        if k != "line" and (k not in before.raw or before.raw[k] != v)
    }
    changed["removed"] = [key for key in before.raw if key not in after.raw]
    return json.dumps(changed, ensure_ascii=True, separators=(",", ":"))


def _positions(path):
    """Frame bytes with the same universal newline boundaries as text parsing."""
    positions = {}
    offset = 0
    # TextIOWrapper recognizes LF, CRLF and standalone CR. Preserve that contract.
    with path.open("rb") as stream:
        for raw in stream:
            for line in raw.splitlines(keepends=True):
                positions[len(positions) + 1] = (offset, len(line))
                offset += len(line)
    return positions


def save_events(db, ref, provider, events, stamp, version, header):
    """Atomically replace positions only when parsing and framing saw one source version."""
    positions = _positions(ref.path)
    rows = []
    previous = None
    for ordinal, event in enumerate(events):
        if event.seq != previous:
            baseline = _record(provider, event.seq, event.raw["line"])
            previous, part = event.seq, 0
        offset, length = positions[event.seq]
        rows.append(
            (
                ordinal,
                event.seq,
                part,
                offset,
                length,
                event.kind,
                event.is_error,
                event.tag,
                _patch(baseline[part], event),
            )
        )
        part += 1
    if signature(ref.path.stat()) != stamp:
        return
    with db:
        db.execute(
            "INSERT INTO read_files(path,provider) VALUES (?,?) ON CONFLICT DO NOTHING",
            (str(ref.path), ref.provider),
        )
        identity = db.execute(
            "SELECT id FROM read_files WHERE path=? AND provider=?", (str(ref.path), ref.provider)
        ).fetchone()[0]
        db.execute("DELETE FROM read_events WHERE file=?", (identity,))
        db.executemany(
            "INSERT INTO read_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            ((identity, *row) for row in rows),
        )
        db.execute(
            "UPDATE read_files SET stamp=?,format=?,total=?,header=? WHERE id=?",
            (json.dumps(stamp), version, len(events), json.dumps(header), identity),
        )


def select_rows(db, identity, opts):
    """Reuse the view's selection rules over lightweight event metadata."""
    rows = db.execute(
        "SELECT ordinal,seq,kind,is_error,tag FROM read_events WHERE file=? ORDER BY ordinal",
        (identity,),
    )
    stubs = [
        Event(
            r["seq"],
            "",
            "",
            r["kind"],
            is_error=bool(r["is_error"]),
            tag=r["tag"],
            raw={"ordinal": r["ordinal"]},
        )
        for r in rows
    ]
    selected, _zoom = _selected(stubs, opts)
    # Individual indexed lookups avoid SQLite's bound-parameter limit for --type.
    return [
        db.execute(
            "SELECT * FROM read_events WHERE file=? AND ordinal=?", (identity, e.raw["ordinal"])
        ).fetchone()
        for e in selected
    ]


def load_events(path, provider, rows):
    """Seek source records and replay annotations; verify the opened inode as well."""
    events = []
    previous = None
    with path.open("rb") as stream:
        stamp = signature(os.fstat(stream.fileno()))
        for row in rows:
            if row["seq"] != previous:
                stream.seek(row["offset"])
                raw = stream.read(row["length"])
                record = json.loads(raw.decode("utf-8", errors="replace"))
                baseline = _record(provider, row["seq"], record)
                previous = row["seq"]
            event = baseline[row["part"]]
            patch = json.loads(row["patch"])
            event.raw.update(patch.pop("raw"))
            for key in patch.pop("removed"):
                event.raw.pop(key, None)
            for key, value in patch.items():
                if key not in FIELDS:
                    raise ValueError("unknown cached event field")
                setattr(event, key, value)
            events.append(event)
        if stamp != signature(os.fstat(stream.fileno())) or stamp != signature(path.stat()):
            raise ValueError("transcript changed while seeking")
    return events
