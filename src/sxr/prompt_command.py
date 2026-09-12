"""The prompts command: which sessions it reads, and how it says which one.

Its own module for the same reason show has one: cli.py stays a registry of
commands rather than a place where one command's selection rules live.
"""

from typing import Annotated

import typer

from sxr import flags, views_prompts
from sxr.handles import fail, resolve
from sxr.prompt_selection import prompt_navigation, prompt_session


def prompts(
    ctx: typer.Context,
    arg: flags.Arg = None,
    latest: Annotated[
        bool, typer.Option("--latest", help="Newest session with human prompts (the default)")
    ] = False,
    include_all: flags.PromptAllF = False,
    include_context: flags.IncludeContextF = False,
    budget: flags.PromptBudgetF = None,
    line_cap: flags.PromptLineLimitF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Complete human prompts in order, excluding records labelled injected context.

    No selector reads the newest session that has human prompts, walking past
    empty, subagent and review transcripts; --latest is that same default,
    spelled out for scripts. An explicit id, @A:@B range or --file is honored
    exactly, background sessions included.

    Text prints whole: no environment budget trims it. --budget/--line-limit ask
    for compact text, --all lifts every limit, --include-context widens selection.
    --json emits the original records, never a session projection.
    """
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd)
    explicit = arg is not None or bool(sessions and sessions[0].extra.get("explicit_file"))
    if latest and explicit:
        fail("--latest cannot be combined with a session ID or --file")
    opts = views_prompts.PromptOpts(
        include_all=include_all,
        include_context=include_context,
        json_out=json_out,
        limit=limit,
        budget=budget,
        line_cap=line_cap,
    )
    if explicit:
        refs = resolve(arg, sessions)
        raise typer.Exit(views_prompts.prompts_scope(refs, provider.parse, opts))
    ref, events = prompt_session(None, sessions, provider.parse)
    prompt_navigation(ref, json_out)
    raise typer.Exit(views_prompts.prompts(ref, events, opts))
