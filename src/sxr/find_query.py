"""Rank session-level clue matches and return bounded, source-addressable evidence."""

import json
import shlex
import zlib

from sxr.handles import fail
from sxr.navigation import command


def clues(query):
    """Words are required clues; quoted phrases stay together and FTS syntax is escaped."""
    try:
        words = shlex.split(query)
    except ValueError as exc:
        fail(f"bad find query: {exc}")
    terms = list(dict.fromkeys(w for w in words if any(c.isalnum() for c in w)))
    if not terms:
        fail("find needs a word, identifier, or quoted phrase")
    if len(terms) > 12:
        fail("find accepts up to 12 clues; use a shorter query")
    return terms


def _excerpt(text, terms, cap=600):
    folded = text.casefold()
    positions = [folded.find(word.casefold()) for term in terms for word in term.split()]
    first = min((p for p in positions if p >= 0), default=0)
    start = max(0, first - 120)
    end = min(len(text), start + cap)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def search_paths(db, refs, terms, limit=0, any_term=False):
    """Find every matching source path without scoring passages or loading their text."""
    db.execute("CREATE TEMP TABLE IF NOT EXISTS find_scope (id INTEGER PRIMARY KEY)")
    db.execute("DELETE FROM find_scope")
    db.executemany("INSERT INTO find_scope VALUES (?)", ((identity,) for identity in refs))
    matched = set() if any_term else set(refs)
    for term in sorted(terms, key=len, reverse=True):
        expression = '"' + term.replace('"', '""') + '"'
        found = {
            row[0]
            for row in db.execute(
                "SELECT DISTINCT p.file FROM find_terms "
                "JOIN passages p ON p.id=find_terms.rowid "
                "JOIN find_scope s ON s.id=p.file WHERE find_terms MATCH ?",
                (expression,),
            )
        }
        if any_term:
            matched.update(found)
        else:
            matched.intersection_update(found)
            if not matched:
                break
    paths = sorted(str(refs[identity].path) for identity in matched)
    return [{"path": path} for path in (paths[:limit] if limit else paths)], len(paths)


def search(db, refs, terms, limit=5, any_term=False):
    """Require every clue somewhere in a session, then rank its strongest passages."""
    db.execute("CREATE TEMP TABLE IF NOT EXISTS find_scope (id INTEGER PRIMARY KEY)")
    db.execute("DELETE FROM find_scope")
    db.executemany("INSERT INTO find_scope VALUES (?)", ((identity,) for identity in refs))
    eligible = set(refs)
    if not any_term and len(terms) > 1:
        # Determine which sessions contain every clue before ranking individual passages.
        for term in sorted(terms, key=len, reverse=True):
            expression = '"' + term.replace('"', '""') + '"'
            found = {
                row[0]
                for row in db.execute(
                    "SELECT DISTINCT p.file FROM find_terms "
                    "JOIN passages p ON p.id=find_terms.rowid "
                    "JOIN find_scope s ON s.id=p.file WHERE find_terms MATCH ?",
                    (expression,),
                )
            }
            eligible.intersection_update(found)
            if not eligible:
                return [], 0
        db.execute("DELETE FROM find_scope")
        db.executemany("INSERT INTO find_scope VALUES (?)", ((i,) for i in eligible))
    by_file = {}
    for term in terms:
        expression = '"' + term.replace('"', '""') + '"'
        matches = db.execute(
            "WITH scores AS MATERIALIZED ("
            "SELECT p.id,p.file,bm25(find_terms) * CASE "
            "WHEN p.role='user' AND p.kind IN ('text','user_message') THEN 3.0 "
            "WHEN p.kind IN ('tool','text','agent_message') THEN 2.0 ELSE 1.0 END AS score "
            "FROM find_terms JOIN passages p ON p.id=find_terms.rowid "
            "JOIN find_scope s ON s.id=p.file WHERE find_terms MATCH ?) "
            "SELECT file,id,min(score) AS score FROM scores GROUP BY file",
            (expression,),
        )
        for row in matches:
            by_file.setdefault(row["file"], {})[term] = (row["score"], row["id"])
    candidates = [
        (identity, hits)
        for identity, hits in by_file.items()
        if any_term or len(hits) == len(terms)
    ]
    candidates.sort(
        key=lambda item: (
            -len(item[1]),
            sum(v[0] for v in item[1].values()),
            str(refs[item[0]].path),
        )
    )
    info_by_id = {
        row["id"]: row
        for row in db.execute(
            "SELECT f.id,f.title,f.digest FROM find_files f JOIN find_scope s ON s.id=f.id"
        )
    }
    seen, output = {}, []
    for identity, hits in candidates:
        ref = refs[identity]
        info = info_by_id[identity]
        key = (ref.provider, ref.id, info["digest"])
        if key in seen:
            if seen[key] is not None:
                seen[key]["sources"].append(str(ref.path))
            continue
        seen[key] = None
        if limit and len(output) >= limit:
            continue
        evidence = []
        for passage in dict.fromkeys(v[1] for v in sorted(hits.values())):
            row = db.execute(
                "SELECT p.*,b.text FROM passages p JOIN find_text b ON b.id=p.id WHERE p.id=?",
                (passage,),
            ).fetchone()
            evidence.append(
                dict(
                    seq=row["seq"],
                    part=row["part"],
                    kind=row["kind"],
                    role=row["role"],
                    tool=row["tool"],
                    outcome=row["outcome"],
                    text=_excerpt(
                        zlib.decompress(row["text"]).decode("utf-8", errors="surrogatepass"), terms
                    ),
                )
            )
            if len(evidence) == 3:
                break
        result = dict(
            provider=ref.provider,
            id=ref.id,
            path=str(ref.path),
            cwd=ref.cwd,
            started=ref.started,
            title=json.loads(info["title"]),
            matched=list(hits),
            sources=[str(ref.path)],
            evidence=evidence,
            follow_up=command(ref, "show", "--around", str(evidence[0]["seq"]), "--context", "3"),
        )
        seen[key] = result
        output.append(result)
    return output, len(seen)
