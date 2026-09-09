"""Discover SKILL.md paths and symlink aliases without reading skill instructions."""

import os
import stat
from pathlib import Path

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def absolute(path):
    """Expand a root without resolving away the alias the caller wants to see."""
    return os.path.abspath(os.path.expanduser(str(path)))


def default_roots():
    """Search common user skill directories and installed plugin caches, never all of HOME."""
    home = Path.home()
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    codex = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return list(
        dict.fromkeys(
            map(
                absolute,
                (
                    claude / "skills",
                    home / ".agents/skills",
                    codex / "skills",
                    home / ".cursor/skills",
                    config / "opencode/skills",
                    home / ".gemini/skills",
                    home / ".copilot/skills",
                    claude / "plugins/cache",
                    codex / "plugins/cache",
                ),
            )
        )
    )


def stamp(path):
    """Track directory membership, replacement, permissions, and symlink destinations."""
    try:
        info = os.stat(path)
        return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_mode]
    except OSError:
        return None


def unchanged(watched):
    """Check directory metadata rather than walking the tree again."""
    return all(stamp(path) == previous for path, previous in watched.items())


def _walk(path, ancestors, found, watched, errors, excluded):
    if os.path.realpath(path) in excluded:
        return
    before = stamp(path)
    watched[path] = before
    if before is None:
        errors.append(f"{path}: directory is missing or inaccessible")
        return
    identity = tuple(before[:2])
    if identity in ancestors:
        errors.append(f"{path}: symlink cycle skipped")
        return
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name == "SKILL.md" and entry.is_file():
                    physical = str(Path(entry.path).resolve(strict=True))
                    watched[entry.path] = stamp(entry.path)
                    watched[physical] = stamp(physical)
                    record = found.setdefault(
                        physical,
                        dict(
                            name=Path(physical).parent.name,
                            path=physical,
                            aliases=[],
                        ),
                    )
                    record["aliases"].append(entry.path)
                elif entry.name not in SKIP and entry.is_dir():
                    _walk(entry.path, ancestors | {identity}, found, watched, errors, excluded)
    except OSError as exc:
        errors.append(f"{path}: {exc.strerror or exc}")


def scan(roots, custom=False, excluded=()):
    """Merge physical files, retaining every discovered logical path and missing root."""
    watched, found, errors, coverage = {}, {}, [], []
    for root in roots:
        previous = stamp(root)
        watched[root] = previous
        present = previous is not None and stat.S_ISDIR(previous[-1])
        coverage.append(dict(root=root, present=present))
        if present:
            _walk(root, set(), found, watched, errors, excluded)
        elif custom:
            errors.append(f"{root}: directory is missing or inaccessible")
        else:
            try:
                os.stat(root)
            except (FileNotFoundError, NotADirectoryError):
                pass
            except OSError as exc:
                errors.append(f"{root}: {exc.strerror or exc}")
    records = sorted(found.values(), key=lambda item: (item["name"].casefold(), item["path"]))
    for record in records:
        record["aliases"] = sorted(set(record["aliases"]))
    return dict(
        version=1,
        custom=custom,
        roots=roots,
        watched=watched,
        skills=records,
        coverage=coverage,
        errors=errors,
    )


def matches(records, query, exact=False):
    """Match directory names or qualified path clues; exact names sort first."""
    clues = query.casefold().replace(":", " ").split()
    result = []
    for record in records:
        names = {record["name"].casefold()}
        names.update(Path(path).parent.name.casefold() for path in record["aliases"])
        exact_name = query.casefold() in names
        haystack = "\n".join((record["path"], *record["aliases"])).casefold()
        if (exact and exact_name) or (not exact and all(clue in haystack for clue in clues)):
            result.append((not exact_name, record))
    result.sort(key=lambda item: (item[0], item[1]["name"].casefold(), item[1]["path"]))
    return [record for _, record in result]
