"""Session references and transcript events shared by providers and views."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionRef:
    """A discovered session: identity, location, and list-view metadata."""

    provider: str
    id: str
    path: Path
    cwd: str = ""
    started: str = ""
    ended: str = ""
    title: str = ""
    name: str = ""
    kind: str = ""
    model: str = ""
    messages: int = 0
    errors: int = 0
    tokens: int = 0
    size_bytes: int = 0
    extra: dict[str, Any] = field(default_factory=dict)
    _summary_loader: Callable | None = field(default=None, repr=False, compare=False)

    def summarize(self, events: list["Event"] | None = None) -> None:
        """Load display metadata once, reusing already parsed events when available."""
        if self._summary_loader is not None:
            self._summary_loader(events)
            self._summary_loader = None

    def read(self, parse: Callable) -> list["Event"]:
        """Read this transcript and derive its summary from the same records."""
        events = parse(self.path)
        self.summarize(events)
        return events

    @property
    def short_id(self) -> str:
        """Display prefix: 8 chars for Claude uuid4, 13 for Codex uuid7."""
        if self.extra.get("display_id"):
            return self.extra["display_id"]
        if "/" in self.id:
            return self.id
        return self.id[:13] if self.provider == "codex" else self.id[:8]

    @property
    def label(self) -> str:
        """Best human handle: user-assigned name, else generated title."""
        self.summarize()
        return self.name or self.title


@dataclass
class Event:
    """One transcript event; seq is the record's order in the file (1-based)."""

    seq: int
    ts: str
    role: str
    kind: str
    text: str = ""
    tool: str = ""
    is_error: bool = False
    tag: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
