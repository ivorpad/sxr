"""Private, disposable SQLite trigram index with atomic per-file updates."""

import json
import os
import sqlite3
import zlib
from contextlib import closing, contextmanager
from pathlib import Path

from sxr.file_stamp import signature

# Bump when normalization or the index schema changes.
FORMAT = 2


def index_path() -> Path:
    """Local index location, independent of transcript provider/profile roots."""
    root = os.environ.get("SXR_CACHE_DIR")
    if root:
        return Path(root).expanduser() / "search.sqlite3"
    cache = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    return cache / "sxr" / "search.sqlite3"


def _schema(db) -> None:
    """Create a contentless index; require deletion support or let callers fall back."""
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, FORMAT):
        raise sqlite3.DatabaseError("unsupported sxr index format; run sxr index --clear")
    if version:
        return
    with db:
        db.execute(
            "CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT, provider TEXT, "
            "stamp TEXT, digest TEXT, offset INTEGER, lines INTEGER, UNIQUE(path, provider))"
        )
        db.execute(
            "CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "file INTEGER, first_seq INTEGER, last_seq INTEGER, tail INTEGER, body BLOB)"
        )
        db.execute("CREATE INDEX by_file ON documents(file)")
        db.execute(
            "CREATE VIRTUAL TABLE terms USING fts5(body, content='', "
            "contentless_delete=1, detail=none, tokenize='trigram case_sensitive 1')"
        )
        db.execute("INSERT INTO terms(terms, rank) VALUES('secure-delete', 1)")
        db.execute(f"PRAGMA user_version={FORMAT}")


@contextmanager
def connect():
    """Open an owner-only cache; lock, filesystem and SQLite errors remain recoverable."""
    path = index_path()
    if os.name != "posix":
        raise OSError("indexing requires POSIX file metadata; direct reads remain available")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(path, timeout=0.1)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        _schema(db)
        yield Index(db)


class Index:
    """Maintain file snapshots; the transcript parser remains the result authority."""

    def __init__(self, db):
        self.db = db

    def _delete_documents(self, identity: int, tail_only: bool = False) -> None:
        clause = "file=?" + (" AND tail=1" if tail_only else "")
        self.db.execute(
            f"DELETE FROM terms WHERE rowid IN (SELECT id FROM documents WHERE {clause})",
            (identity,),
        )
        self.db.execute(f"DELETE FROM documents WHERE {clause}", (identity,))

    def refresh(self, path: Path, provider: str) -> tuple[int, tuple[int, ...]] | None:
        """Reuse an unchanged file, or atomically replace its changed index documents."""
        from sxr.index_records import read_update

        row = self.db.execute(
            "SELECT * FROM files WHERE path=? AND provider=?", (str(path), provider)
        ).fetchone()
        previous = dict(row) if row else None
        stamp = signature(path.stat())
        if previous and tuple(json.loads(previous["stamp"])) == stamp:
            return previous["id"], stamp
        update = read_update(path, provider, previous)
        if update is None:
            return None
        with self.db:
            # Acquire the writer lock before checking for another process's update.
            self.db.execute(
                "UPDATE files SET path=path WHERE path=? AND provider=?", (str(path), provider)
            )
            latest = self.db.execute(
                "SELECT * FROM files WHERE path=? AND provider=?", (str(path), provider)
            ).fetchone()
            if (dict(latest) if latest else None) != previous:
                return None
            if previous:
                identity = previous["id"]
                self._delete_documents(identity, update.append)
            else:
                identity = self.db.execute(
                    "INSERT INTO files(path,provider) VALUES (?,?)", (str(path), provider)
                ).lastrowid
            for text, first, last, tail in update.documents:
                document = self.db.execute(
                    "INSERT INTO documents(file,first_seq,last_seq,tail,body) VALUES (?,?,?,?,?)",
                    (identity, first, last, tail, zlib.compress(text.encode("utf-8"), 1)),
                ).lastrowid
                self.db.execute("INSERT INTO terms(rowid,body) VALUES (?,?)", (document, text))
            self.db.execute(
                "UPDATE files SET stamp=?,digest=?,offset=?,lines=? WHERE id=?",
                (json.dumps(update.stamp), update.digest, update.offset, update.lines, identity),
            )
        return identity, update.stamp

    def matches(self, literal: str, eligible: set[int] | None = None) -> set[int]:
        """Intersect sampled trigrams, then confirm the substring in compressed text."""
        from sxr.index_records import fold

        text = fold(literal)
        count = len(text) - 2
        grams = dict.fromkeys(text[i : i + 3] for i in range(0, count, max(1, (count + 11) // 12)))
        query = " AND ".join('"' + gram.replace('"', '""') + '"' for gram in grams)
        needle = text.encode("utf-8")
        matches = set()
        for row in self.db.execute(
            "SELECT id,file FROM documents WHERE id IN "
            "(SELECT rowid FROM terms WHERE terms MATCH ?)",
            (query,),
        ):
            if row["file"] in matches or (eligible is not None and row["file"] not in eligible):
                continue
            body = self.db.execute(
                "SELECT body FROM documents WHERE id=?", (row["id"],)
            ).fetchone()[0]
            try:
                if needle in zlib.decompress(body):
                    matches.add(row["file"])
            except (zlib.error, TypeError) as exc:
                raise sqlite3.DatabaseError("invalid cached text; run sxr index --clear") from exc
        return matches

    def prune(self) -> None:
        """Remove entries whose source file has been deleted or moved."""
        for row in self.db.execute("SELECT id,path FROM files").fetchall():
            if not Path(row["path"]).exists():
                with self.db:
                    self._delete_documents(row["id"])
                    self.db.execute("DELETE FROM files WHERE id=?", (row["id"],))


def clear() -> None:
    """Discard derived search data, including when the database is corrupt."""
    path = index_path()
    if not path.exists():
        return
    # Take SQLite's exclusive lock when possible; never remove an actively used index.
    with closing(sqlite3.connect(path, timeout=0.1)) as db:
        try:
            db.execute("BEGIN EXCLUSIVE")
        except sqlite3.DatabaseError as exc:
            if getattr(exc, "sqlite_errorcode", None) not in (
                sqlite3.SQLITE_CORRUPT,
                sqlite3.SQLITE_NOTADB,
            ):
                raise
        path.unlink()
        for suffix in ("-journal", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
