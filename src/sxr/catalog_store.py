"""Typed metadata and a fresh, request-local inventory for ranked retrieval."""

from sxr.providers.claude_code import flatten_cwd

STAMP = "dev,ino,size,mtime,ctime"


def schema(db):
    """Migrate cached discovery metadata without rereading unchanged transcripts."""
    fresh = not db.execute("PRAGMA table_info(catalog_fast)").fetchone()
    with db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS catalog_fast (path TEXT PRIMARY KEY, provider TEXT, "
            "identity TEXT,cwd TEXT,started TEXT,kind TEXT,parent_path TEXT,project_key TEXT, "
            "dev INTEGER,ino INTEGER,size INTEGER,mtime INTEGER,ctime INTEGER)"
        )
        columns = {r["name"] for r in db.execute("PRAGMA table_info(catalog)")} if fresh else set()
        if "metadata" in columns:
            fields = [
                "'$.provider'",
                "'$.id'",
                "'$.cwd'",
                "'$.started'",
                "'$.kind'",
                "'$.extra.parent_path'",
                "'$.extra.project_key'",
            ]
            values = [f"coalesce(json_extract(metadata,{key}),'')" for key in fields]
            values += [f"json_extract(stamp,'$[{i}]')" for i in range(5)]
            db.execute(
                "INSERT INTO catalog_fast SELECT path,"
                + ",".join(values)
                + " FROM catalog WHERE format=2"
            )
        db.execute(
            "CREATE TEMP TABLE IF NOT EXISTS catalog_live (path TEXT PRIMARY KEY,root TEXT, "
            "provider TEXT,dev INTEGER,ino INTEGER,size INTEGER,mtime INTEGER,ctime INTEGER)"
        )
        db.execute("DELETE FROM catalog_live")


def changes(db):
    """Select only files whose discovery metadata needs to be reread."""
    mismatch = " OR ".join(f"c.{field}!=l.{field}" for field in STAMP.split(","))
    return db.execute(
        "SELECT l.* FROM catalog_live l LEFT JOIN catalog_fast c ON c.path=l.path "
        "WHERE c.path IS NULL OR " + mismatch
    ).fetchall()


def records(db, targets=None, recursive=False):
    """Apply project scope before constructing references, including live parent metadata."""
    query = (
        "WITH refs AS (SELECT c.path,c.provider,c.identity,c.started,c.kind,"
        "c.parent_path,c.project_key,l.root,l.dev,l.ino,l.size,l.mtime,l.ctime,"
        "coalesce(nullif(p.cwd,''),c.cwd) AS cwd "
        "FROM catalog_live l JOIN catalog_fast c ON c.path=l.path "
        "LEFT JOIN catalog_live parent ON parent.path=c.parent_path "
        "LEFT JOIN catalog_fast p ON p.path=parent.path) SELECT * FROM refs"
    )
    conditions, parameters = [], []
    for target in targets or []:
        conditions.append("cwd=? OR (cwd='' AND provider='claude' AND project_key=?)")
        parameters.extend((target, flatten_cwd(target)))
        if recursive:
            prefix = target.rstrip("/") + "/"
            conditions.append("substr(cwd,1,?)=?")
            parameters.extend((len(prefix), prefix))
    if conditions:
        query += " WHERE " + " OR ".join(conditions)
    return db.execute(query, parameters)
