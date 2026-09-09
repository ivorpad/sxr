"""Expose skill lookup in top-level help while keeping normal calls on the fast parser."""

import typer


def lookup(ctx: typer.Context):
    """Find installed SKILL.md files by name or path; sxr skills --help lists options."""
    from sxr.skills_cli import main

    raise typer.Exit(main(ctx.args))


def register(app):
    """Forward skill arguments unchanged to the shared standalone parser."""
    app.command(
        "skills",
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
            "help_option_names": [],
        },
    )(lookup)
