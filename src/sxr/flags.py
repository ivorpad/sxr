"""Shared option types, the root/command flag merge, and scope enumeration."""

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from sxr.discovery_scope import discover
from sxr.handles import fail, window
from sxr.model import SessionRef
from sxr.providers import claude_code, codex

Arg = Annotated[str | None, typer.Argument(help="Session: @N, @A:@B, id prefix, or name")]
CodexF = Annotated[bool, typer.Option("--codex", help="Read Codex sessions")]
ClaudeF = Annotated[bool, typer.Option("--claude", help="Read Claude Code sessions (default)")]
PathF = Annotated[Path | None, typer.Option("--path", help="Inspect DIR instead of cwd")]
JsonF = Annotated[bool, typer.Option("--json", help="Raw JSONL records, never truncated")]
LimitF = Annotated[
    int | None, typer.Option("--limit", "-n", min=0, help="Cap printed rows (0 = all)")
]
BudgetF = Annotated[
    int | None,
    typer.Option(
        "--budget", min=0, help="Chars before scan views trim (0 = never; env SXR_BUDGET)"
    ),
]
LineLimitF = Annotated[
    int | None,
    typer.Option(
        "--line-limit",
        min=0,
        help="Per-line char cap when trimming (0 = never; env SXR_LINE_LIMIT)",
    ),
]
PromptAllF = Annotated[
    bool, typer.Option("--all", help="Lift every row and character limit (complete output)")
]
IncludeContextF = Annotated[
    bool,
    typer.Option(
        "--include-context",
        help="Also print injected context and tool results, labelled by provenance",
    ),
]
PromptBudgetF = Annotated[
    int | None,
    typer.Option("--budget", help="Ask for compact text above CHARS (0 = complete; default: none)"),
]
PromptLineLimitF = Annotated[
    int | None,
    typer.Option("--line-limit", help="Per-line cap; supplying it asks for compact text"),
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
        "--budget",
        min=0,
        help="Chars of match rows before grep stops (0 = all; env SXR_BUDGET)",
    ),
]
PatternF = Annotated[str | None, typer.Argument(help="Regex (smart-case; -F for literal)")]
CountF = Annotated[
    bool, typer.Option("--count", "-c", help="Rank sessions: matches, first seq, started, title")
]
FixedF = Annotated[bool, typer.Option("--fixed", "-F", help="Fixed string, not a regex")]
ContextF = Annotated[
    int, typer.Option("--context", "-C", help="Events around each match (0 or more)")
]
IgnoreCaseF = Annotated[
    bool, typer.Option("--ignore-case", "-i", help="Match any case (default: smart-case)")
]
IdsOnlyF = Annotated[
    bool,
    typer.Option(
        "--ids",
        "--files-with-matches",
        "-l",
        help="List matching sessions, not matches (--json: one identity object each)",
    ),
]
ExprF = Annotated[
    str | None, typer.Option("--regexp", "-e", help="Pattern (allows a leading dash)")
]
GrepAllF = Annotated[
    bool,
    typer.Option("--all", help="Complete match text, no row or char cap (= --full -n 0)"),
]
GrepFullF = Annotated[
    bool, typer.Option("--full", help="Complete match text; -n still caps results")
]
IncludeZeroF = Annotated[
    bool, typer.Option("--include-zero", help="-c: keep sessions with zero matches")
]
SortF = Annotated[
    str | None,
    typer.Option("--sort", help="-c only; matches (default) or started (oldest first)"),
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
    cwd = str(Path(path or root.get("path") or Path.cwd()).expanduser().resolve())
    if ctx.meta.get("discovery", {}).get("file"):
        from sxr.file_selection import selected

        provider, cwd = selected(ctx, use_codex, use_claude, path or root.get("path"))
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
    refs = discover(ctx, provider, cwd)
    since = since or root.get("since")
    before = before or root.get("before")
    for ref in refs:
        for flag, value in (("--since", since), ("--before", before)):
            if value:
                ref.extra["navigation"].extend([flag, value])
    refs = window(refs, since, before)
    identities = Counter((ref.provider, ref.id.lower()) for ref in refs)
    for index, ref in enumerate(refs, start=1):
        handle = f"@{index}"
        ref.extra["handle"] = handle  # The scope position a multi-session view names.
        if identities[ref.provider, ref.id.lower()] > 1:
            ref.extra.update(display_id=handle, navigation_arg=handle)
    return refs
