"""Claude profile and child transcript discovery."""

from pathlib import Path

from sxr.discovery import deduplicate, matches_path, normalize_path, project_paths
from sxr.model import SessionRef


def _recorded_cwd(path: Path) -> str:
    """Read only until cwd appears, before deciding to parse a whole session."""
    from sxr.providers.claude_code import _iter_records

    try:
        for _seq, record in _iter_records(path):
            if record.get("cwd"):
                return str(record["cwd"])
    except OSError:
        pass
    return ""


def _children(parent: SessionRef, root: Path) -> list[SessionRef]:
    """Parent-qualified IDs prevent agent filenames colliding across sessions."""
    from sxr.providers.claude_code import _summarize

    children = []
    for path in sorted((parent.path.parent / parent.id).glob("**/*.jsonl")):
        if "subagents" not in path.relative_to(parent.path.parent / parent.id).parts:
            continue
        try:
            child = _summarize(path)
        except OSError:
            continue
        child.id = f"{parent.id}/{path.stem}"
        child.cwd = child.cwd or parent.cwd
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
) -> list[SessionRef]:
    """Search only selected profiles; descendants and agents require flags."""
    from sxr.providers.claude_code import _summarize, flatten_cwd, projects_dir

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
            recorded = _recorded_cwd(path)
            # Very old records can lack cwd. Their encoded directory still
            # identifies an exact project, but cannot prove descendant scope.
            legacy_exact = not recorded and path.parent.name in {
                flatten_cwd(str(target)) for target in targets
            }
            if not legacy_exact and not matches_path(recorded, targets, recursive):
                continue
            try:
                ref = _summarize(path)
            except OSError:
                continue
            ref.cwd = recorded or str(targets[0])
            ref.extra["root"] = str(profile)
            refs.append(ref)
            if include_agents:
                refs.extend(_children(ref, profile))
    unique = deduplicate(refs)
    unique.sort(key=lambda ref: (ref.started, ref.id), reverse=True)
    return unique
