"""Transcript command with optional cached event windows."""

from typing import Annotated

import typer

from sxr import flags, views_read
from sxr.handles import resolve
from sxr.read_cache import read_window
from sxr.views_read import ShowOpts


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
    events, total = read_window(ref, provider, opts)
    raise typer.Exit(views_read.show(ref, events, opts, total_events=total))
