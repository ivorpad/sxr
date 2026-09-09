"""Locate installed skills by name or path, with a reusable JSON map."""

import argparse
import json
import sys
from pathlib import Path

from sxr.skills_catalog import matches, unchanged
from sxr.skills_store import load, map_path


def parser():
    """Describe skill discovery without loading the transcript command tree."""
    result = argparse.ArgumentParser(
        prog="sxr skills",
        description="Find installed SKILL.md files by directory name or path clues.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=80),
    )
    result.add_argument("query", nargs="?", default="", help="Skill name or qualified path clues")
    result.add_argument(
        "--index", action="store_true", help="Rebuild the map; remember --root choices"
    )
    result.add_argument(
        "--root", action="append", type=Path, help="Search this directory; repeat for more"
    )
    result.add_argument(
        "--defaults", action="store_true", help="With --index, reset to default roots"
    )
    result.add_argument("--paths", action="store_true", help="Print only canonical SKILL.md paths")
    result.add_argument(
        "--aliases", action="store_true", help="With --paths, include symlinked paths"
    )
    result.add_argument("--exact", action="store_true", help="Match the whole skill directory name")
    result.add_argument(
        "--json", action="store_true", help="Include paths, aliases, roots, and completeness"
    )
    result.add_argument(
        "--limit", "-n", type=int, help="Maximum skills (default: 20; --paths: all; 0: all)"
    )
    result.add_argument(
        "--clear", action="store_true", help="Remove the default map and remembered roots"
    )
    return result


def _render(options, path, data):
    selected = matches(data["skills"], options.query, options.exact)
    total = len(selected)
    limit = options.limit if options.limit is not None else (0 if options.paths else 20)
    selected = selected[:limit] if limit else selected
    errors = list(data["errors"])
    count = len(selected)
    selected = [record for record in selected if Path(record["path"]).is_file()]
    if count != len(selected) or not unchanged(data["watched"]):
        errors.append("skill directories changed during lookup; retry")
    if options.json:
        print(
            json.dumps(
                dict(
                    skills=selected,
                    total=total,
                    complete=not errors,
                    errors=errors,
                    coverage=data["coverage"],
                    index=str(path),
                ),
                ensure_ascii=True,
            )
        )
    elif options.paths:
        paths = {record["path"] for record in selected}
        if options.aliases:
            paths.update(alias for record in selected for alias in record["aliases"])
        for name in sorted(paths):
            print(name)
    elif not options.index or options.query:
        print("# name\tpath")
        for record in selected:
            print(f"{record['name']}\t{record['path']}")
        print(f"# {len(selected)} of {total} matching skills")
    for error in errors:
        print(f"# incomplete: {error}", file=sys.stderr)
    if options.index:
        print(
            f"# indexed {len(data['skills'])} skills across {len(data['roots'])} roots: {path}",
            file=sys.stderr,
        )
    return 2 if errors else (0 if selected or options.index else 1)


def main(arguments):
    """Resolve skills without executing or modifying any installed skill instructions."""
    cli = parser()
    options = cli.parse_args(arguments)
    if options.limit is not None and options.limit < 0:
        cli.error("--limit must be zero or greater")
    if options.exact and not options.query:
        cli.error("--exact needs a skill name")
    if options.defaults and (not options.index or options.root):
        cli.error("--defaults requires --index and cannot be combined with --root")
    if options.aliases and not options.paths:
        cli.error("--aliases requires --paths")
    if options.clear and any((options.query, options.root, options.index, options.defaults)):
        cli.error("--clear cannot be combined with a query, --root, or --index")
    try:
        if options.clear:
            map_path().unlink(missing_ok=True)
            return 0
        path, data = load(options.root, options.index, options.defaults)
        return _render(options, path, data)
    except (OSError, ValueError) as exc:
        print(f"error: cannot look up skills: {exc}", file=sys.stderr)
        return 2
