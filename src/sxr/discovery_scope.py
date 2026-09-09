"""CLI discovery options, coverage diagnostics, and repeatable navigation."""

import os
import sys
from pathlib import Path

from sxr.discovery import normalize_path
from sxr.handles import fail
from sxr.providers import claude_code, codex


def _roots(provider, options: dict) -> list[Path]:
    if provider is codex:
        roots = [normalize_path(codex.sessions_root())]
        if options.get("archives"):
            roots.append(roots[0].parent / "archived_sessions")
        return roots
    profiles = options.get("claude_roots") or [claude_code.projects_dir().parent]
    return list(dict.fromkeys(normalize_path(root) / "projects" for root in profiles))


def _coverage(refs: list, roots: list[Path], cwd: str, options: dict) -> None:
    copies = sum(max(0, len(ref.extra.get("provenance", [])) - 1) for ref in refs)
    children = sum(
        bool(ref.extra.get("parent_id") or ref.extra.get("parent_thread_id")) for ref in refs
    )
    archived = sum(bool(ref.extra.get("archived")) for ref in refs)
    scope = "descendants" if options.get("recursive") else "exact cwd"
    if options.get("worktrees"):
        scope += " + Git worktrees"
    print(
        f"# coverage: {cwd} ({scope}); {len(refs)} sessions, {children} agents, "
        f"{archived} archived, {copies} duplicate copies",
        file=sys.stderr,
    )
    for root in roots:
        available = root.is_dir() and os.access(root, os.R_OK | os.X_OK)
        state = "searched" if available else "unavailable"
        sources = sum(
            1
            for ref in refs
            for source in ref.extra.get("provenance", [str(ref.path)])
            if Path(source).is_relative_to(root)
        )
        print(f"# {state}: {root} ({sources} sources in path scope)", file=sys.stderr)
    if options.get("coverage"):
        for ref in refs:
            sources = ref.extra.get("provenance", [])
            if len(sources) > 1:
                print(f"# copies of {ref.id}: {', '.join(sources)}", file=sys.stderr)


def discover(ctx, provider, cwd: str) -> list:
    """Discover once; diagnostics describe roots even when nothing matched."""
    if ctx.meta.get("file_ref") is not None:
        ref = ctx.meta["file_ref"]
        if ctx.meta.get("discovery", {}).get("coverage"):
            print(f"# coverage: explicit file {ref.path}; 1 source", file=sys.stderr)
        return [ref]
    options = ctx.meta.get("discovery", {})
    if provider is codex and (options.get("claude_roots") or options.get("include_agents")):
        fail("--claude-root and --include-agents apply to Claude sessions")
    if provider is claude_code and options.get("archives"):
        fail("--archives requires --codex")
    roots = _roots(provider, options)
    kwargs = {key: True for key in ("recursive", "worktrees") if options.get(key)}
    if provider is codex:
        if options.get("archives"):
            kwargs["include_archives"] = True
    else:
        kwargs["roots"] = [root.parent for root in roots]
        kwargs["include_agents"] = options.get("include_agents", False)
    refs = provider.list_sessions(cwd, lazy=True, **kwargs)
    if options.get("coverage") or len(roots) > 1 or not refs:
        _coverage(refs, roots, cwd, options)
    navigation = ["--codex" if provider is codex else "--claude", "--path", cwd]
    for key, flag in (
        ("recursive", "--recursive"),
        ("worktrees", "--worktrees"),
        ("include_agents", "--include-agents"),
        ("archives", "--archives"),
    ):
        if options.get(key):
            navigation.append(flag)
    if provider is claude_code:
        for root in roots:
            navigation.extend(["--claude-root", str(root.parent)])
    prefixes: dict[str, int] = {}
    for ref in refs:
        prefixes[ref.short_id] = prefixes.get(ref.short_id, 0) + 1
    for ref in refs:
        if prefixes[ref.short_id] > 1:
            ref.extra["display_id"] = ref.id
        ref.extra["navigation"] = navigation.copy()
        if provider is codex:
            ref.extra["navigation_env"] = {"CODEX_HOME": str(roots[0].parent)}
    return refs
