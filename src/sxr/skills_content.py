"""Hash instruction files and group identical contents without discarding locations."""

import errno
import hashlib
import os
import stat
from pathlib import Path


def _signature(info):
    return [
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
    ]


def signature(path):
    """Identify a regular file and detect edits, replacements, and permission changes."""
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise OSError(errno.EINVAL, "SKILL.md is not a regular file", path)
    return _signature(info)


def _digest(path):
    # Nonblocking open also makes a concurrent replacement with a FIFO safe.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise OSError(errno.EINVAL, "SKILL.md is not a regular file", path)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = _signature(os.fstat(stream.fileno()))
    if _signature(before) != after or signature(path) != after:
        raise OSError(errno.EAGAIN, "SKILL.md changed while hashing; rerun --index", path)
    return dict(sha256=digest, signature=after)


def identify(record, previous=None):
    """Reuse unchanged hashes; retry files edited or hydrated while being read."""
    path = record["path"]
    current = signature(path)
    if previous and previous.get("sha256") and previous.get("signature") == current:
        return dict(record, sha256=previous["sha256"], signature=current)
    for attempt in range(3):
        try:
            return dict(record, **_digest(path))
        except OSError as exc:
            if exc.errno != errno.EAGAIN or attempt == 2:
                raise


def hashed(data, previous=()):
    """Attach content hashes to a discovery snapshot, retaining unreadable locations."""
    known = {record["path"]: record for record in previous}
    records, errors = [], list(data["errors"])
    for record in data["skills"]:
        try:
            records.append(identify(record, known.get(record["path"])))
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as exc:
            records.append(dict(record, sha256=None, signature=None))
            errors.append(f"{record['path']}: {exc.strerror or exc}")
    return dict(data, version=3, skills=records, errors=errors)


def repair_missing(data):
    """Discard vanished unhashed entries and their saved errors from older indexes."""
    removed = set()
    for record in data["skills"]:
        if record["sha256"] is not None:
            continue
        try:
            os.stat(record["path"])
        except (FileNotFoundError, NotADirectoryError):
            removed.add(record["path"])
        except OSError:
            pass
    if not removed:
        return data
    prefixes = tuple(f"{path}: " for path in removed)
    return dict(
        data,
        skills=[record for record in data["skills"] if record["path"] not in removed],
        errors=[error for error in data["errors"] if not error.startswith(prefixes)],
    )


def current(record):
    """Validate a matched file and its aliases, rehashing it only after an edit."""
    updated = identify(record, record)
    if (
        updated["signature"] != record["signature"]
        and str(Path(record["path"]).resolve(strict=True)) != record["path"]
    ):
        raise OSError(errno.ESTALE, "indexed path now resolves elsewhere", record["path"])
    aliases = []
    for alias in record["aliases"]:
        try:
            if alias == record["path"] or str(Path(alias).resolve(strict=True)) == record["path"]:
                aliases.append(alias)
        except OSError:
            pass
    return dict(updated, aliases=aliases)


def public(record):
    """Keep filesystem signatures private to the map."""
    return {key: record[key] for key in ("name", "path", "aliases", "sha256")}


def groups(records, copies=False):
    """Group matched files by exact bytes, keeping every matching installation."""
    grouped = {}
    for record in records:
        key = record["sha256"] or record["path"]
        grouped.setdefault(key, []).append(public(record))
    result = []
    for locations in grouped.values():
        if copies:
            result.extend(dict(record, copies=len(locations)) for record in locations)
        else:
            result.append(dict(locations[0], copies=len(locations), locations=locations))
    return result, len(grouped)
