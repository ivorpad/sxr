"""Optional indexed candidate discovery and the explicit index maintenance command."""

import os
import sqlite3
import sys
from typing import Annotated

import typer

from sxr import flags, views_grep, views_info
from sxr.grep_options import GrepOpts
from sxr.handles import fail
from sxr.index_records import fold, signature
from sxr.index_store import clear, connect, index_path


def _literal(pattern: str, fixed: bool) -> bool:
    """Use only literal substrings of three or more characters as index queries."""
    return (
        len(fold(pattern)) >= 3
        and "\0" not in pattern
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in pattern)
        and (fixed or not any(char in views_grep.METACHARS for char in pattern))
    )


def candidates(refs, pattern: str, fixed: bool):
    """Find possible matches; unsupported queries or cache failures use a direct scan."""
    if os.environ.get("SXR_NO_CACHE") or not _literal(pattern, fixed):
        return None
    try:
        with connect() as index:
            snapshots = {}
            fallback = set()
            for ref in refs:
                try:
                    snapshot = index.refresh(ref.path, ref.provider)
                except (OSError, ValueError, TypeError, AttributeError, UnicodeError):
                    snapshot = None
                if snapshot is None:
                    fallback.add(ref.path)
                else:
                    snapshots[ref.path] = snapshot
            matching = index.matches(pattern, {identity for identity, _ in snapshots.values()})
            for path, (identity, stamp) in snapshots.items():
                if identity in matching or signature(path.stat()) != stamp:
                    fallback.add(path)
            return fallback
    except (OSError, sqlite3.Error, UnicodeError):
        return None


def grep_view(pattern: str, refs, provider, opts: GrepOpts) -> int:
    """Keep the grep output contract while avoiding reads of indexed non-matches."""
    views_grep.compile_pattern(pattern, opts.fixed, opts.ignore_case)
    opts.candidates = candidates(refs, pattern, opts.fixed)
    return views_grep.grep_view(pattern, refs, provider.parse, opts)


def cmds_view(refs, provider, json_out: bool, limit: int | None, pattern: str | None) -> int:
    """Use the same candidate index for literal command searches."""
    selected = candidates(refs, pattern, False) if pattern else None

    def parse(path):
        return provider.parse(path) if selected is None or path in selected else []

    return views_info.cmds_view(refs, parse, json_out, limit, pattern)


def index_cmd(
    ctx: typer.Context,
    clear_: Annotated[
        bool, typer.Option("--clear", help="Remove the whole local search index")
    ] = False,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
) -> None:
    """Build or refresh the search index for a scope; --clear removes its cached data."""
    try:
        if clear_:
            clear()
            print(f"# cleared search index: {index_path()}")
            return
        provider, cwd, _, _ = flags.merge(ctx, use_codex, use_claude, path, False, None)
        refs = flags.sessions(ctx, provider, cwd, since, before)
        with connect() as index:
            index.prune()
            complete = 0
            for position, ref in enumerate(refs, 1):
                if index.refresh(ref.path, ref.provider) is not None:
                    complete += 1
                if position % 25 == 0 or position == len(refs):
                    print(f"# indexed {complete}/{len(refs)} sessions", file=sys.stderr, flush=True)
        print(f"# search index: {index_path()}")
        if complete != len(refs):
            fail("some sessions changed during indexing; searches will read those files directly")
    except (OSError, sqlite3.Error) as exc:
        fail(f"cannot update search index: {exc}; SXR_NO_CACHE=1 uses direct reads")
