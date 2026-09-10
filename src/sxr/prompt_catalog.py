"""List conversations with human prompts and references that open their messages."""

import json
import sys
from collections.abc import Callable
from pathlib import Path

from sxr.model import Event, SessionRef
from sxr.navigation import command, scope_command
from sxr.prompt_selection import human_sessions
from sxr.util import day, line_limit, one_line, tab_row


def prompt_catalog(
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
    json_out: bool,
    limit: int | None,
    line_cap: int | None,
) -> int:
    """List human sessions with counts and previews, without renumbering scope handles."""
    total = shown = 0
    first = None
    for ref, _events, records in human_sessions(refs, parse):
        total += 1
        if limit and shown >= limit:
            continue
        if first is None:
            first = ref
            if not json_out:
                print(f"# human sessions: {ref.provider}, newest first")
                print(tab_row("# @", "id", "started", "prompts", "first prompt"))
        shown += 1
        handle = ref.extra["prompt_handle"]
        if json_out:
            print(
                json.dumps(
                    {
                        "type": "prompt_session",
                        "handle": handle,
                        "id": ref.id,
                        "provider": ref.provider,
                        "cwd": ref.cwd,
                        "started": day(ref.started),
                        "path": str(ref.path),
                        "prompts": len(records),
                        "first_prompt": records[0].text,
                        "follow_up": command(ref, "prompts"),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(
                tab_row(
                    handle,
                    ref.short_id,
                    day(ref.started),
                    len(records),
                    one_line(records[0].text, line_limit(line_cap)),
                )
            )
    if not total:
        print(f"no human prompts in {len(refs)} sessions in scope", file=sys.stderr)
        return 1
    if not json_out:
        print(f"# {total} human sessions ({len(refs) - total} empty or background sessions hidden)")
        if total > shown:
            print(f"# +{total - shown} more (raise -n, -n 0 for all)")
        if first:
            read = scope_command(first, "prompts", first.extra["prompt_handle"])
            print(f"# read: {read}")
    return 0
