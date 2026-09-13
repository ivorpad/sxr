"""Transcript views: show, prompts, errors. Selection only, no judgment."""

import json
import sys

from sxr.model import Event, SessionRef
from sxr.navigation import command
from sxr.output import RowBudget, print_records, record_events
from sxr.show_select import ShowOpts, empty_reason, is_skeleton, selected
from sxr.util import clock, day, middle_trim, one_line


def event_line(event: Event, trim: bool, cap: int = 0) -> str:
    """One printable line (untrimmed text when trim is False)."""
    body = " ".join(event.text.split()) if trim else event.text
    if event.kind == "tool":
        state = f" -> {event.tag}" if event.tag else ""
        return f'{event.tool} "{one_line(event.text, cap) if trim else event.text}"{state}'
    if event.kind == "result":
        head = f"({event.tool}, is_error)" if event.is_error else f"({event.tool})"
        return f'{head} "{middle_trim(body, cap) if trim else event.text}"'
    if event.kind in ("text", "thinking"):
        tag = f"({event.tag}) " if event.tag else ""
        return f'{tag}"{one_line(body, cap) if trim else event.text}"'
    return one_line(body, cap) if trim else event.text


def print_events(
    events: list[Event],
    trim: bool,
    limit: int | None,
    cap: int = 0,
    budget: RowBudget | None = None,
) -> None:
    """Print event lines with the shared #seq/time/role/kind prefix; -n 0 = all.

    An inherited budget spends one allowance across a whole session range and
    reports its own omissions; without one, the note stays as it always was.
    """
    if budget is not None:
        for event in budget.take(events):
            _print_event(event, trim, cap)
        return
    for event in events if not limit else events[:limit]:
        _print_event(event, trim, cap)
    if limit and len(events) > limit:
        print(f"# +{len(events) - limit} more events (raise -n, -n 0 for all)")


def _print_event(event: Event, trim: bool, cap: int) -> None:
    """One event row: #seq, clock, role, kind, then the rendered body."""
    kind = {"text": "text", "thinking": "think", "tool": "tool", "result": "result"}.get(
        event.kind, event.kind
    )
    print(
        f"#{event.seq:04d}  {clock(event.ts)}  {event.role:<6} {kind:<7} "
        f"{event_line(event, trim, cap)}"
    )


def _trim_decision(events: list[Event], limit: int | None, budget_flag: int | None) -> tuple:
    """(trim?, total chars, effective budget) for a scan view."""
    from sxr.util import scan_budget

    shown = events if not limit else events[:limit]
    total = sum(len(e.text) for e in shown)
    budget = scan_budget(budget_flag)
    return budget > 0 and total > budget, total, budget


def _header(ref: SessionRef, total_events: int) -> None:
    """Session header: full id, file, provenance properties, record counts."""
    print(f"session:  {ref.id}")
    print(f"file:     {ref.path}")
    line = f"started:  {day(ref.started)}"
    branch = ref.extra.get("gitBranch", "")
    if branch:
        line += f"   branch: {branch}"
    if ref.extra.get("originator"):
        line += f"   origin: {ref.extra['originator']}"
    print(line)
    if ref.model:
        print(f"model:    {ref.model}")
    print(f"events:   {total_events}")
    print()


def show(
    ref: SessionRef,
    events: list[Event],
    opts: ShowOpts,
    *,
    total_events: int | None = None,
    rows: RowBudget | None = None,
) -> int:
    """Render a transcript skeleton or an explicit selection; exit 1 when empty.

    Selection order lives in `show_select`; this function only displays what
    survived it. Text prints whole whenever the view fits the char budget; only
    over-budget scans trim, and they say so with the recovery commands. rows is
    the allowance a session range shares; None means this session owns it.
    """
    from sxr.util import human_num, line_limit

    picked, zoom = selected(events, opts)
    count = len(events) if total_events is None else total_events
    if not picked:
        print(
            f"nothing selected in {ref.short_id}: {empty_reason(opts, count)}",
            file=sys.stderr,
        )
    if opts.json_out:
        print_records(picked, opts.limit, budget=rows)
        return 0 if picked else 1
    trim, total, budget = _trim_decision(picked, opts.limit, opts.budget)
    trim = trim and not (zoom or opts.full)
    _header(ref, count)
    cap = line_limit(opts.line_limit)
    print_events(picked, trim=trim, limit=opts.limit, cap=cap, budget=rows)
    if trim:
        print(
            f"# trimmed to {cap}-char lines ({human_num(total)} chars > "
            f"{human_num(budget)} budget); whole text: --around <seq>, "
            f"--range A:B, --budget 0, or --json"
        )
    if is_skeleton(opts):
        _hidden_note(events, picked)
    return 0 if picked else 1


def _hidden_note(events: list[Event], selected: list[Event]) -> None:
    """Say what the skeleton hid and which flag reveals each kind."""
    shown = {id(e) for e in selected}
    hidden: dict[str, int] = {}
    for event in events:
        if id(event) not in shown:
            hidden[event.kind] = hidden.get(event.kind, 0) + 1
    if not hidden:
        return
    parts = []
    if hidden.get("thinking"):
        parts.append(f"{hidden.pop('thinking')} thinking (--thinking)")
    if hidden.get("result"):
        parts.append(f"{hidden.pop('result')} tool results (--tool-results)")
    if hidden:
        parts.append(f"{sum(hidden.values())} meta/attachments (--full)")
    print(f"# hidden: {', '.join(parts)}; zoom: --around <seq>; by kind: --type <kind>")


def error_records(ref: SessionRef, parse) -> list[Event]:
    """One event per distinct failing tool call in one transcript, in file order.

    Selection is the recorded `is_error` property, never inferred from wording.
    `show --errors` is deliberately wider: it also keeps the *call* a failed
    result belongs to, which carries `tag == "err"` but not `is_error`.
    """
    seen: set[str] = set()
    picked = []
    for event in parse(ref.path):
        if not event.is_error:
            continue
        call_id = str(event.raw.get("tool_use_id") or event.seq)
        if call_id in seen:
            continue
        seen.add(call_id)
        picked.append(event)
    return picked


def error_line(ref: SessionRef, event: Event, compact: bool, cap: int = 0) -> str:
    """One error row: record number, source session, time, tool, then the text.

    The source column makes a row self-describing, so two errors at the same
    sequence in different sessions stay distinguishable and either row can be
    pasted into `sxr show <source> --around <seq>` on its own. Text is complete
    by default: inline and quoted while the error is one line, otherwise an
    indented block below the row so the row itself stays greppable. `--compact`
    is the only thing that trims, and it trims the middle, where error output
    keeps its summary -- at the per-line cap the view resolved, so `--compact`
    answers SXR_LINE_LIMIT instead of keeping fixed widths whatever was asked.
    """
    head = f"#{event.seq:04d}  {ref.short_id}  {clock(event.ts)}  {event.tool or event.kind}"
    if event.tag:
        head += f"  [{event.tag}]"
    if compact:
        return f'{head}  "{middle_trim(" ".join(event.text.split()), cap)}"'
    text = event.text.strip("\n")
    if "\n" in text:
        return head + "\n" + "\n".join("    " + line for line in text.splitlines())
    return f'{head}  "{text}"'


def errors(
    refs: list[SessionRef], parse, json_out: bool, limit: int | None, compact: bool = False
) -> int:
    """Records carrying error properties, chronological; exit 1 when none.

    Every row names its own session, and error text prints whole unless
    `--compact` asks for one trimmed line. `-n` remains one allowance shared by
    every selected session, and `--json` still emits complete distinct physical
    source records.
    """
    from sxr.util import line_limit

    total = 0
    budget = RowBudget(limit)
    by_tool: dict[str, int] = {}
    first: tuple[SessionRef, Event] | None = None
    # Resolved once per view, so an unusable SXR_LINE_LIMIT is reported once and
    # every trimmed row of this view answers to the same number.
    cap = line_limit(None) if compact else 0
    for ref in refs:
        picked = error_records(ref, parse)
        total += len(picked)
        for event in picked:
            by_tool[event.tool or event.kind] = by_tool.get(event.tool or event.kind, 0) + 1
        if json_out:
            for event in budget.take(record_events(picked)):
                print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
            continue
        for event in budget.take(picked):
            first = first or (ref, event)
            print(error_line(ref, event, compact, cap))
    budget.notice("error records", stderr=json_out)
    if total == 0:
        scope = ", ".join(r.short_id for r in refs)
        print(f"no error records in {scope}", file=sys.stderr)
        return 1
    if not json_out:
        parts = ", ".join(f"{tool} {n}" for tool, n in sorted(by_tool.items(), key=lambda i: -i[1]))
        print(f"# {total} error records ({parts})")
        if first is not None:
            source, event = first
            print(f"# zoom: {command(source, 'show', '--around', str(event.seq))}")
    return 0
