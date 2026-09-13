"""Search selection and rendering options shared by indexed and direct scans.

The options also police themselves. `grep` has three output shapes -- match
rows, the -c table and the -l session list -- and each one ignores flags that
belong to the others. Accepting a flag and then producing a shape it cannot
describe is worse than refusing it, so the combinations are checked once, here,
before any transcript is read.
"""

from dataclasses import dataclass
from pathlib import Path

from sxr.handles import fail

SORTS = ("matches", "started")
METACHARS = "\\.^$*+?[]{}()|"


@dataclass
class GrepOpts:
    """Search flags plus a conservative set of candidate source files."""

    fixed: bool = False
    count: bool = False
    context: int = 0
    ignore_case: bool = False
    ids_only: bool = False
    include_all: bool = False
    sort: str | None = None
    json_out: bool = False
    limit: int | None = None
    budget: int | None = None
    candidates: set[Path] | None = None

    def events(self, ref, parse, *, summarize: bool = False):
        """Skip proven non-candidates; parse every possible match normally."""
        if self.candidates is not None and ref.path not in self.candidates:
            return []
        return ref.read(parse) if summarize else parse(ref.path)

    @property
    def order(self) -> str:
        """The -c ordering, with the default spelled rather than assumed."""
        return self.sort or SORTS[0]

    def check(self) -> None:
        """Reject flag pairs that describe two different output shapes.

        Each message names both flags and says which one to drop, because the
        user asked for something coherent in their head and the tool has to say
        which half it kept.
        """
        if self.sort is not None:
            if self.sort not in SORTS:
                fail(f"--sort takes {' or '.join(SORTS)}, not '{self.sort}'")
            if not self.count:
                fail("--sort orders the -c table; add -c, or drop --sort")
        if self.context < 0:
            fail(f"-C takes 0 or more events, not {self.context}; -C 0 prints no context")
        if self.count and self.ids_only:
            fail("-c ranks matching sessions and -l lists them; pick one")
        if self.count and self.context:
            fail("-c prints one row per session, so -C has no events to surround; drop one")
