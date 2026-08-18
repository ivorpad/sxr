"""The secrets audit: a masked rotation worklist across sessions.

Every row is a distinct secret identified by kind and salted fingerprint;
values never reach output in any mode, --json included, because sxr's own
stdout is recorded into the corpus it just audited. Rotation is the real
remediation; cleaning transcripts only stops re-propagation.
"""

import json
import sys
from dataclasses import dataclass, field
from typing import Annotated

import typer

from sxr import flags
from sxr.handles import resolve
from sxr.model import SessionRef
from sxr.secrets import fingerprint, scan_text
from sxr.secrets.detect import SEVERITIES
from sxr.util import tab_row

CandidatesF = Annotated[
    bool,
    typer.Option("--candidates", help="Include high-entropy review candidates (noisy)"),
]


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


def secrets_cmd(
    ctx: typer.Context,
    arg: flags.Arg = None,
    candidates: CandidatesF = False,
    since: flags.SinceF = None,
    before: flags.BeforeF = None,
    use_codex: flags.CodexF = False,
    use_claude: flags.ClaudeF = False,
    path: flags.PathF = None,
    json_out: flags.JsonF = False,
    limit: flags.LimitF = None,
) -> None:
    """Audit sessions for leaked keys and passwords, masked; a rotation worklist.

    With no session arg the whole directory scope is scanned. Output is one
    row per distinct secret (kind, salted fingerprint, spread); the value
    itself is never printed, in --json mode included.
    """
    provider, cwd, json_out, limit = flags.merge(ctx, use_codex, use_claude, path, json_out, limit)
    sessions = flags.sessions(ctx, provider, cwd, since, before)
    refs = sessions if arg is None else resolve(arg, sessions)
    raise typer.Exit(secrets_view(refs, provider.parse, candidates, json_out, limit))
