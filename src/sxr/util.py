"""Formatting helpers: truncation, timestamps, human numbers, tab rows."""

ONE_LINE_LIMIT = 100
MIDDLE_HEAD = 200
MIDDLE_TAIL = 120


def one_line(text: str, limit: int = ONE_LINE_LIMIT) -> str:
    """Flatten to one line; trim the tail with an explicit recovery marker."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
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
