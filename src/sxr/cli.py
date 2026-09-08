"""Typer wiring for sxr: shared flags parse before or after the command."""

from typing import Annotated

import typer

from sxr import flags, onboard, views_grep, views_info, views_read, views_secrets
from sxr.handles import fail, resolve
from sxr.onboard import EPILOG
from sxr.scope_options import scope_options
from sxr.secrets import clean
from sxr.views_grep import GrepOpts
from sxr.views_read import ShowOpts

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    epilog=EPILOG,
)


@app.callback(invoke_without_command=True)
@scope_options
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
    """sxr: read Claude Code and Codex sessions for a directory.

    Bare invocation lists sessions newest first, with @N handles.
    """
    if version:
        from sxr import __version__

        print(f"sxr {__version__}")
        raise typer.Exit(0)
    ctx.obj = dict(
        codex=use_codex,
        claude=use_claude,
        path=path,
        json=json_out,
        limit=limit,
        since=since,
        before=before,
    )
    if ctx.invoked_subcommand is None:
        provider, cwd, json_out, limit = flags.merge(ctx, False, False, None, False, None)
        raise typer.Exit(
            views_info.list_scope(flags.sessions(ctx, provider, cwd), cwd, json_out, limit)
        )


@app.command("list")
@scope_options
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
    raise typer.Exit(
        views_info.list_scope(
            flags.sessions(ctx, provider, cwd, since, before), cwd, json_out, limit
        )
    )


@app.command()
@scope_options
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
@scope_options
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
@scope_options
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
@scope_options
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
@scope_options
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
@scope_options
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
@scope_options
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
    """Search event text across all sessions in scope; -c ranks matches.

    --since/--before narrow the sessions; -n 0 lifts row and budget limits.
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
@scope_options
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
    """Tool commands with ok/err state; --grep searches all sessions in scope.

    --since/--before narrow the scope by session start date.
    """
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None and grep_ else resolve(arg, sessions)
    raise typer.Exit(views_info.cmds_view(refs, provider.parse, json_out, limit, grep_))


# init, secrets, and clean carry their own flags; their modules own them.
app.command("init")(onboard.init_cmd)
app.command("secrets")(scope_options(views_secrets.secrets_cmd))
app.command("clean")(scope_options(clean.clean_cmd))
