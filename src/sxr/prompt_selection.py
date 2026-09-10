"""Select human prompt records and the newest session that contains them."""

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

from sxr.handles import resolve
from sxr.model import Event, SessionRef
from sxr.navigation import scope_command


def _prompt_record(event: Event, kind: str) -> bool:
    """Select human input using the transcript's recorded content provenance."""
    if event.kind != kind:
        return False
    record = event.raw.get("line", {})
    if record.get("isMeta") or record.get("isCompactSummary"):
        return False
    payload = record.get("payload") or {}
    metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
    kinds = metadata.get("content_item_kinds")
    if not isinstance(kinds, list):
        return True  # Legacy rollouts do not label response-item content.
    return any(isinstance(value, str) and value.startswith("user.") for value in kinds)


def prompt_records(events: list[Event], include_all: bool = False) -> list[Event]:
    """The same record selection for session discovery, text output and JSON."""
    has_user_message = any(e.kind == "user_message" for e in events)
    kind = "user_message" if has_user_message else "text"
    return [e for e in events if e.role == "user" and (include_all or _prompt_record(e, kind))]


def human_sessions(
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
) -> Iterator[tuple[SessionRef, list[Event], list[Event]]]:
    """Yield human conversations in scope order, preserving their original handles."""
    for index, ref in enumerate(refs):
        if (
            ref.kind in {"agent", "subagent", "guardian_review"}
            or ref.extra.get("parent_id")
            or ref.extra.get("parent_thread_id")
        ):
            continue
        events = parse(ref.path)
        records = prompt_records(events)
        if records:
            ref.extra.update(prompt_handle=f"@{index + 1}", prompt_skipped=index)
            yield ref, events, records


def prompt_session(
    arg: str | None,
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
) -> tuple[SessionRef, list[Event]]:
    """Honor explicit selections, otherwise find the newest human conversation."""
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
    """Identify the selected session and show how to discover other handles."""
    skipped = ref.extra.get("prompt_skipped", 0)
    if not ref.extra.get("navigation") or (json_out and not skipped):
        return
    handle = ref.extra.get("prompt_handle", "")
    selected = f"{handle} {ref.id}" if handle else f"{ref.id} (--file)"
    note = f" (skipped {skipped} newer empty or background sessions)" if skipped else ""
    print(f"# prompts: {selected}{note}", file=sys.stderr)
    if not json_out and not ref.extra.get("explicit_file"):
        print(f"# sessions: {scope_command(ref, 'prompts')}", file=sys.stderr)
