"""Search selection and rendering options shared by indexed and direct scans."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GrepOpts:
    """Search flags plus a conservative set of candidate source files."""

    fixed: bool = False
    count: bool = False
    context: int = 0
    ignore_case: bool = False
    ids_only: bool = False
    include_all: bool = False
    sort: str = "matches"
    json_out: bool = False
    limit: int | None = None
    budget: int | None = None
    candidates: set[Path] | None = None

    def events(self, ref, parse, *, summarize: bool = False):
        """Skip proven non-candidates; parse every possible match normally."""
        if self.candidates is not None and ref.path not in self.candidates:
            return []
        return ref.read(parse) if summarize else parse(ref.path)
