"""Claude profile and child transcript discovery."""

from functools import partial
from pathlib import Path

from sxr.discovery import deduplicate, matches_path, normalize_path, project_paths
from sxr.model import SessionRef


def _metadata(path: Path, *, child: bool = False) -> SessionRef:
    """Read the first cwd and timestamp needed for scope and stable handles."""
    from sxr.providers.claude_code import _iter_records, _summarize

    ref = SessionRef("claude", path.stem, path, size_bytes=path.stat().st_size)
    for _seq, record in _iter_records(path):
        ref.cwd = ref.cwd or str(record.get("cwd") or "")
        ref.started = ref.started or record.get("timestamp", "")
        if ref.started and (ref.cwd or child):
            break
    ref._summary_loader = partial(_summarize, path, ref=ref)
    return ref


def _children(parent: SessionRef, root: Path) -> list[SessionRef]:
    """Parent-qualified IDs prevent agent filenames colliding across sessions."""
    children = []
    for path in sorted((parent.path.parent / parent.id).glob("**/*.jsonl")):
        if "subagents" not in path.relative_to(parent.path.parent / parent.id).parts:
            continue
        try:
            child = _metadata(path, child=True)
        except OSError:
            continue
        child.id = f"{parent.id}/{path.stem}"
        child.cwd = parent.cwd
        child.kind = "agent"
        child.extra.update(parent_id=parent.id, root=str(root))
        children.append(child)
    return children


def list_sessions(
    cwd: str,
    *,
    roots: list[Path] | None = None,
    recursive: bool = False,
    worktrees: bool = False,
    include_agents: bool = False,
    lazy: bool = False,
) -> list[SessionRef]:
    """Search only selected profiles; descendants and agents require flags."""
    from sxr.providers.claude_code import flatten_cwd, projects_dir

    targets = project_paths(cwd, worktrees)
    profiles = roots if roots else [projects_dir().parent]
    refs = []
    for profile in dict.fromkeys(normalize_path(root) for root in profiles):
        projects = profile / "projects"
        try:
            candidates = sorted(projects.glob("*/*.jsonl"))
        except OSError:
            continue
        for path in candidates:
            try:
                ref = _metadata(path)
            except OSError:
                continue
            recorded = ref.cwd
            # Very old records can lack cwd. Their encoded directory still
            # identifies an exact project, but cannot prove descendant scope.
            legacy_exact = not recorded and path.parent.name in {
                flatten_cwd(str(target)) for target in targets
            }
            if not legacy_exact and not matches_path(recorded, targets, recursive):
                continue
            ref.cwd = recorded or str(targets[0])
            ref.extra["root"] = str(profile)
            refs.append(ref)
            if include_agents:
                refs.extend(_children(ref, profile))
    unique = deduplicate(refs)
    unique.sort(key=lambda ref: (ref.started, ref.id), reverse=True)
    if not lazy:
        for ref in unique:
            ref.summarize()
    return unique
