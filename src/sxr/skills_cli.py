"""Locate installed skills by name or path, with a reusable JSON map."""

import argparse
import json
import sys
import time
from pathlib import Path

from sxr.skills_catalog import matches
from sxr.skills_content import current, groups
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
        "--index", action="store_true", help="Discover SKILL.md files (default: all of HOME)"
    )
    result.add_argument(
        "--root", action="append", type=Path, help="Discover below this directory; repeat for more"
    )
    result.add_argument(
        "--defaults", action="store_true", help="With --index, restore discovery across HOME"
    )
    result.add_argument("--paths", action="store_true", help="Print only canonical SKILL.md paths")
    result.add_argument(
        "--aliases", action="store_true", help="With --paths, include symlinked paths"
    )
    result.add_argument(
        "--copies",
        action="store_true",
        help="Show every matching file instead of grouping by SHA-256",
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


def _selected(options, data, errors):
    selected = matches(data["skills"], options.query, options.exact)
    if options.index:
        selected = [record for record in selected if record["sha256"]]
        result, unique = groups(selected, options.copies)
        return result, unique, len(selected)
    valid = []
    changed = False
    for record in selected:
        try:
            updated = current(record)
            changed |= updated != record
            valid.append(updated)
        except OSError as exc:
            errors.append(f"{record['path']}: {exc.strerror or exc}")
            changed = True
    if changed:
        errors.append("indexed SKILL.md paths or contents changed; rerun sxr skills --index")
    # A retargeted alias must not keep matching the old physical file.
    valid = matches(valid, options.query, options.exact)
    result, unique = groups(valid, options.copies)
    return result, unique, len(valid)


def _progress():
    previous = time.monotonic()

    def report(directories, skills):
        nonlocal previous
        now = time.monotonic()
        if now - previous >= 10:
            print(f"# discovering: {directories} directories, {skills} files", file=sys.stderr)
            previous = now

    return report


def _render(options, path, data):
    errors = list(data["errors"])
    selected, unique, files = _selected(options, data, errors)
    total = len(selected)
    limit = options.limit if options.limit is not None else (0 if options.paths else 20)
    selected = selected[:limit] if limit else selected
    if options.json:
        print(
            json.dumps(
                dict(
                    skills=selected,
                    total=total,
                    unique=unique,
                    files=files,
                    complete=not errors,
                    errors=errors,
                    coverage=data["coverage"],
                    index=str(path),
                    indexed_at=data["indexed_at"],
                    cycles_skipped=data.get("cycles_skipped", 0),
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
        print("# name\tcopies\tpath")
        for record in selected:
            print(f"{record['name']}\t{record['copies']}\t{record['path']}")
        print(f"# {len(selected)} of {total} results ({unique} distinct contents, {files} files)")
    for error in errors[:8]:
        print(f"# incomplete: {error}", file=sys.stderr)
    if len(errors) > 8:
        print(f"# {len(errors) - 8} more discovery errors; use --json for all", file=sys.stderr)
    if options.index:
        count = len({record["sha256"] for record in data["skills"] if record["sha256"]})
        print(
            f"# discovered {len(data['skills'])} files ({count} distinct SKILL.md contents)"
            f" across {len(data['roots'])} roots: {path}",
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
        path, data = load(options.root, options.index, options.defaults, _progress())
        return _render(options, path, data)
    except (OSError, ValueError) as exc:
        print(f"error: cannot look up skills: {exc}", file=sys.stderr)
        return 2
