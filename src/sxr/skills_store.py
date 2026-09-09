"""Private discovery snapshots, atomically replaced by explicit indexing."""

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from sxr.skills_catalog import absolute, default_roots, scan, stamp
from sxr.skills_content import hashed


def map_path(roots=None):
    """Keep the default map beside sxr's caches; transient root scopes have separate maps."""
    root = os.environ.get("SXR_CACHE_DIR")
    cache = (
        Path(root).expanduser()
        if root
        else Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / "sxr"
    )
    if roots is None:
        return cache / "skills.json"
    import hashlib

    key = hashlib.sha256(json.dumps(roots).encode()).hexdigest()[:24]
    return cache / "skills" / f"{key}.json"


@lru_cache(maxsize=16)
def _read(path, signature):
    data = json.loads(Path(path).read_text())
    if (
        not isinstance(data, dict)
        or data.get("version") not in (1, 2, 3)
        or not isinstance(data.get("roots"), list)
        or not isinstance(data.get("skills"), list)
        or not isinstance(data.get("errors"), list)
        or not isinstance(data.get("coverage"), list)
        or not isinstance(data.get("custom"), bool)
    ):
        raise ValueError("invalid skill map")
    for record in data["skills"]:
        if not all(isinstance(record.get(key), str) for key in ("name", "path")):
            raise ValueError("invalid skill record")
        if not isinstance(record.get("aliases"), list):
            raise ValueError("invalid skill aliases")
        if not all(isinstance(alias, str) for alias in record["aliases"]):
            raise ValueError("invalid skill alias")
        if data["version"] == 3:
            digest = record.get("sha256")
            signature = record.get("signature")
            if "sha256" not in record or "signature" not in record:
                raise ValueError("missing skill content hash")
            if digest is None and signature is not None:
                raise ValueError("invalid unhashed skill signature")
            if digest is not None and (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or not isinstance(signature, list)
                or len(signature) != 6
                or not all(isinstance(value, int) for value in signature)
            ):
                raise ValueError("invalid skill content hash")
    if not all(isinstance(root, str) and os.path.isabs(root) for root in data["roots"]):
        raise ValueError("invalid skill roots")
    if data["version"] >= 2 and not isinstance(data.get("indexed_at"), str):
        raise ValueError("invalid discovery timestamp")
    if not all(isinstance(error, str) for error in data["errors"]):
        raise ValueError("invalid skill errors")
    return data


def read(path):
    """Reuse a parsed map only while the file identity and timestamps are unchanged."""
    signature = stamp(path)
    if signature is None:
        return None
    try:
        return _read(str(path), tuple(signature))
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def write(path, data):
    """Publish a complete owner-only JSON document without exposing partial writes."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".skills-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, ensure_ascii=True, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load(roots=None, force=False, defaults=False, progress=None):
    """Remember roots only with --index; a scoped lookup never changes the default map."""
    explicit = list(dict.fromkeys(map(absolute, roots))) if roots else None
    path = map_path(explicit if explicit and not force else None)
    previous = read(path)
    custom = bool(explicit) or bool(previous and previous["custom"] and not defaults)
    chosen = explicit or (previous["roots"] if custom else default_roots())
    if (
        not force
        and not os.environ.get("SXR_NO_CACHE")
        and previous
        and previous["version"] >= 2
        and previous["roots"] == chosen
    ):
        if previous["version"] == 3:
            return path, previous
        data = hashed(previous)
        write(path, data)
        return path, data
    if not os.environ.get("SXR_NO_CACHE"):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    excluded = {str(map_path().parent.resolve())}
    data = scan(chosen, custom, excluded, progress)
    reusable = previous["skills"] if previous and not os.environ.get("SXR_NO_CACHE") else ()
    data = hashed(data, reusable)
    if not os.environ.get("SXR_NO_CACHE"):
        write(path, data)
    return path, data
