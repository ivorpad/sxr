"""Private JSON skill maps, atomically replaced and refreshed after directory changes."""

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from sxr.skills_catalog import absolute, default_roots, scan, stamp, unchanged


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
        or data.get("version") != 1
        or not isinstance(data.get("roots"), list)
        or not isinstance(data.get("watched"), dict)
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
    if not all(isinstance(root, str) and os.path.isabs(root) for root in data["roots"]):
        raise ValueError("invalid skill roots")
    for name, value in data["watched"].items():
        if not os.path.isabs(name) or (
            value is not None
            and (
                not isinstance(value, list)
                or len(value) != 5
                or not all(isinstance(part, int) for part in value)
            )
        ):
            raise ValueError("invalid skill snapshot")
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


def load(roots=None, force=False, defaults=False):
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
        and previous["roots"] == chosen
        and not previous["errors"]
        and unchanged(previous["watched"])
    ):
        return path, previous
    if not os.environ.get("SXR_NO_CACHE"):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    excluded = {str(map_path().parent.resolve())}
    data = scan(chosen, custom, excluded)
    if not unchanged(data["watched"]):
        data = scan(chosen, custom, excluded)
        if not unchanged(data["watched"]):
            data["errors"].append("skill directories changed during indexing; retry")
    if not os.environ.get("SXR_NO_CACHE"):
        write(path, data)
    return path, data
