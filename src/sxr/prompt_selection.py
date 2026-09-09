"""Select human prompt records and the newest session that contains them."""

import sys
from collections.abc import Callable
from pathlib import Path

from sxr.handles import resolve
from sxr.model import Event, SessionRef


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


def prompt_session(
    arg: str | None,
    refs: list[SessionRef],
    parse: Callable[[Path], list[Event]],
) -> tuple[SessionRef, list[Event]]:
    """Honor explicit selections, otherwise find the newest human conversation."""
    if arg is not None or not refs or refs[0].extra.get("explicit_file"):
        ref = resolve(arg, refs)[0]
        return ref, parse(ref.path)
    for index, ref in enumerate(refs):
        if (
            ref.kind in {"agent", "subagent", "guardian_review"}
            or ref.extra.get("parent_id")
            or ref.extra.get("parent_thread_id")
        ):
            continue
        events = parse(ref.path)
        if prompt_records(events):
            if index:
                print(
                    f"# prompts: {ref.short_id} "
                    f"(skipped {index} newer empty or background sessions)",
                    file=sys.stderr,
                )
            return ref, events
    print(f"no human prompts in {len(refs)} sessions in scope", file=sys.stderr)
    raise SystemExit(1)
