"""Resolve session arguments: @N handles, @A:@B ranges, id prefixes, names."""

import sys
from typing import NoReturn

from sxr.model import SessionRef
from sxr.util import one_line

_HEX = set("0123456789abcdef-")
CANDIDATES = 5
CANDIDATE_TITLE = 60


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
