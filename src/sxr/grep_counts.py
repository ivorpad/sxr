"""The -c decision table, and the diagnostics both grep shapes print.

`grep` answers two different questions -- which sessions mention this, and where
does it appear -- and the count table is the first of them. The zero-match and
pattern warnings live here too, because both shapes end the same way when a
search finds nothing or when the pattern would miss matches silently.
"""

import json
import sys

from sxr.grep_options import METACHARS, SORTS, GrepOpts
from sxr.model import SessionRef
from sxr.navigation import command
from sxr.util import LIVE_NOTE, date_of, is_live, live_mark, order_key, tab_row

TITLE_CAP = 50
BROADEN = "# smart-case regex; -F for literal; --codex / --path <dir> widen scope"


def warnings(pattern: str, opts: GrepOpts) -> list[str]:
    """Footer lines for the two patterns that miss matches silently."""
    lines = []
    if not opts.ignore_case and pattern != pattern.lower():
        lines.append(
            "# pattern has capitals: smart-case matches exact case; lowercase it or -i for any-case"
        )
    if not opts.fixed and any(c in METACHARS for c in pattern):
        lines.append("# pattern has regex metachars; -F matches it literally")
    return lines


def empty(pattern: str, scanned: int, warn: list[str]) -> int:
    """Zero-match diagnostics on stderr: scope searched, then how to widen."""
    print(f"no matches for '{pattern}' in {scanned} sessions", file=sys.stderr)
    for line in warn:
        print(line, file=sys.stderr)
    print(BROADEN, file=sys.stderr)
    return 1


def title(ref: SessionRef, mark: bool = False) -> str:
    """Session title as the bare list shows it, trimmed for a table cell.

    mark prefixes the (live) label, which belongs in the title cell: a sixth
    column would break every TSV parser again, and a suffix hides behind the
    50-char trim exactly when the title is long.
    """
    return (live_mark(ref.ended) if mark else "") + " ".join(ref.label.split())[:TITLE_CAP]


def _order(rows: list[tuple], opts: GrepOpts) -> list[tuple]:
    """Count rows sorted by match density, or oldest first for --sort started."""
    kept = rows if opts.include_all else [row for row in rows if row[1]]
    if opts.order == SORTS[1]:
        return sorted(kept, key=lambda row: order_key(row[0].started))
    return sorted(kept, key=lambda row: -row[1])


def counts(refs: list[SessionRef], parse, needle, opts: GrepOpts) -> list[tuple]:
    """(session, matches, first matching seq) for every session in scope."""
    rows = []
    for ref in refs:
        hits = [
            e for e in opts.events(ref, parse, summarize=True) if e.text and needle.search(e.text)
        ]
        rows.append((ref, len(hits), hits[0].seq if hits else 0))
    return rows


def count_view(pattern: str, rows: list[tuple], opts: GrepOpts, warn: list[str]) -> int:
    """The decision table: which sessions match, and where to zoom first."""
    if opts.budget is not None:
        print(
            "# --budget caps match text, which -c does not print; -n caps table rows",
            file=sys.stderr,
        )
    matched = sum(1 for row in rows if row[1])
    if not matched:
        return empty(pattern, len(rows), warn)
    kept = _order(rows, opts)
    shown = kept if not opts.limit else kept[: opts.limit]
    for ref, _, _ in shown:
        ref.summarize()
    if opts.json_out:
        for ref, count, first in shown:
            print(
                json.dumps(
                    {
                        "type": "grep_count",
                        "session": ref.id,
                        "matches": count,
                        "first": first,
                        "started": date_of(ref.started),
                        "live": is_live(ref.ended),
                        "title": title(ref),
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    print(tab_row("# session", "matches", "first", "started", "title"))
    for ref, count, first in shown:
        print(tab_row(ref.short_id, count, first or "", date_of(ref.started), title(ref, True)))
    top = shown[0]
    print(
        f"# {matched} of {len(rows)} sessions match; "
        f"zoom: {command(top[0], 'show', '--around', str(top[2]))}"
    )
    if len(kept) > len(shown):
        print(f"# +{len(kept) - len(shown)} matching sessions hidden (raise -n)")
    if any(is_live(ref.ended) for ref, _count, _first in shown):
        print(LIVE_NOTE)
    print("# oldest first: --sort started; keep zero-match rows: --all")
    for line in warn:
        print(line)
    return 0
