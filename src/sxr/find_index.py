"""Ranked event passages with source coordinates, maintained per transcript."""

import hashlib
import json
import sqlite3
import sys
import zlib

from sxr.index_records import signature
from sxr.providers import claude_code, codex

FORMAT = 4


def schema(db):
    """Share the private database so clear and secret cleaning remove every cache."""
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS find_config (version INTEGER)")
        version = db.execute("SELECT version FROM find_config").fetchone()
        if version and version[0] != FORMAT:
            raise sqlite3.DatabaseError("ranked index format changed; run sxr index --clear")
        if not version:
            db.execute("INSERT INTO find_config VALUES (?)", (FORMAT,))
        db.execute(
            "CREATE TABLE IF NOT EXISTS find_files (id INTEGER PRIMARY KEY, path TEXT UNIQUE, "
            "stamp TEXT, format INTEGER, title TEXT, digest TEXT)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS passages (id INTEGER PRIMARY KEY, file INTEGER, "
            "seq INTEGER, part INTEGER, start INTEGER, kind TEXT, role TEXT, "
            "tool TEXT, outcome TEXT)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS passages_file ON passages(file)")
        db.execute("CREATE TABLE IF NOT EXISTS find_text (id INTEGER PRIMARY KEY, text BLOB)")
        db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS find_terms USING fts5("
            "text, content='', contentless_delete=1, tokenize='unicode61')"
        )
        if not version:
            db.execute("INSERT INTO find_terms(find_terms, rank) VALUES('secure-delete', 1)")


def _delete(db, identity):
    db.execute(
        "DELETE FROM find_terms WHERE rowid IN (SELECT id FROM passages WHERE file=?)", (identity,)
    )
    db.execute(
        "DELETE FROM find_text WHERE id IN (SELECT id FROM passages WHERE file=?)", (identity,)
    )
    db.execute("DELETE FROM passages WHERE file=?", (identity,))


def _passages(events):
    """Index whole events so tokens and phrases cannot straddle artificial boundaries."""
    previous = None
    part = 0
    for event in events:
        part = part + 1 if previous == event.seq else 0
        previous = event.seq
        if not event.text or event.kind.startswith("duplicate."):
            continue
        yield (event.seq, part, 0, event.kind, event.role, event.tool, event.tag, event.text)


def refresh(db, refs):
    """Parse changed transcripts once; reject concurrent changes instead of serving stale hits."""
    schema(db)
    cached = {r["path"]: r for r in db.execute("SELECT * FROM find_files")}
    identities, errors = {}, []
    updated = 0
    for ref in refs:
        name = str(ref.path)
        try:
            stamp = signature(ref.path.stat())
        except OSError as exc:
            errors.append(f"{ref.path}: {exc}")
            continue
        if tuple(ref.extra["stamp"]) != stamp:
            errors.append(f"{ref.path}: file changed after discovery; retry")
            continue
        old = cached.get(name)
        if old and old["format"] == FORMAT and tuple(json.loads(old["stamp"])) == stamp:
            identities[old["id"]] = ref
            continue
        if updated == 0:
            print("# refreshing ranked session index", file=sys.stderr, flush=True)
        updated += 1
        if updated % 25 == 0:
            print(f"# refreshing session {updated}", file=sys.stderr, flush=True)
        provider = codex if ref.provider == "codex" else claude_code
        try:
            events = provider.parse(ref.path)
            digest = hashlib.sha256(ref.path.read_bytes()).hexdigest()
            rows = list(_passages(events))
            title = next(
                (
                    e.text[:160]
                    for e in events
                    if e.role == "user" and e.kind in ("text", "user_message") and e.text
                ),
                "",
            )
            if signature(ref.path.stat()) != stamp or tuple(ref.extra["stamp"]) != stamp:
                raise ValueError("file changed while indexing; retry")
            with db:
                db.execute("UPDATE find_files SET path=path WHERE path=?", (name,))
                latest = db.execute("SELECT * FROM find_files WHERE path=?", (name,)).fetchone()
                if (dict(latest) if latest else None) != (dict(old) if old else None):
                    raise ValueError("index changed in another process; retry")
                db.execute(
                    "INSERT INTO find_files(path) VALUES (?) ON CONFLICT DO NOTHING", (name,)
                )
                identity = db.execute("SELECT id FROM find_files WHERE path=?", (name,)).fetchone()[
                    0
                ]
                _delete(db, identity)
                for row in rows:
                    text = row[-1]
                    passage = db.execute(
                        "INSERT INTO passages(file,seq,part,start,kind,role,tool,outcome) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (identity, *row[:-1]),
                    ).lastrowid
                    db.execute(
                        "INSERT INTO find_text(id,text) VALUES (?,?)",
                        (passage, zlib.compress(text.encode("utf-8", errors="surrogatepass"), 1)),
                    )
                    db.execute(
                        "INSERT INTO find_terms(rowid,text) VALUES (?,?)",
                        (passage, text.encode("utf-8", errors="replace").decode("utf-8")),
                    )
                db.execute(
                    "UPDATE find_files SET stamp=?,format=?,title=?,digest=? WHERE id=?",
                    (json.dumps(stamp), FORMAT, json.dumps(title), digest, identity),
                )
            identities[identity] = ref
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append(f"{ref.path}: {exc}")
    return identities, errors
