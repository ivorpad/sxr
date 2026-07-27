"""Typer wiring for sxr: shared flags parse before or after the command."""

from pathlib import Path
from typing import Annotated

import typer

from sxr import onboard, views_info, views_read
from sxr.handles import fail, resolve
from sxr.onboard import EPILOG
from sxr.providers import claude_code, codex
from sxr.views_read import ShowOpts

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    epilog=EPILOG,
)

Arg = Annotated[str | None, typer.Argument(help="Session: @N, @A:@B, id prefix, or name")]
CodexF = Annotated[bool, typer.Option("--codex", help="Read Codex sessions")]
ClaudeF = Annotated[bool, typer.Option("--claude", help="Read Claude Code sessions (default)")]
PathF = Annotated[Path | None, typer.Option("--path", help="Inspect DIR instead of cwd")]
JsonF = Annotated[bool, typer.Option("--json", help="Raw JSONL records, never truncated")]
LimitF = Annotated[int | None, typer.Option("--limit", "-n", help="Cap printed rows")]
BudgetF = Annotated[
    int | None,
    typer.Option("--budget", help="Chars before scan views trim (0 = never; env SXR_BUDGET)"),
]
LineLimitF = Annotated[
    int | None,
    typer.Option("--line-limit", help="Per-line char cap when trimming (env SXR_LINE_LIMIT)"),
]


def _merge(
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


def _list(provider, cwd: str, json_out: bool, limit: int | None) -> None:
    """Shared body for bare invocation and the list command."""
    refs = provider.list_sessions(cwd)
    if not refs:
        where = "~/.codex/sessions" if provider is codex else "~/.claude/projects"
        print(f"no sessions found for {cwd} (checked {where})", flush=True)
        raise typer.Exit(0)
    raise typer.Exit(views_info.list_view(refs, json_out, limit, cwd))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
    version: Annotated[bool, typer.Option("--version", help="Print version and exit")] = False,
) -> None:
    """sxr - session x-ray: read Claude Code and Codex sessions for a directory.

    Bare invocation lists sessions for the cwd, newest first, with @N handles.
    Commands accept @N, @A:@B ranges, id prefixes, or names; no id = newest.
    """
    if version:
        from sxr import __version__

        print(f"sxr {__version__}")
        raise typer.Exit(0)
    ctx.obj = {
        "codex": use_codex,
        "claude": use_claude,
        "path": path,
        "json": json_out,
        "limit": limit,
    }
    if ctx.invoked_subcommand is None:
        provider, cwd, json_out, limit = _merge(ctx, False, False, None, False, None)
        _list(provider, cwd, json_out, limit)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """List sessions for the directory, newest first."""
    provider, cwd, json_out, limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    _list(provider, cwd, json_out, limit)


@app.command()
def show(
    ctx: typer.Context,
    arg: Arg = None,
    around: Annotated[int | None, typer.Option(help="Zoom to +/-context of event #N")] = None,
    context: Annotated[int, typer.Option(help="Zoom window half-width")] = 10,
    range_: Annotated[str | None, typer.Option("--range", help="Event span A:B")] = None,
    type_: Annotated[str | None, typer.Option("--type", help="Record type filter")] = None,
    tail: Annotated[
        int | None, typer.Option("--tail", help="Last N selected events, whole text")
    ] = None,
    thinking: Annotated[bool, typer.Option("--thinking")] = False,
    tools: Annotated[bool, typer.Option("--tools")] = False,
    errors: Annotated[bool, typer.Option("--errors")] = False,
    full: Annotated[bool, typer.Option("--full")] = False,
    budget: BudgetF = None,
    line_cap: LineLimitF = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Transcript skeleton; zooms (--around/--range/--type) print whole text."""
    provider, cwd, json_out, limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, provider.list_sessions(cwd))[0]
    opts = ShowOpts(
        thinking=thinking,
        tools=tools,
        errors=errors,
        full=full,
        around=around,
        context=context,
        range_=range_,
        type_=type_,
        tail=tail,
        limit=limit,
        json_out=json_out,
        budget=budget,
        line_limit=line_cap,
    )
    raise typer.Exit(views_read.show(ref, provider.parse(ref.path), opts))


@app.command()
def prompts(
    ctx: typer.Context,
    arg: Arg = None,
    include_all: Annotated[bool, typer.Option("--all")] = False,
    budget: BudgetF = None,
    line_cap: LineLimitF = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """User records in order, exactly as stored."""
    provider, cwd, json_out, limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, provider.list_sessions(cwd))[0]
    events = provider.parse(ref.path)
    raise typer.Exit(
        views_read.prompts(ref, events, include_all, json_out, limit, budget, line_cap)
    )


@app.command()
def errors(
    ctx: typer.Context,
    arg: Arg = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Records with error properties (is_error, nonzero exit_code)."""
    provider, cwd, json_out, limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    refs = resolve(arg, provider.list_sessions(cwd))
    raise typer.Exit(views_read.errors(refs, provider.parse, json_out, limit))


@app.command()
def tools(
    ctx: typer.Context,
    arg: Arg = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Per-tool call and error counts."""
    provider, cwd, json_out, _limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, provider.list_sessions(cwd))[0]
    raise typer.Exit(views_info.tools_view(provider.parse(ref.path), json_out))


@app.command()
def stats(
    ctx: typer.Context,
    arg: Arg = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Counts by record property: the elevation view."""
    provider, cwd, json_out, _limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    for ref in resolve(arg, provider.list_sessions(cwd)):
        views_info.stats_view(ref, provider.parse(ref.path), json_out)
    raise typer.Exit(0)


@app.command("path")
def path_cmd(
    ctx: typer.Context,
    arg: Arg = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Print session file paths; feed them straight to jq."""
    provider, cwd, _json, _limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, provider.list_sessions(cwd))[0]
    raise typer.Exit(views_info.path_view(provider.session_paths(ref)))


@app.command()
def grep(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Regex (smart-case)")],
    arg: Arg = None,
    count: Annotated[bool, typer.Option("--count", "-c", help="Matches per session")] = False,
    fixed: Annotated[bool, typer.Option("--fixed", "-F", help="Fixed string")] = False,
    context: Annotated[int, typer.Option("--context", "-C", help="Events around each match")] = 0,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Search event text across sessions in scope (default: all in cwd)."""
    provider, cwd, json_out, _limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = provider.list_sessions(cwd)
    refs = sessions if arg is None else resolve(arg, sessions)
    raise typer.Exit(
        views_info.grep_view(pattern, refs, provider.parse, fixed, count, json_out, context)
    )


@app.command()
def cmds(
    ctx: typer.Context,
    arg: Arg = None,
    grep_: Annotated[
        str | None, typer.Option("--grep", help="Only commands matching regex (smart-case)")
    ] = None,
    use_codex: CodexF = False,
    use_claude: ClaudeF = False,
    path: PathF = None,
    json_out: JsonF = False,
    limit: LimitF = None,
) -> None:
    """Every tool command a session ran, one line each, with ok/err state.

    --grep filters by command text; with no session arg it searches ALL
    sessions for the directory, one call to find the commands that did X.
    """
    provider, cwd, json_out, limit = _merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = provider.list_sessions(cwd)
    refs = sessions if arg is None and grep_ else resolve(arg, sessions)
    raise typer.Exit(views_info.cmds_view(refs, provider.parse, json_out, limit, grep_))


# init carries its own flags and file handling; onboard.py owns both.
app.command("init")(onboard.init_cmd)
