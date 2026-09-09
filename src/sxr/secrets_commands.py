"""Lazy CLI wiring for secret auditing and cleaning."""

from typing import Annotated

import typer

from sxr import flags
from sxr.handles import resolve

CandidatesF = Annotated[
    bool,
    typer.Option("--candidates", help="Include high-entropy review candidates (noisy)"),
]


ApplyF = Annotated[
    bool, typer.Option("--apply", help="Write the changes; without it this is a dry run")
]


def secrets_cmd(
    ctx: typer.Context,
    arg: flags.Arg = None,
    candidates: CandidatesF = False,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Audit sessions for leaked keys and passwords, masked; a rotation worklist.

    With no session arg the whole directory scope is scanned. Output is one
    row per distinct secret (kind, salted fingerprint, spread); the value
    itself is never printed, in --json mode included.
    """
    from sxr.views_secrets import secrets_view

    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None else resolve(arg, sessions)
    raise typer.Exit(secrets_view(refs, provider.parse, candidates, json_out, limit))


def clean_cmd(
    ctx: typer.Context,
    arg: flags.Arg = None,
    apply: ApplyF = False,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Replace leaked secrets in session files with masked markers. DRY RUN unless --apply.

    Only certain/probable findings are rewritten, never entropy candidates.
    Changed lines are validated as JSON and files replaced atomically;
    (live) sessions are skipped. No backup is kept: a backup keeps the
    secrets. sxr secrets first shows what would be found.
    """
    from sxr.secrets.clean import clean_view

    provider, cwd, _json, _limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None else resolve(arg, sessions)
    raise typer.Exit(clean_view(refs, provider.session_paths, apply))
