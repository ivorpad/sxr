"""Secret auditing by default, with an explicit clean subcommand."""

import typer
from typer.core import TyperGroup

from sxr import flags
from sxr.scope_options import scope_options
from sxr.secrets_commands import clean_cmd, secrets_cmd


class SecretsGroup(TyperGroup):
    """Preserve `secrets SESSION` as an audit while reserving named subcommands."""

    def resolve_command(self, ctx, args):
        """Treat a session selector as an argument to the default audit command."""
        if args and not args[0].startswith("-") and self.get_command(ctx, args[0]) is None:
            return "audit", self.get_command(ctx, "audit"), args
        return super().resolve_command(ctx, args)


app = typer.Typer(
    cls=SecretsGroup,
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
@scope_options
def secrets(
    ctx: typer.Context,
    candidates: bool = typer.Option(
        False, "--candidates", help="Include entropy review candidates"
    ),
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Audit leaked credentials, showing fingerprints only. Use clean to redact them.

    With no subcommand, audit the scope. A session ID, @N handle or name narrows
    the audit: sxr secrets @2. Cleaning previews changes unless --apply is set.
    """
    root = ctx.obj or {}
    ctx.obj = dict(
        root,
        codex=use_codex or root.get("codex", False),
        claude=use_claude or root.get("claude", False),
        path=path or root.get("path"),
        json=json_out or root.get("json", False),
        limit=limit if limit is not None else root.get("limit"),
        since=since or root.get("since"),
        before=before or root.get("before"),
    )
    ctx.meta["secrets_candidates"] = candidates
    if ctx.invoked_subcommand is None:
        secrets_cmd(ctx)


app.command("audit", hidden=True)(scope_options(secrets_cmd))
app.command("clean")(scope_options(clean_cmd))
