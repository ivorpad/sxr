"""Resolve session arguments: @N handles, @A:@B ranges, id prefixes, names.

Time also selects sessions: --since/--before narrow a scope to the sessions
started inside a half-open window, so an agent can read history that predates
its own running session.
"""

import re
import sys
from datetime import UTC, datetime
from typing import NoReturn

from sxr.model import SessionRef
from sxr.util import now_utc, one_line

_HEX = set("0123456789abcdef-")
CANDIDATES = 5
CANDIDATE_TITLE = 60
WHEN_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-][\d:]+)?)?$"
)
WHEN_FORMS = (
    "YYYY-MM-DD, today, an ISO datetime (2026-07-26T14:30:00Z), or @N for that session's start"
)


def fail(message: str, hint: str = "") -> NoReturn:
    """Print an error (plus an optional # hint) to stderr and exit 2."""
    print(f"error: {message}", file=sys.stderr)
    if hint:
        print(f"# {hint}", file=sys.stderr)
    raise SystemExit(2)


def _candidates(hits: list[SessionRef]) -> str:
    """Up to 5 candidates with short titles; full first messages are a bomb."""
    shown = ", ".join(
        f'{s.short_id} "{one_line(s.label, CANDIDATE_TITLE)}"' for s in hits[:CANDIDATES]
    )
    extra = len(hits) - CANDIDATES
    return f"{shown}, +{extra} more" if extra > 0 else shown


def _ordinal(token: str, count: int) -> int:
    """0-based index for an @N token, bounds-checked."""
    try:
        n = int(token.lstrip("@"))
    except ValueError:
        fail(f"bad handle '{token}'")
    if not 1 <= n <= count:
        fail(f"{token} out of range; {count} sessions in scope")
    return n - 1


def resolve(
    arg: str | None,
    sessions: list[SessionRef],
    missing: str | None = None,
    hint: str = "",
) -> list[SessionRef]:
    """Sessions named by arg: None = newest, @N, @A:@B, id prefix, or name.

    Ambiguous or unknown references exit 2 with capped candidates on stderr.
    missing replaces the not-found text and hint trails every failure, so a
    caller that knows what the argument probably was can teach it.
    """
    if not sessions:
        fail("no sessions in scope")
    if arg is None:
        return [sessions[0]]
    if arg.startswith("@"):
        if ":" in arg:
            lo, hi = (arg.split(":", 1) + [""])[:2]
            a, b = _ordinal(lo, len(sessions)), _ordinal(hi, len(sessions))
            return sessions[min(a, b) : max(a, b) + 1]
        return [sessions[_ordinal(arg, len(sessions))]]
    lowered = arg.lower()
    if set(lowered) <= _HEX:
        hits = [s for s in sessions if s.id.lower().startswith(lowered)]
        exact = [s for s in hits if s.id.lower() == lowered]
        if exact:
            return exact
        if len(hits) == 1:
            return hits
        if hits:
            fail(f"ambiguous id '{arg}': {_candidates(hits)}", hint)
    hits = [s for s in sessions if lowered in s.name.lower() or lowered in s.title.lower()]
    if len(hits) == 1:
        return hits
    if hits:
        fail(f"ambiguous name '{arg}': {_candidates(hits)}", hint)
    fail(missing or f"no session matching '{arg}'; run sxr to list")


def _stamp(value: str, flag: str, sessions: list[SessionRef]) -> str:
    """A --since/--before value as a timestamp comparable with ref.started.

    A leading @ means a session handle, so the bound is that session's own
    start; anything else is a date or ISO datetime, normalized to UTC. Only
    @ selects a session: a bare id prefix like 2026 is also a valid date.
    `today` is midnight UTC today, since the docs teach --before today.
    """
    if value.startswith("@"):
        return resolve(value, sessions)[0].started
    text = value.strip()
    if text == "today":
        text = now_utc().date().isoformat()
    if not WHEN_RE.fullmatch(text):
        fail(f"bad {flag} value '{value}': want {WHEN_FORMS}")
    try:
        when = datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError as exc:
        fail(f"bad {flag} value '{value}': {exc}. Want {WHEN_FORMS}")
    if when.tzinfo is not None:
        when = when.astimezone(UTC).replace(tzinfo=None)
    return when.isoformat()


def window(
    sessions: list[SessionRef], since: str | None = None, before: str | None = None
) -> list[SessionRef]:
    """Sessions whose start falls in [since, before): inclusive, then exclusive.

    A bare date is midnight UTC, so --before today drops today's sessions --
    the caller's own included -- and --since today keeps only them.
    """
    if not since and not before:
        return sessions
    low = _stamp(since, "--since", sessions) if since else ""
    high = _stamp(before, "--before", sessions) if before else ""
    kept = [s for s in sessions if (not low or s.started >= low) and (not high or s.started < high)]
    if sessions and not kept:
        bounds = " ".join(f"{f} {v}" for f, v in (("--since", since), ("--before", before)) if v)
        print(f"# {bounds} kept none of {len(sessions)} sessions in scope", file=sys.stderr)
    return kept
