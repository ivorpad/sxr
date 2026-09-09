"""Low-startup CLI for the common agent invocation, sxr find."""

import argparse
from pathlib import Path
from types import SimpleNamespace

from sxr.find_service import execute


def main(arguments):
    """Parse the find command without importing unrelated commands or Typer."""
    parser = argparse.ArgumentParser(
        prog="sxr find",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=80),
        description="Find sessions with source evidence across Claude and Codex. "
        "Use a few distinctive words or quoted phrases; default scope is cwd.",
    )
    parser.add_argument("query", nargs="?", help="Required words or quoted phrases")
    parser.add_argument("--all-projects", action="store_true", help="Search every project")
    parser.add_argument("--any", dest="any_term", action="store_true", help="Match any clue")
    parser.add_argument("--index", action="store_true", help="Prepare the ranked search index")
    parser.add_argument("--codex", dest="use_codex", action="store_true", help="Only Codex")
    parser.add_argument("--claude", dest="use_claude", action="store_true", help="Only Claude")
    parser.add_argument("--path", type=Path, help="Project directory (default: cwd)")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Structured results")
    parser.add_argument(
        "--paths",
        dest="paths_only",
        action="store_true",
        help="Matching source paths, without ranking or excerpts (default: all)",
    )
    parser.add_argument("--limit", "-n", type=int, help="Session result limit (default: 5; 0: all)")
    parser.add_argument("--since", help="Session start on/after DATE")
    parser.add_argument("--before", help="Session start before DATE")
    parser.add_argument("--file", type=Path, help="Search one verified transcript")
    parser.add_argument(
        "--claude-root",
        dest="claude_roots",
        action="append",
        type=Path,
        help="Claude config profile; repeat for several",
    )
    parser.add_argument("--recursive", action="store_true", help="Include descendant projects")
    parser.add_argument("--worktrees", action="store_true", help="Include registered worktrees")
    parser.add_argument(
        "--include-agents", action="store_true", help="Children are included by default"
    )
    parser.add_argument("--archives", action="store_true", help="Archives are included by default")
    parser.add_argument("--coverage", action="store_true", help="Include source coverage")
    parser.add_argument(
        "--include-current", action="store_true", help="Include the invoking Codex session"
    )
    parser.add_argument(
        "--exclude-session",
        dest="exclude_sessions",
        action="append",
        help="Exclude a full session ID; repeat for several",
    )
    options = vars(parser.parse_args(arguments))
    scope = {
        key: options.pop(key)
        for key in (
            "file",
            "claude_roots",
            "recursive",
            "worktrees",
            "include_agents",
            "archives",
            "coverage",
        )
    }
    ctx = SimpleNamespace(obj={}, meta={"discovery": scope})
    return execute(ctx, **options)
