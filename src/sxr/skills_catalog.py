"""Discover SKILL.md paths and symlink aliases without reading skill instructions."""

import os
import stat
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path


def absolute(path):
    """Expand a root without resolving away the alias the caller wants to see."""
    return os.path.abspath(os.path.expanduser(str(path)))


def default_roots():
    """Discover across HOME, also covering configured profiles outside it."""
    home = Path.home()
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    codex = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    roots = [absolute(home)]
    for directory in (claude, codex, config / "opencode"):
        candidate = absolute(directory)
        if not any(os.path.commonpath((root, candidate)) == root for root in roots):
            roots.append(candidate)
    return roots


def stamp(path):
    """Track directory membership, replacement, permissions, and symlink destinations."""
    try:
        info = os.stat(path)
        return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_mode]
    except OSError:
        return None


def _remember(entry, found):
    physical = str(Path(entry.path).resolve(strict=True))
    record = found.setdefault(
        physical, dict(name=Path(physical).parent.name, path=physical, aliases=set())
    )
    record["aliases"].add(entry.path)


def _walk(root, found, visited, aliases, errors, excluded, progress):
    stack = [(root, frozenset())]
    cycles, retries = 0, {}
    while stack:
        path, ancestors = stack.pop()
        try:
            info = os.stat(path)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as exc:
            errors.append(f"{path}: {exc.strerror or exc}")
            continue
        identity = info.st_dev, info.st_ino
        if identity in excluded:
            continue
        if identity in ancestors:
            cycles += 1
            continue
        if identity in visited:
            aliases.append((path, visited[identity]))
            continue
        visited[identity] = path
        if progress and len(visited) % 25000 == 0:
            progress(len(visited), len(found))
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.name == "SKILL.md" and entry.is_file():
                            _remember(entry, found)
                        elif entry.is_dir():
                            stack.append((entry.path, ancestors | {identity}))
                    except (FileNotFoundError, NotADirectoryError):
                        pass
                    except InterruptedError:
                        raise
                    except OSError as exc:
                        errors.append(f"{entry.path}: {exc.strerror or exc}")
        except (FileNotFoundError, NotADirectoryError):
            pass
        except InterruptedError as exc:
            retries[path] = retries.get(path, 0) + 1
            if retries[path] <= 3:
                visited.pop(identity)
                stack.append((path, ancestors))
            else:
                errors.append(f"{path}: {exc.strerror or exc}")
        except OSError as exc:
            errors.append(f"{path}: {exc.strerror or exc}")
    return cycles


def _expand_aliases(found, aliases):
    # Traverse each physical directory once, then recover its other logical paths.
    redirects = {}
    for alias, original in aliases:
        redirects.setdefault(original, []).append(alias)
    for record in found.values():
        pending = list(record["aliases"])
        while pending:
            path = pending.pop()
            for parent in Path(path).parents:
                prefix = str(parent)
                for alias in redirects.get(prefix, ()):
                    candidate = alias.rstrip(os.sep) + path[len(prefix.rstrip(os.sep)) :]
                    if candidate not in record["aliases"]:
                        record["aliases"].add(candidate)
                        pending.append(candidate)


def scan(roots, custom=False, excluded=(), progress=None):
    """Merge physical files, retaining every discovered logical path and missing root."""
    found, visited, aliases, errors, coverage = {}, {}, [], [], []
    cycles = 0
    excluded = {tuple(value[:2]) for path in excluded if (value := stamp(path))}
    for root in roots:
        previous = stamp(root)
        present = previous is not None and stat.S_ISDIR(previous[-1])
        coverage.append(dict(root=root, present=present))
        if present:
            cycles += _walk(root, found, visited, aliases, errors, excluded, progress)
        elif custom:
            errors.append(f"{root}: directory is missing or inaccessible")
        else:
            try:
                os.stat(root)
            except (FileNotFoundError, NotADirectoryError):
                pass
            except OSError as exc:
                errors.append(f"{root}: {exc.strerror or exc}")
    _expand_aliases(found, aliases)
    records = sorted(found.values(), key=lambda item: (item["name"].casefold(), item["path"]))
    for record in records:
        record["aliases"] = sorted(set(record["aliases"]))
    return dict(
        version=2,
        custom=custom,
        roots=roots,
        indexed_at=datetime.now(UTC).isoformat(),
        directories=len(visited),
        cycles_skipped=cycles,
        skills=records,
        coverage=coverage,
        errors=errors,
    )


@lru_cache(maxsize=32768)
def _terms(name, path, aliases):
    names = {name.casefold()}
    names.update(os.path.basename(os.path.dirname(alias)).casefold() for alias in aliases)
    return names, "\n".join((path, *aliases)).casefold()


def matches(records, query, exact=False):
    """Match directory names or qualified path clues; exact names sort first."""
    clues = query.casefold().replace(":", " ").split()
    result = []
    for record in records:
        names, haystack = _terms(record["name"], record["path"], tuple(record["aliases"]))
        exact_name = query.casefold() in names
        if (exact and exact_name) or (not exact and all(clue in haystack for clue in clues)):
            result.append((not exact_name, record))
    result.sort(
        key=lambda item: (
            item[0],
            item[1]["name"].casefold(),
            item[1]["path"].count(os.sep),
            item[1]["path"],
        )
    )
    return [record for _, record in result]
