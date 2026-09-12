"""Choose which sessions the prompts view reads, and say which one it chose.

Adopted from the published v0.13.0 `prompt_selection.py` and kept close to it so
future upstream changes stay mergeable. Two departures, both from D-08: reading
stays the default, so there is no catalog here and no `prompt_records`; and the
record predicate is not duplicated -- `views_prompts.human_prompt` already is it.

Session filtering is upstream's and is taken wholesale: the newest session is a
poor default when it is a subagent transcript, a review, or has no human input
at all, so the default walks past those. An explicit id or `--file` is always
honored exactly, however empty or background the session it names.
"""

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

from sxr.handles import resolve
from sxr.model import Event, SessionRef
from sxr.navigation import scope_command
from sxr.views_prompts import human_prompt

BACKGROUND = {"agent", "subagent", "guardian_review"}


def human_records(events: list[Event]) -> list[Event]:
    """The session's human prompts, by the same predicate the view prints with."""
    kind = "user_message" if any(e.kind == "user_message" for e in events) else "text"
    return [e for e in events if e.role == "user" and human_prompt(e, kind)]


def background(ref: SessionRef) -> bool:
    """Is this a nested or review transcript rather than a human conversation?"""
    return bool(
        ref.kind in BACKGROUND or ref.extra.get("parent_id") or ref.extra.get("parent_thread_id")
    )


def human_sessions(
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
) -> Iterator[tuple[SessionRef, list[Event], list[Event]]]:
    """Human conversations in scope order, keeping the handles the scope gave them."""
    for index, ref in enumerate(refs):
        if background(ref):
            continue
        events = parse(ref.path)
        records = human_records(events)
        if records:
            ref.extra.update(prompt_handle=f"@{index + 1}", prompt_skipped=index)
            yield ref, events, records


def prompt_session(
    arg: str | None,
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
) -> tuple[SessionRef, list[Event]]:
    """Honor an explicit selection; otherwise find the newest human conversation.

    Raises SystemExit(1) when the scope holds no human conversation at all, which
    is the empty-result contract every read view follows.
    """
    if arg is not None or not refs or refs[0].extra.get("explicit_file"):
        ref = resolve(arg, refs)[0]
        if not ref.extra.get("explicit_file"):
            ref.extra["prompt_handle"] = f"@{refs.index(ref) + 1}"
        return ref, parse(ref.path)
    for ref, events, _records in human_sessions(refs, parse):
        return ref, events
    print(f"no human prompts in {len(refs)} sessions in scope", file=sys.stderr)
    raise SystemExit(1)


def prompt_navigation(ref: SessionRef, json_out: bool) -> None:
    """Name the discovered session, and the command that lists what was skipped.

    Called only when nothing was selected, so it never annotates a session the
    caller already named -- an explicit id, range or --file is silent, as it is
    in every other read view. Under --json it is silent unless something was
    skipped, so stdout stays exactly the raw records D-09 pins.
    """
    skipped = ref.extra.get("prompt_skipped", 0)
    if not ref.extra.get("navigation") or (json_out and not skipped):
        return
    handle = ref.extra.get("prompt_handle", "")
    note = f" (skipped {skipped} newer empty or background sessions)" if skipped else ""
    print(f"# prompts: {handle} {ref.id}{note}".lstrip(), file=sys.stderr)
    if not json_out:
        # `list`, not `prompts`: under D-08 prompts reads, so the command that
        # shows the skipped sessions is the session list itself.
        print(f"# sessions: {scope_command(ref, 'list')}", file=sys.stderr)
