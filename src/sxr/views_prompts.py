"""The prompts view: complete human input by default, compact only on request.

Selection and presentation are separate concerns here. Which records count as
human input comes from the transcript's own provenance properties; whether the
view is complete or compact comes from the caller's limit flags. `--all` only
lifts limits, `--include-context` only widens selection.
"""

import sys
from dataclasses import dataclass

from sxr.model import Event, SessionRef
from sxr.output import RowBudget, print_records
from sxr.session_scope import render
from sxr.util import human_num, line_limit, scan_budget
from sxr.views_read import print_events


@dataclass
class PromptOpts:
    """Selection and presentation flags for the prompts view."""

    include_all: bool = False
    include_context: bool = False
    json_out: bool = False
    limit: int | None = None
    budget: int | None = None
    line_cap: int | None = None


@dataclass
class Display:
    """The resolved presentation: row cap, compact threshold, per-line cap."""

    limit: int | None = None
    compact: bool = False
    budget: int = 0
    cap: int = 0


def human_prompt(event: Event, kind: str) -> bool:
    """Select human input using the transcript's recorded content provenance."""
    if event.kind != kind:
        return False
    record = event.raw.get("line", {})
    if record.get("isMeta") or record.get("isCompactSummary"):
        return False
    kinds = _content_item_kinds(record)
    if kinds is None:
        return True  # Legacy rollouts do not label response-item content.
    return any(value.startswith("user.") for value in kinds)


def context_label(event: Event) -> str:
    """The recorded provenance of a non-human user-role record.

    Only properties already present in the record are reported; nothing here
    infers authorship from wording. Records carrying no label at all fall back
    to their event kind, so the display never invents a source.
    """
    record = event.raw.get("line", {})
    if record.get("isCompactSummary"):
        return "compact"
    if record.get("isMeta"):
        return "meta"
    kinds = _content_item_kinds(record)
    if kinds:
        return kinds[0]
    return "tool_result" if event.kind == "result" else "context"


def _content_item_kinds(record: dict) -> list[str] | None:
    """Codex content-item labels for a record, or None when unlabelled."""
    payload = record.get("payload") or {}
    metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
    kinds = metadata.get("content_item_kinds")
    if not isinstance(kinds, list):
        return None
    return [value for value in kinds if isinstance(value, str)]


def _prompt_kind(events: list[Event]) -> str:
    """Explicit Codex user_message events win over user-role text when present."""
    return "user_message" if any(e.kind == "user_message" for e in events) else "text"


def _selected(events: list[Event], include_context: bool) -> tuple[list[Event], int]:
    """(records to print in source order, how many user records were excluded)."""
    kind = _prompt_kind(events)
    picked: list[Event] = []
    excluded = 0
    for event in events:
        if event.role != "user":
            continue
        if human_prompt(event, kind):
            picked.append(event)
        elif include_context:
            event.tag = event.tag or context_label(event)
            picked.append(event)
        else:
            excluded += 1
    return picked, excluded


def display(opts: PromptOpts) -> Display:
    """Resolve row and character limits; complete output unless asked otherwise.

    `--all` lifts every limit. Otherwise a positive `--budget` or `--line-limit`
    is what requests compact text; no environment default can trim on its own,
    so a plain run always prints whole prompts.
    """
    if opts.include_all:
        return Display()
    limit = opts.limit or None
    if opts.budget is not None and opts.budget <= 0:
        return Display(limit=limit)  # --budget 0 asks for whole text, and wins.
    compact = opts.budget is not None or (opts.line_cap is not None and opts.line_cap > 0)
    if not compact:
        return Display(limit=limit)
    budget = opts.budget if opts.budget is not None else scan_budget(None)
    return Display(limit=limit, compact=True, budget=budget, cap=line_limit(opts.line_cap))


def trims(view: Display, shown: list[Event]) -> tuple[bool, int]:
    """(trim these rows?, their total chars) for an already resolved view."""
    total = sum(len(event.text) for event in shown)
    return (view.compact and total > view.budget), total


def prompts(
    ref: SessionRef, events: list[Event], opts: PromptOpts, rows: RowBudget | None = None
) -> int:
    """Print the session's human prompts in order; exit 1 when there are none.

    rows is the allowance a session range shares; None means this session owns
    it, which is what a single `@N` selection always does.
    """
    picked, excluded = _selected(events, opts.include_context)
    view = display(opts)
    if opts.json_out:
        print_records(picked, view.limit, budget=rows)
        return 0 if picked else 1
    if not picked:
        print(f"no user text records in {ref.short_id}", file=sys.stderr)
        return 1
    shown = list((rows or RowBudget(view.limit)).take(picked))
    trim, total = trims(view, shown)
    print_events(shown, trim=trim, limit=None, cap=view.cap)
    _summary(len(shown), picked, excluded, opts)
    if trim:
        print(
            f"# trimmed to {view.cap}-char lines ({human_num(total)} chars > "
            f"{human_num(view.budget)} requested budget); whole text: "
            f"--all, --budget 0, or --json"
        )
    return 0


def prompts_scope(refs: list[SessionRef], parse, opts: PromptOpts) -> int:
    """Human prompts of every selected session under one shared row allowance.

    The allowance is the resolved one, so `--all` lifts it for a range exactly
    as it does for a single session.
    """
    return render(
        refs,
        lambda ref, rows: prompts(ref, parse(ref.path), opts, rows),
        display(opts).limit,
        "human prompts",
        json_out=opts.json_out,
    )


def _summary(shown: int, picked: list[Event], excluded: int, opts: PromptOpts) -> None:
    """One line naming what was printed, what was left out, and how to get it."""
    label = "user records" if opts.include_context else "human prompts"
    line = f"# {shown} of {len(picked)} {label} shown"
    if shown < len(picked):
        line += " (raise -n, or -n 0/--all for all)"
    if excluded and not opts.include_context:
        line += (
            f"; {excluded} other user-role records hidden "
            f"(injected context, tool results): --include-context"
        )
    print(line)
