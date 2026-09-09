"""A fresh file inventory with reusable session metadata for ranked retrieval."""

import os
from pathlib import Path

from sxr import catalog_store
from sxr.claude_discovery import _metadata
from sxr.discovery import normalize_path
from sxr.file_selection import _parent
from sxr.file_stamp import signature
from sxr.model import SessionRef
from sxr.providers import codex


def _files(root, provider, errors):
    """Enumerate the store on every request so new files cannot disappear in a cache."""
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    yield from _files(entry.path, provider, errors)
                elif (
                    entry.name.endswith(".jsonl")
                    and entry.is_file()
                    and (provider == "claude" or entry.name.startswith("rollout-"))
                ):
                    yield entry.path, signature(entry.stat()), entry.is_symlink()
    except OSError as exc:
        errors.append(f"{root}: {exc.strerror or exc}")


def _reference(path, provider):
    """Read only discovery metadata; empty or torn Codex files wait for their header."""
    if provider == "codex":
        first = codex._first_record(path)
        return codex._metadata(path, first) if first else None
    parent = _parent(path)
    ref = _metadata(path, child=parent is not None)
    if parent:
        ref.id = f"{parent.name}/{path.stem}"
        ref.kind = "agent"
        ref.extra["parent_id"] = parent.name
        ref.extra["parent_path"] = str(parent.with_suffix(".jsonl"))
    ref.extra["project_key"] = (parent.parent if parent else path.parent).name
    return ref


def _update(db, errors):
    updates = []
    for row in catalog_store.changes(db):
        path = Path(row["path"])
        stamp = tuple(row[field] for field in catalog_store.STAMP.split(","))
        try:
            ref = _reference(path, row["provider"])
            if ref is None:
                raise ValueError("missing session metadata; retry after the header is written")
            if signature(path.stat()) != stamp:
                raise ValueError("file changed while reading metadata; retry")
            cwd = str(normalize_path(ref.cwd)) if ref.cwd else ""
            updates.append(
                (
                    str(path),
                    ref.provider,
                    ref.id,
                    cwd,
                    ref.started,
                    ref.kind,
                    ref.extra.get("parent_path", ""),
                    ref.extra.get("project_key", ""),
                    *stamp,
                )
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(f"{path}: {exc}")
            db.execute("DELETE FROM catalog_live WHERE path=?", (str(path),))
    db.executemany(
        "INSERT OR REPLACE INTO catalog_fast VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", updates
    )


def inventory(db, roots, targets=None, recursive=False):
    """Return scoped references after checking every source file for metadata changes."""
    catalog_store.schema(db)
    errors, seen, live, coverage = [], set(), [], []
    for root, provider in roots:
        root = str(normalize_path(root))
        prefix = root.rstrip(os.sep) + os.sep
        for name, stamp, symlink in _files(root, provider, errors):
            if provider == "claude":
                parts = name[len(prefix) :].split(os.sep)
                if len(parts) != 2 and "subagents" not in parts[2:-1]:
                    continue
            if symlink:
                name = str(Path(name).resolve())
            if name in seen:
                continue
            seen.add(name)
            live.append((name, root, provider, *stamp))
        coverage.append(dict(root=root, provider=provider, files=0))
    with db:
        db.executemany("INSERT INTO catalog_live VALUES (?,?,?,?,?,?,?,?)", live)
        _update(db, errors)
    counts = dict(db.execute("SELECT root,count(*) FROM catalog_live GROUP BY root"))
    for scope in coverage:
        scope["files"] = counts.get(scope["root"], 0)
    refs = []
    for row in catalog_store.records(db, targets, recursive):
        extra = dict(
            root=row["root"],
            navigation=["--file", row["path"]],
            stamp=tuple(row[field] for field in catalog_store.STAMP.split(",")),
            parent_path=row["parent_path"],
            project_key=row["project_key"],
        )
        refs.append(
            SessionRef(
                provider=row["provider"],
                id=row["identity"],
                path=Path(row["path"]),
                cwd=row["cwd"],
                started=row["started"],
                kind=row["kind"],
                extra=extra,
            )
        )
    return refs, coverage, errors
