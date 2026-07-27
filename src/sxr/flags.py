"""Shared option types and the root/command flag merge for every command."""

from pathlib import Path
from typing import Annotated

import typer

from sxr.handles import fail
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
AfterF = Annotated[int | None, typer.Option("-A", "--after-context", hidden=True)]
BeforeF = Annotated[int | None, typer.Option("-B", "--before-context", hidden=True)]


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
