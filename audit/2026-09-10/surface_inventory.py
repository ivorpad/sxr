"""Enumerate the real CLI parser surfaces and associate options with feature IDs."""

import argparse
from contextlib import suppress
from unittest.mock import patch

import typer.main

from sxr.cli import app
from sxr.find_cli import main as find_main
from sxr.find_worker import main as serve_main
from sxr.skills_cli import parser as skills_parser

COMMON = {
    "--help": ["CLI-HELP"],
    "--version": ["CLI-VERSION"],
    "--codex": ["LIST-CODEX", "CLI-CONFLICTS"],
    "--claude": ["LIST-DEFAULT", "CLI-CONFLICTS"],
    "--path": ["SCOPE-PATH"],
    "--file": ["SCOPE-FILE", "SCOPE-FILE-VALIDATION"],
    "--recursive": ["SCOPE-RECURSIVE"],
    "--worktrees": ["SCOPE-WORKTREES"],
    "--claude-root": ["SCOPE-PROFILES"],
    "--include-agents": ["SCOPE-CHILDREN"],
    "--archives": ["SCOPE-ARCHIVES"],
    "--coverage": ["SCOPE-COVERAGE"],
    "--since": ["TIME-WINDOW", "TIME-HANDLES", "TIME-VALIDATION"],
    "--before": ["TIME-WINDOW", "TIME-HANDLES", "TIME-VALIDATION"],
    "--budget": ["SHOW-BUDGET"],
    "--line-limit": ["SHOW-BUDGET"],
}

SPECIFIC = {
    "show": {
        "--around": "SHOW-AROUND",
        "--context": "SHOW-AROUND",
        "--range": "SHOW-RANGE",
        "--type": "SHOW-FILTERS",
        "--tail": "SHOW-TAIL",
        "--thinking": "SHOW-FILTERS",
        "--tools": "SHOW-FILTERS",
        "--errors": "SHOW-FILTERS",
        "--full": "SHOW-FULL",
    },
    "grep": {
        "--count": "GREP-COUNT",
        "--fixed": "GREP-MATCH",
        "--context": "GREP-CONTEXT",
        "--ignore-case": "GREP-MATCH",
        "--files-with-matches": "GREP-IDS",
        "--regexp": "GREP-MATCH",
        "--all": "GREP-COUNT",
        "--sort": "GREP-ORDER",
        "--after-context": "GREP-CONTEXT",
        "--before-context": "GREP-CONTEXT",
        "--budget": "GREP-LIMIT",
    },
    "find": {
        "--codex": "FIND-DEFAULT",
        "--claude": "FIND-DEFAULT",
        "--include-agents": "FIND-DEFAULT",
        "--archives": "FIND-DEFAULT",
        "--coverage": "FIND-COMPLETENESS",
        "--all-projects": "FIND-DEFAULT",
        "--any": "FIND-CLUES",
        "--index": "FIND-INDEX",
        "--paths": "FIND-PATHS",
        "--include-current": "FIND-CURRENT",
        "--exclude-session": "FIND-EXCLUDE",
    },
    "skills": {
        "--index": "SKILLS-DISCOVERY",
        "--root": "SKILLS-ROOTS",
        "--defaults": "SKILLS-ROOTS",
        "--paths": "SKILLS-PATHS",
        "--aliases": "SKILLS-PATHS",
        "--copies": "SKILLS-GROUP",
        "--exact": "SKILLS-QUERY",
        "--clear": "SKILLS-CLEAR",
    },
    "init": {"--write": "INIT-IDEMPOTENT", "--check": "INIT-CHECK", "--global": "INIT-GLOBAL"},
    "serve": {"--foreground": "WORKER-CONTROL", "--idle": "WORKER-CONTROL"},
    "index": {"--clear": "INDEX-PREPARE"},
    "prompts": {"--all": "PROMPTS-ALL"},
    "cmds": {"--grep": "CMDS-GREP"},
    "secrets": {"--candidates": "SECRETS-CANDIDATES"},
    "secrets audit": {"--candidates": "SECRETS-CANDIDATES"},
    "secrets clean": {"--apply": "CLEAN-APPLY"},
}

LIMITS = {
    "root": "LIST-LIMIT",
    "list": "LIST-LIMIT",
    "find": "FIND-LIMIT",
    "skills": "SKILLS-LIMIT",
    "grep": "GREP-LIMIT",
    "cmds": "CMDS-LIMIT",
    "show": "OUTPUT-LIMIT-JSON",
    "prompts": "OUTPUT-LIMIT-JSON",
    "errors": "ERRORS-LIMIT",
    "tools": "OUTPUT-LIMIT-AGGREGATES",
    "stats": "OUTPUT-LIMIT-AGGREGATES",
    "path": "OUTPUT-LIMIT-AGGREGATES",
    "secrets": "SECRETS-LIMIT",
    "secrets audit": "SECRETS-LIMIT",
    "secrets clean": "OUTPUT-LIMIT-AGGREGATES",
    "index": "INDEX-PREPARE",
}


def links(command, parameter):
    """Map every advertised parameter to an expectation in the feature catalogue."""
    names = parameter["flags"]
    if not names:
        mapping = {
            "find": "FIND-CLUES",
            "skills": "SKILLS-QUERY",
            "init": "INIT-TARGET",
            "serve": "WORKER-CONTROL",
        }
        if command in mapping:
            return [mapping[command]]
        return ["GREP-MATCH"] if parameter["name"] == "pattern" else ["SELECT-HANDLES"]
    if "--limit" in names:
        return [LIMITS[command], "CLI-NEGATIVE-LIMIT"]
    if "--json" in names:
        return [
            {
                "secrets clean": "FORMAT-CLEAN-JSON",
                "path": "FORMAT-PATH-JSON",
                "find": "FIND-EVIDENCE",
                "skills": "SKILLS-JSON",
                "secrets": "SECRETS-MASKING",
                "secrets audit": "SECRETS-MASKING",
            }.get(command, "FORMAT-JSON")
        ]
    for name in names:
        if name in SPECIFIC.get(command, {}):
            return [SPECIFIC[command][name]]
        if name in COMMON:
            return COMMON[name]
    return []


def click_surface(command, path="root"):
    """Walk Typer's actual Click command tree, including the hidden audit alias."""
    parameters = []
    for item in command.params:
        parameter = dict(
            name=item.name,
            kind=item.param_type_name,
            flags=[*item.opts, *getattr(item, "secondary_opts", [])]
            if item.param_type_name == "option"
            else [],
            help=getattr(item, "help", ""),
            default=item.default,
            type=str(item.type),
            required=item.required,
            multiple=getattr(item, "multiple", False),
            hidden=getattr(item, "hidden", False),
        )
        parameter["feature_ids"] = links(path, parameter)
        parameters.append(parameter)
    result = [
        dict(
            command=path,
            parser="typer",
            hidden=command.hidden,
            help=command.help,
            parameters=parameters,
        )
    ]
    if hasattr(command, "commands"):
        for name, child in command.commands.items():
            child_path = name if path == "root" else f"{path} {name}"
            result.extend(click_surface(child, child_path))
    return result


def capture_parser(entrypoint):
    """Obtain argparse metadata without running a query or starting a worker."""
    captured = []

    class StopCapture(Exception):
        """Stop before parsing can run command behavior."""

    def intercept(parser, *args, **kwargs):
        captured.append(parser)
        raise StopCapture

    with patch.object(argparse.ArgumentParser, "parse_args", intercept), suppress(StopCapture):
        entrypoint(["--help"])
    return captured[0]


def argparse_surface(command, parser):
    """Retain the fast-parser flags and defaults independently of Typer."""
    parameters = []
    for item in parser._actions:
        parameter = dict(
            name=item.dest,
            flags=item.option_strings,
            kind="option" if item.option_strings else "argument",
            default=item.default,
            required=item.required,
            help=item.help,
            choices=item.choices,
            type=str(item.type),
            nargs=item.nargs,
        )
        parameter["feature_ids"] = links(command, parameter)
        parameters.append(parameter)
    return dict(
        command=command,
        parser="argparse",
        hidden=False,
        help=parser.description,
        parameters=parameters,
    )


def inventory():
    """Return all public command surfaces and both implementations of fast paths."""
    return [
        *click_surface(typer.main.get_command(app)),
        argparse_surface("find", capture_parser(find_main)),
        argparse_surface("skills", skills_parser()),
        argparse_surface("serve", capture_parser(serve_main)),
    ]
