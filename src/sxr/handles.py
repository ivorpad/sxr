"""Resolve session arguments: @N handles, @A:@B ranges, id prefixes, names."""

import sys

from sxr.model import SessionRef

_HEX = set("0123456789abcdef-")


def fail(message: str) -> None:
    """Print an error to stderr and exit 2; the usage/bad-id contract."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _ordinal(token: str, count: int) -> int:
    """0-based index for an @N token, bounds-checked."""
    try:
        n = int(token.lstrip("@"))
    except ValueError:
        fail(f"bad handle '{token}'")
    if not 1 <= n <= count:
        fail(f"{token} out of range; {count} sessions in scope")
    return n - 1


def resolve(arg: str | None, sessions: list[SessionRef]) -> list[SessionRef]:
    """Sessions named by arg: None = newest, @N, @A:@B, id prefix, or name.

    Ambiguous or unknown references exit 2 with candidates on stderr.
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
            names = ", ".join(f'{s.short_id} "{s.label}"' for s in hits[:6])
            fail(f"ambiguous id '{arg}': {names}")
    hits = [s for s in sessions if lowered in s.name.lower() or lowered in s.title.lower()]
    if len(hits) == 1:
        return hits
    if hits:
        names = ", ".join(f'{s.short_id} "{s.label}"' for s in hits[:6])
        fail(f"ambiguous name '{arg}': {names}")
    fail(f"no session matching '{arg}'; run sxr to list")
    return []
