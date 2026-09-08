"""Attach discovery flags to root and command signatures without repeating them."""

import inspect
from functools import wraps
from pathlib import Path
from typing import Annotated

import typer

OPTIONS = {
    "recursive": (
        False,
        Annotated[
            bool,
            typer.Option("--recursive", help="Include sessions recorded in descendant directories"),
        ],
    ),
    "worktrees": (
        False,
        Annotated[
            bool,
            typer.Option(
                "--worktrees", help="Include registered Git worktrees of the selected repository"
            ),
        ],
    ),
    "claude_roots": (
        None,
        Annotated[
            list[Path] | None,
            typer.Option(
                "--claude-root", help="Claude config root to search; repeat for multiple profiles"
            ),
        ],
    ),
    "include_agents": (
        False,
        Annotated[
            bool, typer.Option("--include-agents", help="Include nested Claude agent transcripts")
        ],
    ),
    "archives": (
        False,
        Annotated[
            bool,
            typer.Option(
                "--archives", help="Include Codex archived_sessions alongside active sessions"
            ),
        ],
    ),
    "coverage": (
        False,
        Annotated[
            bool,
            typer.Option(
                "--coverage",
                help="Report searched/unavailable roots and discovered sources on stderr",
            ),
        ],
    ),
}


def scope_options(function):
    """Typer reads the extended signature; implementations read context metadata."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        ctx = kwargs.get("ctx") or args[0]
        scope = ctx.meta.setdefault("discovery", {})
        for name, (default, _annotation) in OPTIONS.items():
            value = kwargs.pop(name, default)
            if name == "claude_roots":
                scope[name] = [*scope.get(name, []), *(value or [])]
            else:
                scope[name] = scope.get(name, False) or value
        return function(*args, **kwargs)

    signature = inspect.signature(function)
    parameters = list(signature.parameters.values())
    parameters.extend(
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=default,
            annotation=annotation,
        )
        for name, (default, annotation) in OPTIONS.items()
    )
    wrapped.__signature__ = signature.replace(parameters=parameters)
    return wrapped
