"""Typer wiring for sxr: shared flags parse before or after the command."""

from typing import Annotated

import typer

from sxr import flags, onboard, views_grep, views_info, views_read
from sxr.handles import fail, resolve
from sxr.onboard import EPILOG
from sxr.providers import codex
from sxr.views_grep import GrepOpts
from sxr.views_read import ShowOpts

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    epilog=EPILOG,
)


def _list(refs, provider, cwd: str, json_out: bool, limit: int | None) -> None:
    """Shared body for bare invocation and the list command."""
    if not refs:
        where = "~/.codex/sessions" if provider is codex else "~/.claude/projects"
        print(f"no sessions found for {cwd} (checked {where})", flush=True)
        raise typer.Exit(0)
    raise typer.Exit(views_info.list_view(refs, json_out, limit, cwd))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    version: Annotated[bool, typer.Option("--version", help="Print version and exit")] = False,
) -> None:
    """sxr - session x-ray: read Claude Code and Codex sessions for a directory.

    Bare invocation lists sessions for the cwd, newest first, with @N handles.
    Commands accept @N, @A:@B ranges, id prefixes, or names; no id = newest.
    (live) marks sessions written in the last 10 min; --since/--before scope by date.
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
        "since": since,
        "before": before,
    }
    if ctx.invoked_subcommand is None:
        provider, cwd, json_out, limit = flags.merge(ctx, False, False, None, False, None)
        _list(flags.sessions(ctx, provider, cwd), provider, cwd, json_out, limit)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
) -> None:
    """List sessions for the directory, newest first; (live) = written just now."""
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    _list(flags.sessions(ctx, provider, cwd, since, before), provider, cwd, json_out, limit)


@app.command()
def show(
    ctx: typer.Context,
    arg: flags.Arg = None,
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
    budget: flags.BudgetF = None,
    line_cap: flags.LineLimitF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Transcript skeleton; zooms (--around/--range/--type) print whole text."""
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, flags.sessions(ctx, provider, cwd))[0]
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
    arg: flags.Arg = None,
    include_all: Annotated[bool, typer.Option("--all")] = False,
    budget: flags.BudgetF = None,
    line_cap: flags.LineLimitF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """User records in order, exactly as stored."""
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, flags.sessions(ctx, provider, cwd))[0]
    events = provider.parse(ref.path)
    raise typer.Exit(
        views_read.prompts(ref, events, include_all, json_out, limit, budget, line_cap)
    )


@app.command()
def errors(
    ctx: typer.Context,
    arg: flags.Arg = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Records with error properties (is_error, nonzero exit_code)."""
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    refs = resolve(arg, flags.sessions(ctx, provider, cwd))
    raise typer.Exit(views_read.errors(refs, provider.parse, json_out, limit))


@app.command()
def tools(
    ctx: typer.Context,
    arg: flags.Arg = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Per-tool call and error counts."""
    provider, cwd, json_out, _limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, flags.sessions(ctx, provider, cwd))[0]
    raise typer.Exit(views_info.tools_view(provider.parse(ref.path), json_out))


@app.command()
def stats(
    ctx: typer.Context,
    arg: flags.Arg = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Counts by record property: the elevation view."""
    provider, cwd, json_out, _limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    for ref in resolve(arg, flags.sessions(ctx, provider, cwd)):
        views_info.stats_view(ref, provider.parse(ref.path), json_out)
    raise typer.Exit(0)


@app.command("path")
def path_cmd(
    ctx: typer.Context,
    arg: flags.Arg = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Print session file paths; feed them straight to jq."""
    provider, cwd, _json, _limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    ref = resolve(arg, flags.sessions(ctx, provider, cwd))[0]
    raise typer.Exit(views_info.path_view(provider.session_paths(ref)))


@app.command()
def grep(
    ctx: typer.Context,
    pattern: flags.PatternF = None,
    arg: flags.Arg = None,
    count: flags.CountF = False,
    fixed: flags.FixedF = False,
    context: flags.ContextF = 0,
    ignore_case: flags.IgnoreCaseF = False,
    ids_only: flags.IdsOnlyF = False,
    expr: flags.ExprF = None,
    include_all: flags.AllRowsF = False,
    sort: flags.SortF = "matches",
    after_ctx: flags.AfterCtxF = None,
    before_ctx: flags.BeforeCtxF = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    budget: flags.GrepBudgetF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Search event text across sessions in scope (default: all in cwd).

    -c is the decision table: which sessions match, how densely, and the
    first matching event index to zoom into. Rows are capped by -n and by
    the char budget; -n 0 prints everything. --since/--before scope the
    sessions searched; your own (live) session is in scope until you do.
    """
    if after_ctx is not None or before_ctx is not None:
        fail("no -A/-B; context is symmetric: -C 3 prints 3 events each side.")
    pattern, arg = views_grep.pick_pattern(pattern, arg, expr)
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None else views_grep.scope(arg, pattern, sessions)
    opts = GrepOpts(
        fixed=fixed,
        count=count,
        context=context,
        ignore_case=ignore_case,
        ids_only=ids_only,
        include_all=include_all,
        sort=sort,
        json_out=json_out,
        limit=limit,
        budget=budget,
    )
    raise typer.Exit(views_grep.grep_view(pattern, refs, provider.parse, opts))


@app.command()
def cmds(
    ctx: typer.Context,
    arg: flags.Arg = None,
    grep_: Annotated[
        str | None, typer.Option("--grep", help="Only commands matching regex (smart-case)")
    ] = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Every tool command a session ran, one line each, with ok/err state.

    --grep filters by command text; with no session arg it searches ALL
    sessions for the directory, one call to find the commands that did X.
    --since/--before narrow that scope by session start date.
    """
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None and grep_ else resolve(arg, sessions)
    raise typer.Exit(views_info.cmds_view(refs, provider.parse, json_out, limit, grep_))


# init carries its own flags and file handling; onboard.py owns both.
app.command("init")(onboard.init_cmd)
