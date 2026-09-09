"""Ranked session search orchestration shared by CLI entry points."""

import json
import os
import sqlite3
import sys
import zlib
from pathlib import Path

from sxr.catalog import inventory
from sxr.discovery import normalize_path, project_paths
from sxr.file_selection import selected as select_file
from sxr.find_index import refresh
from sxr.find_query import clues, search
from sxr.handles import fail, window
from sxr.index_records import signature
from sxr.index_store import connect
from sxr.providers import claude_code, codex
from sxr.util import one_line


def _roots(ctx, use_codex, use_claude):
    root = ctx.obj or {}
    use_codex = use_codex or root.get("codex", False)
    use_claude = use_claude or root.get("claude", False)
    if use_codex and use_claude:
        fail("--claude and --codex are mutually exclusive; find defaults to both")
    options = ctx.meta.get("discovery", {})
    if use_codex and (options.get("claude_roots") or options.get("include_agents")):
        fail("--claude-root and --include-agents apply to Claude sessions")
    if use_claude and options.get("archives"):
        fail("--archives requires Codex")
    roots = []
    if not use_codex:
        profiles = options.get("claude_roots") or [claude_code.projects_dir().parent]
        for profile in profiles:
            directory = normalize_path(profile) / "projects"
            if (
                directory.exists()
                or options.get("claude_roots")
                or use_claude
                or os.environ.get("CLAUDE_CONFIG_DIR")
            ):
                roots.append((directory, "claude"))
    if not use_claude:
        store = normalize_path(codex.sessions_root())
        if store.exists() or use_codex or os.environ.get("CODEX_HOME"):
            roots.append((store, "codex"))
        if options.get("archives") or (store.parent / "archived_sessions").exists():
            roots.append((store.parent / "archived_sessions", "codex"))
    if not roots:
        fail("no Claude or Codex session stores found; select --claude-root or CODEX_HOME")
    return list(dict.fromkeys(roots))


def _scope(refs, ctx, path, all_projects, since, before):
    root = ctx.obj or {}
    options = ctx.meta.get("discovery", {})
    if not all_projects and not options.get("file"):
        targets = [
            str(p)
            for p in project_paths(
                str(path or root.get("path") or Path.cwd()), options.get("worktrees", False)
            )
        ]
        kept = []
        for r in refs:
            legacy = (
                next(
                    (
                        p
                        for p in targets
                        if claude_code.flatten_cwd(p) == r.extra.get("project_key")
                    ),
                    "",
                )
                if not r.cwd and r.provider == "claude"
                else ""
            )
            if legacy:
                r.cwd = legacy
            if any(
                r.cwd == p
                or (options.get("recursive") and r.cwd.startswith(p.rstrip(os.sep) + os.sep))
                for p in targets
            ):
                kept.append(r)
        refs = kept
    refs.sort(key=lambda r: (r.started, r.id), reverse=True)
    return window(refs, since or root.get("since"), before or root.get("before"))


def _display(value):
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(value.encode(encoding, errors="backslashreplace").decode(encoding))


def _render(results, coverage, errors, total, json_out, show_coverage=False):
    if show_coverage:
        for scope in coverage:
            print(
                f"# {scope['provider']} {scope['root']}: {scope['searched']} files searched",
                file=sys.stderr,
            )
    if json_out:
        print(
            json.dumps(
                dict(
                    results=results,
                    total=total,
                    complete=not errors,
                    coverage=coverage,
                    errors=errors,
                ),
                ensure_ascii=True,
            )
        )
        return
    for rank, result in enumerate(results, 1):
        print(f"{rank}. {result['provider']} {result['id']}  {result['started'][:10]}")
        _display(f"   {result['cwd']}  {one_line(result['title'], 120)}")
        for item in result["evidence"]:
            outcome = f" -> {item['outcome']}" if item["outcome"] else ""
            print(f"   #{item['seq']} {item['role']} {item['tool'] or item['kind']}{outcome}")
            _display("   " + item["text"].replace("\n", "\n   "))
        print(f"   {result['follow_up']}")
    print(
        f"# {len(results)} of {total} matching sessions; "
        f"{sum(r['searched'] for r in coverage)} files searched"
    )
    for error in errors:
        print(f"# incomplete: {error}", file=sys.stderr)


def execute(
    ctx,
    query=None,
    all_projects=False,
    any_term=False,
    index=False,
    use_codex=False,
    use_claude=False,
    path=None,
    json_out=False,
    limit=None,
    since=None,
    before=None,
):
    """Return session evidence with current scope and a completeness indicator."""
    if not query and not index:
        fail("provide search clues, or --index to prepare searches")
    terms = clues(query) if query else []
    root = ctx.obj or {}
    json_out = json_out or root.get("json", False)
    limit = limit if limit is not None else root.get("limit")
    if limit is not None and limit < 0:
        fail("--limit must be zero or greater")
    if os.environ.get("SXR_NO_CACHE"):
        fail("find requires its ranked index; unset SXR_NO_CACHE or use grep for direct reads")
    try:
        with connect() as index_db:
            db = index_db.db
            db.execute("PRAGMA cache_size=-32768")
            db.execute("PRAGMA temp_store=MEMORY")
            if ctx.meta.get("discovery", {}).get("file"):
                select_file(
                    ctx,
                    use_codex or root.get("codex", False),
                    use_claude or root.get("claude", False),
                    path or root.get("path"),
                )
                ref = ctx.meta["file_ref"]
                ref.extra.update(stamp=signature(ref.path.stat()), root=str(ref.path))
                refs, coverage, errors = (
                    [ref],
                    [dict(root=str(ref.path), provider=ref.provider, files=1)],
                    [],
                )
            else:
                refs, coverage, errors = inventory(db, _roots(ctx, use_codex, use_claude))
            refs = _scope(refs, ctx, path, all_projects, since, before)
            selected, problems = refresh(db, refs)
            errors.extend(problems)
            for scope in coverage:
                scope["searched"] = sum(r.extra["root"] == scope["root"] for r in selected.values())
            results, total = (
                search(db, selected, terms, 5 if limit is None else limit, any_term)
                if terms
                else ([], 0)
            )
            changed = set()
            for r in refs:
                try:
                    if signature(r.path.stat()) == tuple(r.extra["stamp"]):
                        continue
                except OSError:
                    pass
                changed.add(str(r.path))
            if changed:
                errors.append(f"{len(changed)} transcripts changed during search; retry")
                results = [r for r in results if r["path"] not in changed]
            _render(
                results,
                coverage,
                errors,
                total,
                json_out,
                ctx.meta.get("discovery", {}).get("coverage"),
            )
            if index and not query:
                print(f"# prepared {len(selected)} sessions", file=sys.stderr)
            return 2 if errors else (0 if results or index else 1)
    except (OSError, sqlite3.Error, zlib.error, UnicodeError) as exc:
        fail(
            f"cannot search ranked index: {exc}; run sxr index --clear or use grep for direct reads"
        )
