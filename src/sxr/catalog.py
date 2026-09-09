"""A fresh file inventory with reusable session metadata for ranked retrieval."""

import json
import os
from dataclasses import asdict
from pathlib import Path

from sxr.claude_discovery import _metadata
from sxr.discovery import normalize_path
from sxr.file_selection import _parent
from sxr.index_records import signature
from sxr.model import SessionRef
from sxr.providers import codex

FORMAT = 2


def _schema(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS catalog (path TEXT PRIMARY KEY, stamp TEXT, "
        "format INTEGER, metadata TEXT)"
    )


def _files(root, provider, errors):
    """Enumerate the store on every request so new files cannot disappear in a cache."""
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    yield from _files(Path(entry.path), provider, errors)
                elif entry.name.endswith(".jsonl") and entry.is_file():
                    path = Path(entry.path)
                    # Roots below are traversed recursively; store filtering happens in inventory.
                    if provider == "claude" or entry.name.startswith("rollout-"):
                        yield path, signature(entry.stat()), entry.is_symlink()
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


def _encode(ref):
    ref._summary_loader = None
    data = asdict(ref)
    data.pop("_summary_loader")
    data["path"] = str(ref.path)
    return json.dumps(data, ensure_ascii=True)


def inventory(db, roots):
    """Return current references and explicit coverage, re-reading only changed headers."""
    _schema(db)
    cached = {row["path"]: row for row in db.execute("SELECT * FROM catalog")}
    refs, errors, seen = [], [], set()
    coverage = []
    updates = []
    for root, provider in roots:
        root = normalize_path(root)
        before = len(refs)
        for path, stamp, symlink in _files(root, provider, errors):
            if provider == "claude":
                parts = path.relative_to(root).parts
                if len(parts) != 2 and "subagents" not in parts[2:-1]:
                    continue
            if symlink:
                path = path.resolve()
            name = str(path)
            if name in seen:
                continue
            seen.add(name)
            old = cached.get(name)
            try:
                if old and old["format"] == FORMAT and tuple(json.loads(old["stamp"])) == stamp:
                    data = json.loads(old["metadata"])
                    data["path"] = Path(data["path"])
                    ref = SessionRef(**data)
                else:
                    ref = _reference(path, provider)
                    if ref is None:
                        raise ValueError(
                            "missing session metadata; retry after the header is written"
                        )
                    if signature(path.stat()) != stamp:
                        raise ValueError("file changed while reading metadata; retry")
                    ref.cwd = str(normalize_path(ref.cwd)) if ref.cwd else ""
                    updates.append((name, json.dumps(stamp), FORMAT, _encode(ref)))
                ref.extra.update(root=str(root), navigation=["--file", name], stamp=stamp)
                refs.append(ref)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(f"{path}: {exc}")
        coverage.append(dict(root=str(root), provider=provider, files=len(refs) - before))
    with db:
        db.executemany("INSERT OR REPLACE INTO catalog VALUES (?,?,?,?)", updates)
    by_path = {str(ref.path): ref for ref in refs}
    for ref in refs:
        parent = by_path.get(ref.extra.get("parent_path"))
        if parent:
            ref.cwd = parent.cwd or ref.cwd
    return refs, coverage, errors
