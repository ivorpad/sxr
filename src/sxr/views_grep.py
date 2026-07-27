"""Cross-session search: match rows, -C windows, and the -c decision table.

Every output path is capped: -n limits rows, a char budget stops runaway
scans, and the footers name the flag that widens or narrows the next call.
"""

import json
import re
import sys
from dataclasses import dataclass

from sxr.handles import fail, resolve
from sxr.model import Event, SessionRef
from sxr.util import (
    LIVE_NOTE,
    clock,
    is_live,
    line_limit,
    live_mark,
    one_line,
    scan_budget,
    tab_row,
)
from sxr.views_read import event_line

METACHARS = "\\.^$*+?[]{}()|"
TITLE_CAP = 50
BROADEN = "# smart-case regex; -F for literal; --codex / --path <dir> widen scope"
SORTS = ("matches", "started")


@dataclass
class GrepOpts:
    """Search and output flags for the grep view."""

    fixed: bool = False
    count: bool = False
    context: int = 0
    ignore_case: bool = False
    ids_only: bool = False
    include_all: bool = False
    sort: str = "matches"
    json_out: bool = False
    limit: int | None = None
    budget: int | None = None


def compile_pattern(
    pattern: str, fixed: bool = False, ignore_case: bool = False, literal: str = ""
) -> re.Pattern:
    """Smart-case regex (all-lowercase matches any case); bad regex exits 2.

    literal names the caller's own way of matching verbatim, since a bad
    regex must never be answered with a flag the command does not have.
    """
    flags = re.IGNORECASE if ignore_case or pattern == pattern.lower() else 0
    try:
        return re.compile(re.escape(pattern) if fixed else pattern, flags)
    except re.error as exc:
        fix = literal or f"use -F '{pattern}'"
        fail(f"bad regex '{pattern}': {exc}. Quote metacharacters or {fix} to match it literally.")


def scope(arg: str, pattern: str, sessions: list[SessionRef]) -> list[SessionRef]:
    """Sessions named by grep's second positional; typos get taught, not guessed.

    The predictable mistake is an unquoted two-word pattern, where word two
    lands here: say so, and spell the regex that keeps both words.
    """
    tail = f'try "{pattern}.*{arg}" or "{pattern}|{arg}".'
    return resolve(
        arg,
        sessions,
        missing=f"'{arg}' is not a session (@N, id prefix, or name). One pattern per call: {tail}",
        hint=f"one pattern per call: {tail}",
    )


def pick_pattern(pattern: str | None, arg: str | None, expr: str | None) -> tuple[str, str | None]:
    """(pattern, session) with -e taking over, so a positional shifts right."""
    if expr is None:
        if pattern is None:
            fail('missing pattern; usage: sxr grep "<regex>" [session]')
        return pattern, arg
    if pattern is None:
        return expr, arg
    if arg is not None:
        fail(f"'{pattern}' and '{arg}' are both positionals; -e takes the pattern")
    return expr, pattern


def _warnings(pattern: str, opts: GrepOpts) -> list[str]:
    """Footer lines for the two patterns that miss matches silently."""
    lines = []
    if not opts.ignore_case and pattern != pattern.lower():
        lines.append(
            "# pattern has capitals: smart-case matches exact case; lowercase it or -i for any-case"
        )
    if not opts.fixed and any(c in METACHARS for c in pattern):
        lines.append("# pattern has regex metachars; -F matches it literally")
    return lines


def _empty(pattern: str, scanned: int, warn: list[str]) -> int:
    """Zero-match diagnostics on stderr: scope searched, then how to widen."""
    print(f"no matches for '{pattern}' in {scanned} sessions", file=sys.stderr)
    for line in warn:
        print(line, file=sys.stderr)
    print(BROADEN, file=sys.stderr)
    return 1


@dataclass
class _Sink:
    """Prints match blocks until the row cap or the char budget stops it."""

    row_cap: int | None
    budget: int
    shown: int = 0
    chars: int = 0
    capped: bool = False

    def write(self, lines: list[str]) -> None:
        """Print one match's lines, or note that a cap ended the output."""
        if self.capped:
            return
        if self.row_cap is not None and self.shown >= self.row_cap:
            self.capped = True
            return
        size = sum(len(line) + 1 for line in lines)
        if self.budget > 0 and self.shown and self.chars + size > self.budget:
            self.capped = True
            return
        print("\n".join(lines))
        self.shown += 1
        self.chars += size


def _window(ref: SessionRef, events: list[Event], pos: int, context: int, cap: int) -> list[str]:
    """One hit plus its surrounding events, grep -C style, as lines."""
    hit = events[pos]
    lines = []
    for event in events[max(0, pos - context) : pos + context + 1]:
        mark = ">" if event is hit else " "
        lines.append(
            f"{mark} {ref.short_id} #{event.seq:04d} {clock(event.ts)} "
            f"{event.role:<5} {event_line(event, True, cap)}"
        )
    lines.append("--")
    return lines


def _row(ref: SessionRef, event: Event) -> str:
    """One match row: session, event index, role, flattened text."""
    return tab_row(ref.short_id, f"#{event.seq:04d}", event.role, f'"{one_line(event.text)}"')


def _title(ref: SessionRef, mark: bool = False) -> str:
    """Session title as the bare list shows it, trimmed for a table cell.

    mark prefixes the (live) label, which belongs in the title cell: a sixth
    column would break every TSV parser again, and a suffix hides behind the
    50-char trim exactly when the title is long.
    """
    return (live_mark(ref.ended) if mark else "") + " ".join(ref.label.split())[:TITLE_CAP]


def _order(rows: list[tuple], opts: GrepOpts) -> list[tuple]:
    """Count rows sorted by match density, or oldest first for --sort started."""
    kept = rows if opts.include_all else [row for row in rows if row[1]]
    if opts.sort == "started":
        return sorted(kept, key=lambda row: row[0].started)
    return sorted(kept, key=lambda row: -row[1])


def _count_view(pattern: str, rows: list[tuple], opts: GrepOpts, warn: list[str]) -> int:
    """The decision table: which sessions match, and where to zoom first."""
    matched = sum(1 for row in rows if row[1])
    if not matched:
        return _empty(pattern, len(rows), warn)
    kept = _order(rows, opts)
    shown = kept if not opts.limit else kept[: opts.limit]
    if opts.json_out:
        for ref, count, first in shown:
            print(
                json.dumps(
                    {
                        "type": "grep_count",
                        "session": ref.id,
                        "matches": count,
                        "first": first,
                        "started": ref.started[:10],
                        "live": is_live(ref.ended),
                        "title": _title(ref),
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    print(tab_row("# session", "matches", "first", "started", "title"))
    for ref, count, first in shown:
        print(tab_row(ref.short_id, count, first or "", ref.started[:10], _title(ref, True)))
    top = shown[0]
    print(
        f"# {matched} of {len(rows)} sessions match; "
        f"zoom: sxr show {top[0].short_id} --around {top[2]}"
    )
    if len(kept) > len(shown):
        print(f"# +{len(kept) - len(shown)} matching sessions hidden (raise -n)")
    if any(is_live(ref.ended) for ref, _count, _first in shown):
        print(LIVE_NOTE)
    print("# oldest first: --sort started; keep zero-match rows: --all")
    for line in warn:
        print(line)
    return 0


def _counts(refs: list[SessionRef], parse, needle: re.Pattern) -> list[tuple]:
    """(session, matches, first matching seq) for every session in scope."""
    rows = []
    for ref in refs:
        hits = [e for e in parse(ref.path) if e.text and needle.search(e.text)]
        rows.append((ref, len(hits), hits[0].seq if hits else 0))
    return rows


def _emit(ref: SessionRef, events: list[Event], hits: list[Event], opts: GrepOpts, sink: _Sink):
    """Send one session's hits to the sink in the requested shape."""
    if opts.ids_only:
        sink.write([ref.short_id])
        return
    if opts.json_out:
        for event in hits:
            sink.write([json.dumps(event.raw.get("line", {}), ensure_ascii=False)])
        return
    if opts.context > 0:
        index = {id(event): i for i, event in enumerate(events)}
        cap = line_limit(None)
        for hit in hits:
            sink.write(_window(ref, events, index[id(hit)], opts.context, cap))
        return
    for event in hits:
        sink.write([_row(ref, event)])


def _hits_view(
    pattern: str,
    refs: list[SessionRef],
    parse,
    needle: re.Pattern,
    opts: GrepOpts,
    warn: list[str],
) -> int:
    """Match rows, id list, or -C windows, all under the printing caps."""
    unlimited = opts.limit == 0
    sink = _Sink(
        row_cap=None if unlimited or not opts.limit else opts.limit,
        budget=0 if unlimited or opts.json_out else scan_budget(opts.budget),
    )
    total = 0
    sessions = 0
    for ref in refs:
        events = parse(ref.path)
        hits = [e for e in events if e.text and needle.search(e.text)]
        total += len(hits)
        if hits:
            sessions += 1
            _emit(ref, events, hits, opts, sink)
    if total == 0:
        return _empty(pattern, len(refs), warn)
    if opts.json_out:
        return 0
    if sink.capped:
        found = f"{sessions} sessions" if opts.ids_only else f"{total} matches"
        print(
            f"# {found}, showing first {sink.shown}; narrow the pattern, "
            f"scope to <id>, or -n 0 for all"
        )
    if not opts.ids_only and opts.context == 0:
        print("# context inline: -C 3; zoom: sxr show <id> --around <seq>")
    for line in warn:
        print(line)
    return 0


def grep_view(pattern: str, refs: list[SessionRef], parse, opts: GrepOpts) -> int:
    """Search event text across the scope; -c ranks sessions, -l lists ids."""
    if opts.sort not in SORTS:
        fail(f"--sort takes {' or '.join(SORTS)}, not '{opts.sort}'")
    needle = compile_pattern(pattern, opts.fixed, opts.ignore_case)
    warn = _warnings(pattern, opts)
    if opts.count:
        return _count_view(pattern, _counts(refs, parse, needle), opts, warn)
    return _hits_view(pattern, refs, parse, needle, opts, warn)
