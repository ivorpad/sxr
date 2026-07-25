"""Formatting helpers: truncation, timestamps, human numbers, tab rows.

Trim sizes are defaults, not policy: flags override env vars override these
(SXR_LINE_LIMIT, SXR_BUDGET; 0 disables trimming entirely).
"""

import os

ONE_LINE_LIMIT = 200
MIDDLE_HEAD = 200
MIDDLE_TAIL = 120
SCAN_BUDGET_CHARS = 40_000


def _env_int(name: str, default: int) -> int:
    """Integer env override, falling back to the default on absence/garbage."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


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


def middle_trim(text: str, head: int = MIDDLE_HEAD, tail: int = MIDDLE_TAIL) -> str:
    """Trim the middle of long output; errors and summaries live at the end."""
    if len(text) <= head + tail:
        return text
    omitted = len(text) - head - tail
    return f"{text[:head]} ...[+{omitted} chars, middle]... {text[-tail:]}"


def clock(ts: str) -> str:
    """HH:MM:SS from an ISO timestamp, or blanks when missing."""
    return ts[11:19] if len(ts) >= 19 else "--:--:--"


def day(ts: str) -> str:
    """YYYY-MM-DDTHH:MM:SSZ from an ISO timestamp, or empty string."""
    return f"{ts[:19]}Z" if len(ts) >= 19 else ""


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
