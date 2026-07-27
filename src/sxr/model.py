"""Session references and transcript events shared by providers and views."""

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

    @property
    def short_id(self) -> str:
        """Display prefix: 8 chars for Claude uuid4, 13 for Codex uuid7."""
        return self.id[:13] if self.provider == "codex" else self.id[:8]

    @property
    def label(self) -> str:
        """Best human handle: user-assigned name, else generated title."""
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
