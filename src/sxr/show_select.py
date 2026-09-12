"""One selection pipeline for show, so no flag silently discards another.

Four stages, always in this order, each narrowing the one before:

1. **window** — `--around N` (plus or minus `--context`) or `--range A:B`, never
   both. Without either, every record in the transcript.
2. **kind** — `--type K` when given. Otherwise every kind, because a window,
   `--full` or `--errors` all mean the caller asked for something other than the
   default reading view. Otherwise the skeleton, which `--thinking` and
   `--tool-results` widen.
3. **errors** — `--errors` keeps only records carrying error properties.
4. **tail** — `--tail N` keeps the last N of whatever survived.

Row count and text trimming are display concerns and happen after all four, in
`views_read.show`. Combinations that name two different windows, or a window
half-width without a window, are usage errors rather than a silent winner.
"""

import re
from dataclasses import dataclass
from typing import NoReturn

from sxr.handles import fail
from sxr.model import Event

SKELETON = ("text", "tool", "turn_context")
KNOWN_KINDS = ("text", "thinking", "tool", "result", "turn_context", "user_message")


@dataclass
class ShowOpts:
    """Selection and display flags for the show view."""

    thinking: bool = False
    tools: bool = False
    errors: bool = False
    full: bool = False
    around: int | None = None
    context: int = 10
    range_: str | None = None
    type_: str | None = None
    tail: int | None = None
    limit: int | None = None
    json_out: bool = False
    budget: int | None = None
    line_limit: int | None = None


def _bad_range(text: str) -> NoReturn:
    """Reject a range spec, teaching both the format and the bounds."""
    fail(
        f"bad range '{text}'; format is A:B, e.g. --range 10:50",
        "A and B are physical record numbers, 0 < A <= B",
    )


def parse_range(text: str) -> tuple[int, int]:
    """Inclusive physical record bounds from A:B, or from the A-B grep habit."""
    spec = text.replace("-", ":") if re.fullmatch(r"\d+-\d+", text) else text
    low, high = (spec.split(":", 1) + ["0"])[:2]
    try:
        start, end = int(low), int(high)
    except ValueError:
        _bad_range(text)
    if not 0 < start <= end:
        _bad_range(text)
    return start, end


def validate(opts: ShowOpts, context_given: bool = False) -> None:
    """Reject the flag combinations that used to discard each other in silence."""
    if opts.around is not None and opts.range_:
        fail(
            "--around and --range are two different windows; use one",
            "--around <seq> zooms around a record, --range A:B spans records",
        )
    if context_given and opts.around is None:
        fail("--context only widens --around", "add --around <seq>, or drop --context")
    if opts.range_:
        parse_range(opts.range_)  # bad bounds are a usage error, not an empty result


def window(events: list[Event], opts: ShowOpts) -> list[Event]:
    """Stage 1: the records a --around or --range window admits."""
    if opts.around is not None:
        low, high = opts.around - opts.context, opts.around + opts.context
        return [e for e in events if low <= e.seq <= high]
    if opts.range_:
        low, high = parse_range(opts.range_)
        return [e for e in events if low <= e.seq <= high]
    return events


def windowed(opts: ShowOpts) -> bool:
    """Whether stage 1 narrows anything."""
    return opts.around is not None or bool(opts.range_)


def kept_kind(event: Event, opts: ShowOpts) -> bool:
    """Stage 2: whether one record's kind survives --type or the skeleton."""
    if opts.type_:
        return event.kind == opts.type_ or event.kind.startswith(opts.type_ + ".")
    if opts.full or opts.errors or windowed(opts):
        return True
    if event.kind in SKELETON:
        return True
    if event.kind == "thinking":
        return opts.thinking
    if event.kind == "result":
        return opts.tools
    return False


def is_error(event: Event) -> bool:
    """Stage 3 predicate: the record carries recorded error properties."""
    return event.is_error or event.tag == "err"


def is_zoom(opts: ShowOpts) -> bool:
    """An explicit selector was named, so text prints whole rather than trimmed."""
    return windowed(opts) or bool(opts.type_) or opts.tail is not None


def is_skeleton(opts: ShowOpts) -> bool:
    """The default reading view: the only one with records worth calling hidden."""
    return not (is_zoom(opts) or opts.full or opts.errors)


def selected(events: list[Event], opts: ShowOpts) -> tuple[list[Event], bool]:
    """All four stages: (records to print, whether whole text was asked for)."""
    picked = [event for event in window(events, opts) if kept_kind(event, opts)]
    if opts.errors:
        picked = [event for event in picked if is_error(event)]
    if opts.tail is not None:
        picked = picked[-opts.tail :] if opts.tail else []
    return picked, is_zoom(opts)


def empty_reason(opts: ShowOpts, total: int) -> str:
    """Why the selection came out empty, naming the selectors that emptied it.

    The cached zoom path hands the view only the records it already selected, so
    this reads the flags and the session's event count rather than the records.
    A mistyped `--type` is the easy mistake, so that case says where the kinds a
    session recorded are listed.
    """
    if not total:
        return "the transcript has no records"
    if opts.tail == 0:
        return "--tail 0 selects no records"
    asked = []
    if opts.around is not None:
        asked.append(f"--around {opts.around} within +/-{opts.context}")
    if opts.range_:
        asked.append(f"--range {opts.range_}")
    if opts.type_:
        asked.append(f"--type {opts.type_}")
    if opts.errors:
        asked.append("--errors")
    if not asked:
        return f"none of the {total} events are text, tool calls or turn context"
    hint = "; sxr stats lists the kinds a session recorded" if opts.type_ else ""
    return f"none of the {total} events satisfy {' and '.join(asked)}{hint}"
