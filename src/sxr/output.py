"""Count printed rows across a command without discarding record contents."""

import json
import sys
from dataclasses import dataclass


@dataclass
class RowBudget:
    """A command-wide row allowance; zero and None mean unlimited."""

    limit: int | None = None
    total: int = 0
    shown: int = 0

    def take(self, rows):
        """Count every row while yielding only the allowed prefix."""
        for row in rows:
            self.total += 1
            if not self.limit or self.shown < self.limit:
                self.shown += 1
                yield row

    def notice(self, label="rows", *, stderr=False):
        """Report the omitted count without mixing diagnostics into JSON or path output."""
        if self.shown < self.total:
            print(
                f"# +{self.total - self.shown} more {label} "
                f"(shown {self.shown} of {self.total}; raise -n, -n 0 for all)",
                file=sys.stderr if stderr else sys.stdout,
            )


def record_events(events):
    """Select one representative per physical record, preserving source order."""
    seen = set()
    for event in events:
        if event.seq not in seen:
            seen.add(event.seq)
            yield event


def print_records(events, limit, budget=None):
    """Print complete raw JSONL records, once each, with a bounded row count.

    Deduplication is per transcript, so a shared budget still counts every
    session's physical records exactly once. An inherited budget reports its
    omissions once for the whole scope instead of once per session.
    """
    own = budget is None
    budget = budget or RowBudget(limit)
    for event in budget.take(record_events(events)):
        print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
    if own:
        budget.notice("records", stderr=True)
