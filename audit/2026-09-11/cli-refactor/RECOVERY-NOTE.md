# Recovery note: two reconciliation assessments, 2026-09-12

Written by the coordinating agent, not by a slice. Records a coordination error
and what was recovered, so neither document is mistaken for the other later.

## What happened

The coordinator wrongly concluded that the agent assigned the upstream
reconciliation assessment had died, because nothing had been written to the repo
for thirteen hours. A second agent was launched for the same task at 06:26. The
first agent then delivered at 06:46, while the second was still working.

Both wrote `upstream-reconciliation.md`. The second agent's blind `Write` landed
last, so the first agent's document was overwritten and lost from disk. It was
untracked, so git had no blob and no snapshot existed.

## What was recovered, and how

The first agent's document was reconstructed from its own session transcript by
replaying the recorded `Write` (26261 chars) followed by the single recorded
`StrReplace` (unique match), giving 26459 bytes / 436 lines. It is
self-consistent and complete: it ends with its evidence table and refers to
`evidence-06/` eighteen times.

- `upstream-reconciliation.md` — the **first** agent's assessment, restored as
  above. This is the document `ledger.md` was written against and the one whose
  `evidence-06/` artifacts exist on disk.
- `upstream-reconciliation-second-opinion.md` — the **second** agent's
  assessment, 35227 bytes / 586 lines, preserved verbatim as it was found on
  disk. It cites no `evidence-06/` paths because it built its own scratch
  evidence outside the repository, which was removed on interrupt.

Nothing else was damaged. The second agent's one attempted `ledger.md` edit
failed because the row it targeted had already been rewritten, so the ledger is
the first agent's. `evidence-06/` and the three `probe_*.py` scripts were never
touched by the second agent, and nothing under `audit/2026-09-10/` was written.

## Why both are kept

They agree on every conclusion but were measured independently, and the second
is materially richer in several places — a larger CSV staleness count, two
upstream defects in the catalog path, the observation that upstream is missing
the entire seventeen-finding remediation, and per-suite scores across the two
trees. Treat the first as the assessment of record and the second as an
independent corroboration whose extra findings are live input to the
reconciliation work.
