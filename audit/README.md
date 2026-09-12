# Audit trail

Two engagements against this CLI, kept because the reasoning is worth more than
the diffs:

- **`2026-09-10/`** — a full audit: 17 findings, a 408-row before/after review of
  every command, flag and proposal (`command-review/commands-before-after.csv`),
  and a preserved 67-check CLI contract suite (`verify_cli.py`,
  `contract_checks.py`) that any later change can be re-run against.
- **`2026-09-11/cli-refactor/`** — the staged refactor that acted on it. One
  review packet per slice, a decisions ledger, and the reconciliation with three
  releases (`v0.12.3`, `v0.12.4`, `v0.13.0`) that had shipped while the work was
  in flight.

Start with [`2026-09-11/cli-refactor/ledger.md`](2026-09-11/cli-refactor/ledger.md):
it holds the task table, every resolved decision with who decided it and when,
and the decisions still open.

## What is tracked here, and what is not

Tracked: the documents and the reproducers. Every review packet, the ledger, the
review CSV and its machine-readable siblings, the per-slice patches, and every
`verify_*.py`, `probe_*.py`, `capture_*.py` and `fixture_*.py` script. A reader
should be able to reconstruct *why* each decision was made and *what* was
verified, and re-run any of it.

Not tracked (see the `audit/` section of `.gitignore`):

| Excluded | Why |
|---|---|
| `baseline*/` | Whole-tree snapshots, eight `.tar.gz` files totalling about 19 MB. Each one captured a tree that is now in this repository's history. |
| `evidence*/` except its `README.md` | Roughly a thousand captured command outputs and run logs. Regenerable by the `capture_*.py` and `verify_*.py` scripts, which are tracked. Each directory's `README.md` is kept, because it says what was measured and what the numbers were. |
| `*-after-sha256.txt` | Per-file hash manifests of a tree that is now a commit. |
| `pytest*.xml`, `__pycache__/` | Machine receipts and build artifacts. |

**Dangling evidence paths are expected.** The packets cite paths inside
`baseline*/` and `evidence*/` because those files existed, and were verified,
when the packet was written. They are simply not carried in git. Where a number
matters, the evidence directory's own `README.md` repeats it, and the command
that produced it is in the packet. Nothing was deleted to make this commit: the
excluded files are still on disk in the working tree where the work happened.
