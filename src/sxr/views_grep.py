"""Cross-session search: the match rows, the -C windows and the -l session list.

Every output path is capped: -n limits rows, a char budget stops runaway scans,
and the footers name the flag that widens or narrows the next call. The -c table
and the shared diagnostics live in grep_counts.

"""

import json
import re
import sys
from dataclasses import dataclass

from sxr.grep_counts import count_view, counts, empty, warnings
from sxr.grep_options import GrepOpts
from sxr.handles import fail, resolve
from sxr.model import Event, SessionRef
from sxr.navigation import command
from sxr.output import record_events
from sxr.util import clock, line_limit, one_line, scan_budget, tab_row
from sxr.views_read import event_line


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


def _row(ref: SessionRef, event: Event, cap: int) -> str:
    """One match row: session, event index, role, text under the view's cap.

    The cap is passed in rather than defaulted because a row and a -C window in
    the same invocation used to disagree: the window read SXR_LINE_LIMIT and the
    row kept one_line's built-in 200 whatever the caller asked for.
    """
    return tab_row(ref.short_id, f"#{event.seq:04d}", event.role, f'"{one_line(event.text, cap)}"')


def _session_json(ref: SessionRef) -> str:
    """-l under --json: the session's identity, since -l names no records.

    There is no raw source record to emit here -- -l answers "which sessions",
    a question the transcript does not contain a line for -- so this is a
    projection, typed and named like the -c table's own `grep_count` rows. It
    carries the full id and the source path so a short-id collision cannot make
    two sessions look like one.
    """
    return json.dumps(
        {
            "type": "grep_session",
            "session": ref.id,
            "provider": ref.provider,
            "path": str(ref.path),
        },
        ensure_ascii=False,
    )


def _emit(ref: SessionRef, events: list[Event], hits: list[Event], opts: GrepOpts, sink: _Sink):
    """Send one session's hits to the sink in the requested shape.

    JSON is decided before -l, so every JSON mode emits JSON. Raw records are
    deduplicated per transcript: one physical line holding two matching blocks
    is one record, and printing it twice would misreport the source.
    """
    if opts.json_out:
        if opts.ids_only:
            sink.write([_session_json(ref)])
            return
        for event in record_events(hits):
            sink.write([json.dumps(event.raw.get("line", {}), ensure_ascii=False)])
        return
    if opts.ids_only:
        sink.write([ref.short_id])
        return
    cap = 0 if opts.complete_text else line_limit(None)
    if opts.context > 0:
        index = {id(event): i for i, event in enumerate(events)}
        for hit in hits:
            sink.write(_window(ref, events, index[id(hit)], opts.context, cap))
        return
    for event in hits:
        sink.write([_row(ref, event, cap)])


def _omitted(total: int, sessions: int, shown: int, opts: GrepOpts) -> None:
    """Say what a cap held back, and name the escape the caller has not used yet.

    Under --json this goes to stderr, because stdout is a record contract (D-09)
    and an omission nobody is told about is the worse of the two problems: before
    this, `grep -n 2 --json` printed 2 of 14 records and said nothing anywhere.
    """
    found = f"{sessions} sessions" if opts.ids_only else f"{total} matches"
    hint = (
        "--all for all of it whole, or --budget 0 to lift the character stop"
        if opts.rows_uncapped
        else "narrow the pattern, scope to <id>, -n 0 for every result, "
        "or --all for all of it whole"
    )
    stream = sys.stderr if opts.json_out else sys.stdout
    print(f"# {found}, showing first {shown}; {hint}", file=stream)
    if opts.limit == 0 and not opts.uncapped:
        # -n 0 used to lift the character budget as well. It stopped here instead,
        # so the caller needs to hear that the flag they used no longer does that.
        print(
            "# -n 0 lifts the result cap only now; the character budget still "
            "applies (--all, or --budget 0)",
            file=sys.stderr,
        )


def _hits_view(
    pattern: str,
    refs: list[SessionRef],
    parse,
    needle: re.Pattern,
    opts: GrepOpts,
    warn: list[str],
) -> int:
    """Match rows, id list, or -C windows, all under the printing caps."""
    sink = _Sink(
        row_cap=None if opts.rows_uncapped or not opts.limit else opts.limit,
        # -n used to lift this too, which meant an explicit --budget could be
        # discarded by a flag that reads as a row count. Only the character flags
        # decide the character stop now.
        budget=0 if opts.complete_text or opts.json_out else scan_budget(opts.budget),
    )
    total = 0
    sessions = 0
    first_hit = None
    for ref in refs:
        events = opts.events(ref, parse)
        hits = [e for e in events if e.text and needle.search(e.text)]
        total += len(hits)
        if hits:
            if first_hit is None:
                first_hit = (ref, hits[0].seq)
            sessions += 1
            _emit(ref, events, hits, opts, sink)
    if total == 0:
        return empty(pattern, len(refs), warn)
    if sink.capped:
        _omitted(total, sessions, sink.shown, opts)
    if opts.json_out:
        return 0
    if not opts.ids_only and opts.context == 0 and first_hit:
        ref, seq = first_hit
        print(f"# context inline: -C 3; zoom: {command(ref, 'show', '--around', str(seq))}")
    for line in warn:
        print(line)
    return 0


def grep_view(pattern: str, refs: list[SessionRef], parse, opts: GrepOpts) -> int:
    """Search event text across the scope; -c ranks sessions, -l lists ids."""
    opts.check()
    needle = compile_pattern(pattern, opts.fixed, opts.ignore_case)
    warn = warnings(pattern, opts)
    if opts.count:
        return count_view(pattern, counts(refs, parse, needle, opts), opts, warn)
    return _hits_view(pattern, refs, parse, needle, opts, warn)
