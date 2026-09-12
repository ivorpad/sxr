# SXR-CLI-04 evidence

Every file here was produced by a command that ran; nothing is transcribed from
an earlier slice. Baseline files were written before any source edit, the rest
after the last one.

## Baseline, measured before editing

| File | Command | Result |
|---|---|---|
| `baseline-pytest.{log,xml}` | `uv run pytest -q` | 825 passed, 0 failed |
| `baseline-lint.log` | `uv run ruff check .` | clean |
| `baseline-format.log` | `uv run ruff format --check .` | 159 files formatted |
| `baseline-konpy-validate.log` | `uv run konpy validate` | exit 0 |
| `baseline-konpy-check.log` | `uv run konpy check` | 102 files, 0 violations |
| `baseline-historical-contracts.{log,json}` | `verify_cli.py` | 66 passed, 1 failed (`PROMPTS-filter`) |
| `baseline-migrated-contracts.{log,json}` | `verify_prompts.py` | 5 passed, 0 failed |

The starting tree itself is `../baseline-04/`, hash-listed in its `sha256.txt`
and unpacked to `/tmp/sxr-b04` for the before-captures. Its `NOTE.txt` records
that this is the first per-slice snapshot to actually contain `docs/`: that
directory is gitignored, so the recipe's `git ls-files -o --exclude-standard
docs` returned nothing for slices 1 to 3 and their snapshots hold no docs file.

## After the change

| File | Command | Result |
|---|---|---|
| `after-pytest.{log,xml}` | `uv run pytest -q` | 863 passed, 0 failed (38 new) |
| `lint.log` | `uv run ruff check .` | clean |
| `format.log` | `uv run ruff format --check .` | 164 files formatted (ruff also formats code blocks in the markdown written for this slice) |
| `konpy-validate.log` | `uv run konpy validate` | exit 0 |
| `konpy-check.log` | `uv run konpy check` | 103 files, 0 violations |
| `historical-contracts.{log,json}` | `verify_cli.py` | 66 passed, 1 failed (`PROMPTS-filter`) |
| `migrated-contracts.{log,json}` | `verify_prompts.py` | 5 passed, 0 failed |

Both contract suites carry the same check ids before and after, and **no check
changed status**: `PROMPTS-filter` was already failing at the baseline, by the
design recorded in D-02, and everything else passes in both runs.

## Compatibility by capture

`before/` and `after/` hold 38 `sxr errors` invocations each, 19 per provider,
captured by `../capture_errors.py` — `before/` with `--source /tmp/sxr-b04`, so
it exercises the baseline source, `after/` against the working tree.
`before-after-index.txt` names which are byte-identical and gives a reason for
each one that changed.

## Slices 1 to 3 still green

| File | What it re-runs | Result |
|---|---|---|
| `show-recheck/`, `show-recheck.log` | `capture_show.py`, slice 3's 48 cases | 48 of 48 byte-identical to `evidence-03/after/` |
| `ranges-recheck/`, `ranges-recheck.log` | `capture_ranges.py`, slice 2's 28 cases | 28 of 28 byte-identical to `evidence-03/ranges-after/` |

The six range cases that differ from `evidence-02/after/` are slice 3's flag
rename and its one added stderr notice, not slice 4's: measured against slice 3's
own recheck directory, all 28 reproduce exactly.

## Hazard fix receipts

`../evidence-04-prep/` holds the D-06 evidence: both scripts refusing a bare run
(exit 2, nothing written), and a `verify_cli.py` run through the new required
`--output` whose 67 result lines are byte-identical to slice 3's.
