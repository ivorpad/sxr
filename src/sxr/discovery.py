"""Path scope and duplicate-copy handling shared by transcript providers."""

from pathlib import Path

from sxr.model import SessionRef


def normalize_path(value: str | Path) -> Path:
    """Use physical absolute paths for both requested and recorded cwd values."""
    return Path(value).expanduser().resolve()


def project_paths(cwd: str, worktrees: bool = False) -> list[Path]:
    """Exact cwd plus registered sibling worktrees when explicitly requested."""
    target = normalize_path(cwd)
    if not worktrees:
        return [target]
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(target), "worktree", "list", "--porcelain", "-z"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [target]
    paths = [target]
    if result.returncode == 0:
        for field in result.stdout.decode("utf-8", errors="replace").split("\0"):
            if field.startswith("worktree "):
                path = normalize_path(field.removeprefix("worktree "))
                if path not in paths:
                    paths.append(path)
    return paths


def matches_path(recorded_cwd: str, targets: list[Path], recursive: bool = False) -> bool:
    """Match whole path components, never /repo-other as a child of /repo."""
    if not recorded_cwd:
        return False
    path = normalize_path(recorded_cwd)
    return any(path == target or (recursive and path.is_relative_to(target)) for target in targets)


def deduplicate(refs: list[SessionRef]) -> list[SessionRef]:
    """Collapse byte-identical copies, keeping every source path as provenance.

    Differing files with the same identity remain separate for the resolver
    to reject, rather than silently picking a profile or an archive copy.
    """
    import hashlib

    counts: dict[tuple[str, str], int] = {}
    for ref in refs:
        key = (ref.provider, ref.id)
        counts[key] = counts.get(key, 0) + 1
    copies: dict[tuple[str, str, str], SessionRef] = {}
    unique = []
    for ref in refs:
        sources = ref.extra.setdefault("provenance", [str(ref.path)])
        key = (ref.provider, ref.id)
        if counts[key] > 1:
            digest = hashlib.sha256(ref.path.read_bytes()).hexdigest()
            fingerprint = (*key, digest)
            if fingerprint in copies:
                provenance = copies[fingerprint].extra["provenance"]
                provenance.extend(path for path in sources if path not in provenance)
                continue
            copies[fingerprint] = ref
        unique.append(ref)
    return unique
