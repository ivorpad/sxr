# evidence-A: the primer downgrade hazard, closed (D-10)

A bounded hazard fix, not a slice. It stops this tree's `sxr init --write` from
silently replacing a newer installed primer with an older one, and stops
`init --check` from recommending that write.

| File | What it records |
|---|---|
| `primer-guard.log` | The hazard reproduced against the real published v0.13.0 primer, before and after, plus `--force` and a legitimate refresh. Produced by `../capture_primer_guard.py --output evidence-A/primer-guard.log` |
| `historical-contracts.json`, `.log` | `audit/2026-09-10/verify_cli.py --output …`: 66 passed, 1 failed (`PROMPTS-filter`, failing by design since slice 1) |
| `migrated-contracts.json`, `.log` | `../verify_prompts.py --output …`: 5 passed, 0 failed |

## What the reproduction shows

The published primer body is rendered from `origin/HEAD` with `git show` into a
temp module, so nothing is checked out. The fixture is a scratch `AGENTS.md`
with local prose above and below the block.

Before, in a tree extracted from `HEAD 48b11c6c`: `init --check` printed
`primer v0.13.0 installed …, binary is v0.12.2; run sxr init --write`, the write
succeeded, and `--latest still documented: False` — the guidance was gone.

After, in this tree: `init --check` names the loss and says to leave it alone or
use `--force`; `init --write` exits 2 with `file changed: False`. `--force`
still works and still keeps both prose lines. A refresh from an older primer
that documents nothing this body lacks is replaced normally, then reported up to
date, and a second write leaves the file byte-identical.

## Measurements

Taken after the change, in this order: `pytest` 923 passed (903 before, plus 20
in `tests/test_primer_guard.py`); `ruff check` clean; `ruff format --check` 179
files; `konpy validate` valid; `konpy check` 106 files, 0 violations, no
suppressions. Both contract suites were run with an explicit `--output`, and a
per-check-id comparison against `evidence-05/` shows **no check changing
status**.

`src/sxr/onboard.py` is 285 lines and `src/sxr/primer_text.py` 138, both under
the 300-line limit; `tests/test_primer_guard.py` is 216, under 400.

## A coordination note about this patch's bounds

`baseline-A/` was snapshotted at 06:45, before the coordinator restored the
first reconciliation assessment over the second agent's copy at 07:01. Three
paths in that snapshot therefore changed without this task touching them, and
are excluded from `task-A.patch` so the diff is only this work:
`upstream-reconciliation.md`, `upstream-reconciliation-second-opinion.md` and
`RECOVERY-NOTE.md`. `baseline-A/`'s own metadata files are excluded for the same
reason — they were written after `files.txt` was enumerated.
