"""Transcript command with optional cached event windows."""

from typing import Annotated

import typer

from sxr import flags, views_read
from sxr.handles import resolve
from sxr.read_cache import read_window
from sxr.session_scope import render as render_scope
from sxr.show_select import KNOWN_KINDS, ShowOpts, validate

KINDS = ", ".join(KNOWN_KINDS)


def show(
    ctx: typer.Context,
    arg: flags.Arg = None,
    around: Annotated[
        int | None, typer.Option(min=1, help="Window on record #N, plus or minus --context")
    ] = None,
    context: Annotated[
        int | None, typer.Option(min=0, help="Half-width of the --around window (default: 10)")
    ] = None,
    range_: Annotated[
        str | None, typer.Option("--range", help="Window on records A:B, inclusive, 0 < A <= B")
    ] = None,
    type_: Annotated[
        str | None,
        typer.Option("--type", help=f"Keep one event kind ({KINDS}, or a provider record type)"),
    ] = None,
    tail: Annotated[
        int | None,
        typer.Option("--tail", min=0, help="Last N selected events, whole text (0 = none)"),
    ] = None,
    thinking: Annotated[
        bool, typer.Option("--thinking", help="Widen the skeleton with thinking")
    ] = False,
    tools: Annotated[
        bool,
        typer.Option("--tool-results", "--tools", help="Widen the skeleton with tool results"),
    ] = False,
    errors: Annotated[
        bool, typer.Option("--errors", help="Keep only records with error properties")
    ] = False,
    full: Annotated[
        bool, typer.Option("--full", help="Every kind, whole text; filters still narrow it")
    ] = False,
    budget: flags.BudgetF = None,
    line_cap: flags.LineLimitF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Transcript skeleton, or an explicit selection; selectors compose, never override.

    Selection runs in one order: window (--around or --range, never both), then
    kind (--type, else the skeleton widened by --thinking/--tool-results, else
    every kind once a window/--full/--errors asked for more), then --errors, then
    --tail, then -n. Text prints whole for any explicit selector and for --full;
    otherwise it trims above --budget. An @A:@B range renders every session.
    """
    opts = ShowOpts(
        thinking=thinking,
        tools=tools,
        errors=errors,
        full=full,
        around=around,
        context=10 if context is None else context,
        range_=range_,
        type_=type_,
        tail=tail,
        json_out=json_out,
        budget=budget,
        line_limit=line_cap,
    )
    validate(opts, context_given=context is not None)
    provider, cwd, opts.json_out, opts.limit = flags.merge(
        ctx, use_codex, use_claude, path, json_out, limit
    )
    refs = resolve(arg, flags.sessions(ctx, provider, cwd))

    def render(ref, rows):
        events, total = read_window(ref, provider, opts)
        return views_read.show(ref, events, opts, total_events=total, rows=rows)

    raise typer.Exit(render_scope(refs, render, opts.limit, "events", json_out=opts.json_out))
