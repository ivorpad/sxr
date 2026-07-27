"""Shared option types, the root/command flag merge, and scope enumeration."""

from pathlib import Path
from typing import Annotated

import typer

from sxr.handles import fail, window
from sxr.model import SessionRef
from sxr.providers import claude_code, codex

Arg = Annotated[str | None, typer.Argument(help="Session: @N, @A:@B, id prefix, or name")]
CodexF = Annotated[bool, typer.Option("--codex", help="Read Codex sessions")]
ClaudeF = Annotated[bool, typer.Option("--claude", help="Read Claude Code sessions (default)")]
PathF = Annotated[Path | None, typer.Option("--path", help="Inspect DIR instead of cwd")]
JsonF = Annotated[bool, typer.Option("--json", help="Raw JSONL records, never truncated")]
LimitF = Annotated[int | None, typer.Option("--limit", "-n", help="Cap printed rows (0 = all)")]
BudgetF = Annotated[
    int | None,
    typer.Option("--budget", help="Chars before scan views trim (0 = never; env SXR_BUDGET)"),
]
LineLimitF = Annotated[
    int | None,
    typer.Option("--line-limit", help="Per-line char cap when trimming (env SXR_LINE_LIMIT)"),
]
SinceF = Annotated[
    str | None,
    typer.Option("--since", help="Sessions started on/after DATE (YYYY-MM-DD, ISO, today, @N)"),
]
BeforeF = Annotated[
    str | None,
    typer.Option("--before", help="Sessions started before DATE; --before today skips today's"),
]

GrepBudgetF = Annotated[
    int | None,
    typer.Option(
        "--budget", help="Chars of match rows before grep stops (0 = all; env SXR_BUDGET)"
    ),
]
PatternF = Annotated[str | None, typer.Argument(help="Regex (smart-case; -F for literal)")]
CountF = Annotated[
    bool, typer.Option("--count", "-c", help="Rank sessions: matches, first seq, started, title")
]
FixedF = Annotated[bool, typer.Option("--fixed", "-F", help="Fixed string, not a regex")]
ContextF = Annotated[int, typer.Option("--context", "-C", help="Events around each match")]
IgnoreCaseF = Annotated[
    bool, typer.Option("--ignore-case", "-i", help="Match any case (default: smart-case)")
]
IdsOnlyF = Annotated[
    bool, typer.Option("--files-with-matches", "-l", help="Print only ids of matching sessions")
]
ExprF = Annotated[
    str | None, typer.Option("--regexp", "-e", help="Pattern (allows a leading dash)")
]
AllRowsF = Annotated[bool, typer.Option("--all", help="-c: keep zero-match rows")]
SortF = Annotated[
    str, typer.Option("--sort", help="-c order: matches (default) or started (oldest first)")
]
AfterCtxF = Annotated[int | None, typer.Option("-A", "--after-context", hidden=True)]
BeforeCtxF = Annotated[int | None, typer.Option("-B", "--before-context", hidden=True)]


def merge(
    ctx: typer.Context,
    use_codex: bool,
    use_claude: bool,
    path: Path | None,
    json_out: bool,
    limit: int | None,
):
    """Combine root-level and command-level shared flags."""
    root = ctx.obj or {}
    use_codex = use_codex or root.get("codex", False)
    use_claude = use_claude or root.get("claude", False)
    if use_codex and use_claude:
        fail("--claude and --codex are mutually exclusive")
    provider = codex if use_codex else claude_code
    cwd = str(path or root.get("path") or Path.cwd())
    return (
        provider,
        cwd,
        json_out or root.get("json", False),
        limit if limit is not None else root.get("limit"),
    )


def sessions(
    ctx: typer.Context,
    provider,
    cwd: str,
    since: str | None = None,
    before: str | None = None,
) -> list[SessionRef]:
    """The scope every command works from: cwd's sessions inside the time window.

    --since/--before count from either flag level, so `sxr --before @2 show`
    and `sxr grep x --before 2026-07-26` narrow the same list, and @N handles
    number the narrowed scope.
    """
    root = ctx.obj or {}
    return window(
        provider.list_sessions(cwd),
        since or root.get("since"),
        before or root.get("before"),
    )
