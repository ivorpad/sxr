"""Transcript views: show, prompts, errors. Selection only, no judgment."""

import json
import sys
from dataclasses import dataclass

from sxr.model import Event, SessionRef
from sxr.util import clock, day, middle_trim, one_line


@dataclass
class ShowOpts:
    """Selection flags for the show view."""

    thinking: bool = False
    tools: bool = False
    errors: bool = False
    full: bool = False
    around: int | None = None
    context: int = 10
    range_: str | None = None
    type_: str | None = None
    limit: int | None = None
    json_out: bool = False
    budget: int | None = None
    line_limit: int | None = None


def _selected(events: list[Event], opts: ShowOpts) -> tuple[list[Event], bool]:
    """(events to print, whether the selection is an explicit zoom)."""
    if opts.type_:
        prefix = opts.type_ + "."
        return [e for e in events if e.kind == opts.type_ or e.kind.startswith(prefix)], True
    if opts.around is not None:
        lo, hi = opts.around - opts.context, opts.around + opts.context
        return [e for e in events if lo <= e.seq <= hi], True
    if opts.range_:
        lo, hi = (opts.range_.split(":", 1) + ["0"])[:2]
        try:
            a, b = int(lo), int(hi)
        except ValueError:
            print(f"error: bad range '{opts.range_}'", file=sys.stderr)
            raise SystemExit(2) from None
        return [e for e in events if a <= e.seq <= b], True
    return [e for e in events if _default_pick(e, opts)], False


def _default_pick(event: Event, opts: ShowOpts) -> bool:
    """Default skeleton membership for one event."""
    if opts.full:
        return True
    if opts.errors:
        return event.is_error or event.tag == "err"
    if event.kind in ("text", "tool", "turn_context"):
        return True
    if event.kind == "thinking":
        return opts.thinking
    if event.kind == "result":
        return opts.tools
    return False


def event_line(event: Event, trim: bool, cap: int = 0) -> str:
    """One printable line (untrimmed text when trim is False)."""
    body = " ".join(event.text.split()) if trim else event.text
    if event.kind == "tool":
        state = f" -> {event.tag}" if event.tag else ""
        return f'{event.tool} "{one_line(event.text, cap) if trim else event.text}"{state}'
    if event.kind == "result":
        head = f"({event.tool}, is_error)" if event.is_error else f"({event.tool})"
        return f'{head} "{middle_trim(body) if trim else event.text}"'
    if event.kind in ("text", "thinking"):
        tag = f"({event.tag}) " if event.tag else ""
        return f'{tag}"{one_line(body, cap) if trim else event.text}"'
    return one_line(body, cap) if trim else event.text


def _print_events(events: list[Event], trim: bool, limit: int | None, cap: int = 0) -> None:
    """Print event lines with the shared #seq/time/role/kind prefix."""
    shown = events if limit is None else events[:limit]
    for event in shown:
        kind = {"text": "text", "thinking": "think", "tool": "tool", "result": "result"}.get(
            event.kind, event.kind
        )
        print(
            f"#{event.seq:04d}  {clock(event.ts)}  {event.role:<6} {kind:<7} "
            f"{event_line(event, trim, cap)}"
        )
    if limit is not None and len(events) > limit:
        print(f"# +{len(events) - limit} more events (raise -n, or --range/--around)")


def _trim_decision(events: list[Event], limit: int | None, budget_flag: int | None) -> tuple:
    """(trim?, total chars, effective budget) for a scan view."""
    from sxr.util import scan_budget

    shown = events if limit is None else events[:limit]
    total = sum(len(e.text) for e in shown)
    budget = scan_budget(budget_flag)
    return budget > 0 and total > budget, total, budget


def _header(ref: SessionRef, events: list[Event]) -> None:
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
    print(f"events:   {len(events)}")
    print()


def show(ref: SessionRef, events: list[Event], opts: ShowOpts) -> int:
    """Render a transcript skeleton or an explicit zoom; exit code 0.

    Text prints whole whenever the view fits the char budget; only
    over-budget scans trim, and they say so with the recovery commands.
    """
    from sxr.util import human_num, line_limit

    selected, zoom = _selected(events, opts)
    if opts.json_out:
        for event in selected:
            print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
        return 0 if selected else 1
    trim, total, budget = _trim_decision(selected, opts.limit, opts.budget)
    trim = trim and not zoom
    _header(ref, events)
    cap = line_limit(opts.line_limit)
    _print_events(selected, trim=trim, limit=opts.limit, cap=cap)
    if trim:
        print(
            f"# trimmed to {cap}-char lines ({human_num(total)} chars > "
            f"{human_num(budget)} budget); whole text: --around <seq>, "
            f"--range A:B, --budget 0, or --json"
        )
    if not zoom:
        _hidden_note(events, selected)
    return 0


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
        parts.append(f"{hidden.pop('result')} tool results (--tools)")
    if hidden:
        parts.append(f"{sum(hidden.values())} meta/attachments (--full)")
    print(f"# hidden: {', '.join(parts)}; zoom: --around <seq>; by kind: --type <kind>")


def prompts(
    ref: SessionRef,
    events: list[Event],
    include_all: bool,
    json_out: bool,
    limit: int | None,
    budget: int | None = None,
    cap_flag: int | None = None,
) -> int:
    """User-authored-side records as stored; exit 1 when none exist."""
    from sxr.util import human_num, line_limit

    kinds = ("text", "user_message")
    picked = [e for e in events if e.role == "user" and (include_all or e.kind in kinds)]
    rest = sum(1 for e in events if e.role == "user") - len(picked)
    if json_out:
        for event in picked:
            print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
        return 0 if picked else 1
    if not picked:
        print(f"no user text records in {ref.short_id}", file=sys.stderr)
        return 1
    trim, total, eff_budget = _trim_decision(picked, limit, budget)
    cap = line_limit(cap_flag)
    _print_events(picked, trim=trim, limit=limit, cap=cap)
    note = (
        f" ({rest} more user records are tool_result blocks; --all includes them)" if rest else ""
    )
    print(f"# {len(picked)} user records shown{note}")
    if trim:
        print(
            f"# trimmed to {cap}-char lines ({human_num(total)} chars > "
            f"{human_num(eff_budget)} budget); whole text: --budget 0 or --json"
        )
    return 0


def errors(refs: list[SessionRef], parse, json_out: bool, limit: int | None) -> int:
    """Records carrying error properties, chronological; exit 1 when none."""
    total = 0
    by_tool: dict[str, int] = {}
    for ref in refs:
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
        total += len(picked)
        for event in picked:
            by_tool[event.tool or event.kind] = by_tool.get(event.tool or event.kind, 0) + 1
        if json_out:
            for event in picked:
                print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
            continue
        for event in picked if limit is None else picked[:limit]:
            body = middle_trim(" ".join(event.text.split()))
            denial = f"  [{event.tag}]" if event.tag else ""
            print(
                f'#{event.seq:04d}  {clock(event.ts)}  {event.tool or event.kind}{denial}  "{body}"'
            )
    if total == 0:
        scope = ", ".join(r.short_id for r in refs)
        print(f"no error records in {scope}", file=sys.stderr)
        return 1
    if not json_out:
        parts = ", ".join(f"{tool} {n}" for tool, n in sorted(by_tool.items(), key=lambda i: -i[1]))
        print(f"# {total} error records ({parts})")
        if len(refs) == 1:
            print(f"# zoom: sxr show {refs[0].short_id} --around <seq>")
    return 0
