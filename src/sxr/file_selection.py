"""Resolve a named transcript without discovering unrelated sessions."""

import json
from functools import partial
from pathlib import Path

from sxr.discovery import matches_path, normalize_path, project_paths
from sxr.handles import fail
from sxr.providers import claude_code, codex


def _provider(path: Path):
    """Recognize recorded provider fields, never a filename alone."""
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("type") == "session_meta":
                return codex, record
            if record.get("type") in (
                "user",
                "assistant",
                "system",
                "progress",
                "queue-operation",
                "attachment",
                "ai-title",
                "custom-title",
                "file-history-snapshot",
                "summary",
            ):
                return claude_code, record
    fail(f"cannot identify transcript provider: {path}")


def _parent(path: Path) -> Path | None:
    """Locate the owning session directory, including deeply nested child files."""
    projects = next((p for p in path.parents if p.name == "projects"), None)
    if projects:
        parts = path.relative_to(projects).parts
        if len(parts) >= 4 and "subagents" in parts[2:-1]:
            return projects / parts[0] / parts[1]
        return None
    agents = next((p for p in path.parents if p.name == "subagents"), None)
    if agents:
        return next((p for p in agents.parents if p.with_suffix(".jsonl").is_file()), agents.parent)
    return None


def reference(value: Path):
    """Read identity and provenance, including parent-qualified Claude agents."""
    from sxr.claude_discovery import _metadata

    path = normalize_path(value)
    if not path.is_file():
        fail(f"not a transcript file: {path}")
    try:
        provider, record = _provider(path)
        if provider is codex:
            ref = codex._metadata(path, record)
            store = next(
                (p for p in path.parents if p.name in ("sessions", "archived_sessions")), None
            )
            titles = partial(codex.history_titles, store.parent) if store else dict
            ref._summary_loader = partial(codex._summarize, ref, titles)
            ref.extra["archived"] = "archived_sessions" in path.parts
        else:
            parent_dir = _parent(path)
            ref = _metadata(path, child=parent_dir is not None)
            if parent_dir is not None:
                parent_id = parent_dir.name
                parent = parent_dir.with_suffix(".jsonl")
                ref.id = f"{parent_id}/{path.stem}"
                ref.kind = "agent"
                ref.extra["parent_id"] = parent_id
                if parent.is_file():
                    ref.cwd = _metadata(parent).cwd or ref.cwd
        ref.extra.update(provenance=[str(path)], explicit_file=True)
        return provider, ref
    except OSError as exc:
        fail(f"cannot read transcript {path}: {exc}")


def selected(ctx, codex_flag: bool, claude_flag: bool, requested_path):
    """Validate explicit provider, project and profile constraints against the file."""
    options = ctx.meta.get("discovery", {})
    value = options.get("file")
    if not value:
        return None
    provider, ref = reference(value)
    if (codex_flag and provider is not codex) or (claude_flag and provider is not claude_code):
        fail(f"--file is a {ref.provider} transcript; provider flag conflicts")
    if requested_path and not matches_path(
        ref.cwd,
        project_paths(str(requested_path), options.get("worktrees", False)),
        options.get("recursive", False),
    ):
        fail(f"--file does not belong to the requested project: {requested_path}")
    profiles = options.get("claude_roots")
    if profiles and (
        provider is not claude_code
        or not any(ref.path.is_relative_to(normalize_path(p) / "projects") for p in profiles)
    ):
        fail("--file does not belong to the selected Claude profiles")
    if provider is claude_code and options.get("archives"):
        fail("--archives requires --codex")
    if provider is codex and options.get("include_agents"):
        fail("--include-agents applies to Claude sessions")
    ref.extra["navigation"] = ["--file", str(ref.path)]
    ctx.meta["file_ref"] = ref
    return provider, ref.cwd or str(ref.path.parent)
