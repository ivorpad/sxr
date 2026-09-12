"""Snapshot CLI parsers and help without changing sxr or real session stores."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer.main

from sxr.cli import app

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location(
    "surface_inventory", HERE.parent / "surface_inventory.py"
)
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


def hashes():
    """Identify the source and tests without treating report files as product changes."""
    paths = [ROOT / name for name in ("README.md", "pyproject.toml", "justfile", "konpy.json")]
    for directory in ("src", "tests", "native", "packaging"):
        paths.extend(
            p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts
        )
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p.is_file()
    }


def collect():
    """Save all actual parameters, including automatically attached help switches."""
    surfaces = INVENTORY.inventory()
    commands = {}

    def walk(command, path="root"):
        commands[path] = command
        for name, child in getattr(command, "commands", {}).items():
            walk(child, name if path == "root" else f"{path} {name}")

    walk(typer.main.get_command(app))
    for surface in surfaces:
        if surface["parser"] == "typer":
            command = commands[surface["command"]]
            context = typer.Context(command, **(command.context_settings or {}))
            help_option = command.get_help_option(context)
            if help_option:
                surface["parameters"].append(
                    dict(
                        name="help",
                        kind="option",
                        flags=help_option.opts,
                        help=help_option.help,
                        default=False,
                        type="BOOL",
                        required=False,
                        multiple=False,
                        hidden=False,
                        automatic=True,
                    )
                )
        for parameter in surface["parameters"]:
            parameter["hidden"] = (
                parameter.get("hidden", False) or parameter.get("help") == "==SUPPRESS=="
            )
            parameter.pop("feature_ids", None)
    return surfaces


def main():
    """Capture parser declarations, actual help and source identity for the review."""
    baseline = hashes()
    surfaces = collect()
    scratch = Path("/private/tmp/sxr-command-review")
    scratch.mkdir(exist_ok=True)
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        SXR_CACHE_DIR=str(scratch / "cache"),
        SXR_NO_DAEMON="1",
    )
    helps = HERE / "help"
    helps.mkdir(exist_ok=True)
    results = []
    for surface in surfaces:
        command, parser = surface["command"], surface["parser"]
        args = [] if command == "root" else command.split()
        if parser == "typer" and command in ("find", "skills", "serve"):
            args.insert(0, "--json")
        args.append("--help")
        process = subprocess.run(
            ["rtk", "proxy", sys.executable, "-c", "from sxr import main; main()", *args],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=15,
        )
        name = f"{command.replace(' ', '-')}-{parser}.txt"
        (helps / name).write_text(process.stdout + process.stderr)
        results.append(
            dict(
                command=command,
                parser=parser,
                argv=args,
                exit_code=process.returncode,
                file=f"help/{name}",
            )
        )
    snapshot = dict(
        created_at=datetime.now(UTC).isoformat(),
        basis=(
            "Current uncommitted source tree. The installed sxr binary was "
            "not updated or audited here."
        ),
        head=subprocess.check_output(
            ["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        source=baseline,
        source_unchanged=baseline == hashes(),
        surfaces=surfaces,
        help_checks=results,
    )
    (HERE / "surface.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
    print(
        json.dumps(
            dict(
                surfaces=len(surfaces),
                commands=sorted(set(s["command"] for s in surfaces)),
                parameters=sum(len(s["parameters"]) for s in surfaces),
                help_passed=sum(r["exit_code"] == 0 for r in results),
                source_unchanged=snapshot["source_unchanged"],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
