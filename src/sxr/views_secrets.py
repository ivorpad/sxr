"""The secrets audit: a masked rotation worklist across sessions.

Every row is a distinct secret identified by kind and salted fingerprint;
values never reach output in any mode, --json included, because sxr's own
stdout is recorded into the corpus it just audited. Rotation is the real
remediation; cleaning transcripts only stops re-propagation.
"""

import json
import sys
from dataclasses import dataclass, field

from sxr.model import SessionRef
from sxr.secrets import fingerprint, scan_text
from sxr.secrets.detect import SEVERITIES
from sxr.util import tab_row


@dataclass
class _Tally:
    """Aggregate for one distinct secret across the scanned scope."""

    kind: str
    severity: str
    sessions: set = field(default_factory=set)
    hits: int = 0
    first: str = ""


def secrets_view(
    refs: list[SessionRef], parse, candidates: bool, json_out: bool, limit: int | None
) -> int:
    """Scan the scope's events and print the masked worklist; exit 1 if clean."""
    tallies: dict[str, _Tally] = {}
    for ref in refs:
        for event in parse(ref.path):
            for f in scan_text(event.text, candidates):
                tally = tallies.setdefault(fingerprint(f.value), _Tally(f.kind, f.severity))
                tally.sessions.add(ref.short_id)
                tally.hits += 1
                tally.first = tally.first or f"{ref.short_id}:{event.seq}"
    rows = sorted(tallies.items(), key=lambda kv: (SEVERITIES.index(kv[1].severity), -kv[1].hits))
    if limit:
        rows = rows[:limit]
    if json_out:
        for fp, t in rows:
            print(
                json.dumps(
                    {
                        "type": "secret",
                        "fingerprint": fp,
                        "kind": t.kind,
                        "severity": t.severity,
                        "sessions": sorted(t.sessions),
                        "hits": t.hits,
                        "first": t.first,
                    }
                )
            )
        return 0 if rows else 1
    if not rows:
        scope = f"{len(refs)} session(s)"
        hint = "" if candidates else "; --candidates widens the net"
        print(f"no secrets detected in {scope}{hint}", file=sys.stderr)
        return 1
    print(tab_row("# kind", "severity", "fingerprint", "sessions", "hits", "first"))
    for fp, t in rows:
        print(tab_row(t.kind, t.severity, fp, len(t.sessions), t.hits, t.first))
    certain = sum(1 for _, t in rows if t.severity == "certain")
    print(
        f"# {len(rows)} distinct secrets ({certain} certain); values never printed. "
        "Rotate certain ones first; zoom: sxr show <id> --around <seq>"
    )
    return 0
