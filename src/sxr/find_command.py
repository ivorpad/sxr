"""Typer command wiring for ranked session retrieval."""

from typing import Annotated

import typer

from sxr import flags
from sxr.find_service import execute


def find_cmd(
    ctx: typer.Context,
    query: Annotated[
        str | None, typer.Argument(help="Words or quoted phrases identifying a session")
    ] = None,
    all_projects: Annotated[
        bool, typer.Option("--all-projects", help="Search every project in selected stores")
    ] = False,
    any_term: Annotated[
        bool, typer.Option("--any", help="Match any clue instead of requiring all clues")
    ] = False,
    index: Annotated[
        bool, typer.Option("--index", help="Prepare the ranked index without a query")
    ] = False,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: Annotated[
        bool, typer.Option("--json", help="Structured results and coverage")
    ] = False,
    limit: flags.LimitF = None,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    include_current: Annotated[
        bool, typer.Option("--include-current", help="Include the invoking Codex session")
    ] = False,
    exclude_sessions: Annotated[
        list[str] | None,
        typer.Option("--exclude-session", help="Exclude a full session ID; repeat for several"),
    ] = None,
    paths_only: Annotated[
        bool,
        typer.Option("--paths", help="All matching source paths, without ranking or excerpts"),
    ] = False,
) -> None:
    """Find ranked sessions with evidence. Both providers, children and archives are included.

    Use a few distinctive clues. All must occur somewhere in the session;
    --any broadens this. Quoted phrases stay together. Default scope is cwd.
    """
    raise typer.Exit(
        execute(
            ctx,
            query,
            all_projects,
            any_term,
            index,
            use_codex,
            use_claude,
            path,
            json_out,
            limit,
            since,
            before,
            include_current,
            exclude_sessions,
            paths_only,
        )
    )
