"""Seek to cached event windows while retaining whole-session annotations."""

import json
import os
import sqlite3

from sxr.index_records import signature
from sxr.index_store import connect
from sxr.read_positions import load_events, save_events, schema, select_rows

FORMAT = 1


def _header(ref):
    """Only transcript-derived fields displayed by show belong in this cache."""
    return dict(started=ref.started, model=ref.model, gitBranch=ref.extra.get("gitBranch", ""))


def _restore(ref, header):
    ref.started = header["started"]
    ref.model = header["model"]
    ref.extra["gitBranch"] = header["gitBranch"]


def read_window(ref, provider, opts):
    """Return selected events and the original count; cache failures use the parser.

    The first zoom parses the whole file to resolve distant tool outcomes. Later
    zooms seek only selected records and apply their cached canonical changes.
    Any source mutation invalidates all annotations, including on earlier lines.
    """
    zoom = opts.around is not None or opts.range_ or opts.type_ or opts.tail is not None
    if os.environ.get("SXR_NO_CACHE") or not zoom or (opts.tail is not None and opts.tail < 0):
        events = ref.read(provider.parse)
        return events, len(events)
    events = None
    try:
        stamp = signature(ref.path.stat())
        with connect() as index:
            db = index.db
            schema(db)
            row = db.execute(
                "SELECT * FROM read_files WHERE path=? AND provider=?",
                (str(ref.path), ref.provider),
            ).fetchone()
            if row and row["format"] == FORMAT and tuple(json.loads(row["stamp"])) == stamp:
                count = db.execute(
                    "SELECT count(*) FROM read_events WHERE file=?", (row["id"],)
                ).fetchone()[0]
                if count == row["total"]:
                    selected = load_events(ref.path, provider, select_rows(db, row["id"], opts))
                    if signature(ref.path.stat()) == stamp:
                        _restore(ref, json.loads(row["header"]))
                        return selected, count
            events = ref.read(provider.parse)
            save_events(db, ref, provider, events, stamp, FORMAT, _header(ref))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        pass
    if events is None:
        events = ref.read(provider.parse)
    return events, len(events)
