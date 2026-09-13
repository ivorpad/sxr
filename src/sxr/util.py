"""Formatting helpers: truncation, timestamps, human numbers, tab rows.

Trim sizes are defaults, not policy: flags override env vars override these
(SXR_LINE_LIMIT, SXR_BUDGET; 0 disables trimming entirely).
"""

import os
import sys
from datetime import UTC, datetime

ONE_LINE_LIMIT = 200
MIDDLE_HEAD = 200
MIDDLE_TAIL = 120
SCAN_BUDGET_CHARS = 40_000
LIVE_WINDOW_SECONDS = 600
LIVE_MARK = "(live) "
LIVE_NOTE = (
    "# (live) = written in the last 10 min, your own session included; "
    "scope it out with --before today"
)


_noted_env: set[str] = set()


def reset_env_notices() -> None:
    """Forget which variables have been reported. For tests and long-lived workers.

    The notice below is deduplicated per process because one command resolves the
    same variable two or three times. A test session is one process running many
    commands, so it has to be able to clear that memory; `tests/conftest.py` does
    so for every test.
    """
    _noted_env.clear()


def _env_int(name: str, default: int) -> int:
    """Integer env override; a value that cannot be used is reported, then ignored.

    Silence was the defect: a typo in SXR_BUDGET changed nothing and said nothing,
    so a shell could quietly cap or uncap every command for weeks. A negative
    value counts as unusable rather than as a synonym for "no trimming", because 0
    is the documented way to ask for that and `--budget -1` is a usage error.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        if name not in _noted_env:
            _noted_env.add(name)
            print(
                f"# {name}={raw!r} is not a character count of 0 or more; "
                f"using {default}. 0 means never trim",
                file=sys.stderr,
            )
        return default
    return value


def line_limit(flag: int | None = None) -> int:
    """Effective per-line char cap: flag, else SXR_LINE_LIMIT, else default."""
    return flag if flag is not None else _env_int("SXR_LINE_LIMIT", ONE_LINE_LIMIT)


def scan_budget(flag: int | None = None) -> int:
    """Effective whole-view char budget: flag, else SXR_BUDGET, else default."""
    return flag if flag is not None else _env_int("SXR_BUDGET", SCAN_BUDGET_CHARS)


def one_line(text: str, limit: int = ONE_LINE_LIMIT) -> str:
    """Flatten to one line; trim the tail with an explicit recovery marker."""
    flat = " ".join(text.split())
    if limit <= 0 or len(flat) <= limit:
        return flat
    return f"{flat[:limit]}... [+{len(flat) - limit} chars]"


def middle_trim(text: str, cap: int = ONE_LINE_LIMIT) -> str:
    """Trim the middle of long output; errors and summaries live at the end.

    The head and tail derive from the one per-line cap, so a tool-result body obeys
    the same number as every other row of the same view instead of the fixed 200
    and 120 it used to keep regardless. At the 200 default the split is exactly the
    200 and 120 it always was, so nothing moves unless a cap was asked for. A cap
    of 0 means no trimming, as everywhere else.
    """
    if cap <= 0:
        return text
    head, tail = cap, cap * MIDDLE_TAIL // MIDDLE_HEAD
    if len(text) <= head + tail:
        return text
    omitted = len(text) - head - tail
    return f"{text[:head]} ...[+{omitted} chars, middle]... {text[-tail:]}"


def instant(ts: str) -> datetime:
    """The UTC moment a recorded timestamp names; ValueError if it names none.

    A timestamp without a zone is read as UTC, the way both providers record
    them, and one with an offset is converted rather than having its offset
    discarded. This is the only place in the tool that reads a recorded
    timestamp: every sort, window and display goes through it, so a corpus
    cannot order one way and print another.
    """
    return _aware(datetime.fromisoformat(ts.replace(" ", "T")))


def _aware(when: datetime) -> datetime:
    """The same moment as an aware UTC datetime."""
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def _utc(ts: str) -> datetime | None:
    """instant(), or None for a missing or unreadable timestamp."""
    try:
        return instant(ts) if ts else None
    except (AttributeError, TypeError, ValueError):
        return None


def clock(ts: str) -> str:
    """HH:MM:SS UTC from an ISO timestamp, or blanks when there is none."""
    when = _utc(ts)
    return when.strftime("%H:%M:%S") if when else "--:--:--"


def day(ts: str) -> str:
    """YYYY-MM-DDTHH:MM:SSZ in real UTC, or empty string when there is none."""
    when = _utc(ts)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ") if when else ""


def date_of(ts: str) -> str:
    """The UTC calendar date of a timestamp, or empty string when there is none.

    Not `ts[:10]`: for a session recorded just after local midnight east of
    Greenwich, the recorded date and the UTC date are different days, and the
    UTC one is the day whose `--since`/`--before` window contains it.
    """
    when = _utc(ts)
    return when.strftime("%Y-%m-%d") if when else ""


def order_key(ts: str) -> datetime:
    """Chronological sort key; an unreadable timestamp sorts as the oldest.

    Sorting the recorded strings instead puts `2026-09-10T09:00:00+02:00` after
    `2026-09-10T08:00:00Z`, though it happened an hour earlier.
    """
    return _utc(ts) or datetime.min.replace(tzinfo=UTC)


def now_utc() -> datetime:
    """Current UTC time; the seam that lets live-label tests freeze the clock."""
    return datetime.now(UTC)


def is_live(ts: str) -> bool:
    """Is an event timestamp within LIVE_WINDOW_SECONDS of now, either way?

    Timestamps without a zone are read as UTC, the way both providers record
    them; unparseable or missing ones are simply not live.
    """
    stamp = _utc(ts)
    return stamp is not None and abs((now_utc() - stamp).total_seconds()) < LIVE_WINDOW_SECONDS


def live_mark(ts: str) -> str:
    """The '(live) ' title prefix for a session still being written, else ''."""
    return LIVE_MARK if is_live(ts) else ""


def human_num(n: int) -> str:
    """Compact count: 981, 45k, 1.2M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n // 1000}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k"
    return str(n)


def human_size(n: int) -> str:
    """Compact byte size: 210k, 5.8M."""
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f}M"
    if n >= 1024:
        return f"{n // 1024}k"
    return str(n)


def tab_row(*cells: object) -> str:
    """Join cells with single tabs; the unambiguous machine-readable layout."""
    return "\t".join(str(c) for c in cells)
