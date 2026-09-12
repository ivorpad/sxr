# SXR-CLI-03 evidence

Everything here was produced by `uv run` against this checkout. The installed
`/opt/homebrew/bin/sxr` was never invoked. Every transcript read is synthetic and
written into a temporary directory by `fixture_show.py` or `fixture_ranges.py`;
no real session was read, and no secret value appears in any capture.

## Baseline, measured before any edit

`../baseline-03/` holds the pre-edit tree: `files.txt` (110 paths),
`sha256.txt`, `worktree-snapshot.tar.gz`, `head.txt`, `git-status.txt` (48
entries) and `tracked-vs-head.patch`. Slice 1's `../baseline/` and slice 2's
`../baseline-02/` were not touched; their snapshot hashes are recorded in
`../review-slice-03.md`.

| file | command | result |
|---|---|---|
| `baseline-pytest.log` / `.xml` | `uv run pytest -q` | 745 passed, 0 failed |
| `baseline-lint.log` | `uv run ruff check .` | exit 0 |
| `baseline-format.log` | `uv run ruff format --check .` | exit 0, 153 files |
| `baseline-konpy-validate.log` | `uv run konpy validate` | exit 0 |
| `baseline-konpy-check.log` | `uv run konpy check` | 100 files, 0 violations |
| `baseline-historical-contracts.{log,json}` | `audit/2026-09-10/verify_cli.py` | 66 passed, 1 failed (`PROMPTS-filter`) |
| `baseline-migrated-contracts.{log,json}` | `verify_prompts.py` | 5 passed, 0 failed |

## After the change

| file | command | result |
|---|---|---|
| `after-pytest.log` / `.xml` | `uv run pytest -q` | 825 passed, 0 failed (+80 new) |
| `lint.log` | `uv run ruff check .` | exit 0 |
| `format.log` | `uv run ruff format --check .` | exit 0, 159 files |
| `konpy-validate.log` | `uv run konpy validate` | exit 0 |
| `konpy-check.log` | `uv run konpy check` | 102 files, 0 violations |
| `historical-contracts.{log,json}` | `audit/2026-09-10/verify_cli.py` | 66 passed, 1 failed (`PROMPTS-filter`) |
| `migrated-contracts.{log,json}` | `verify_prompts.py` | 5 passed, 0 failed |

`PROMPTS-filter` fails at both measurements, for the reason it has failed since
slice 1: it asserts the pre-slice-1 meaning of `prompts --all`. **No historical
contract changed status in this slice.**

## Compatibility by capture

`before/` and `after/` hold the same 48 `show` invocations, one file each,
recording argv, exit code, stdout and stderr with the temporary directory
rewritten to `<TMP>`. `before/` was captured by running `capture_show.py` with
`sys.path` pointed at `../baseline-03/worktree-snapshot.tar.gz` extracted into
`/tmp/sxr-b03`, after confirming all 110 extracted files hash-match
`../baseline-03/sha256.txt`. `after-capture.log` is the after run.

`before-after-index.txt` marks each case UNCHANGED or CHANGED and gives the
reason for every change: 17 unchanged, 31 changed, all intended.

## Slice 2 re-verified

`ranges-after/` is `capture_ranges.py` rerun under this slice, and
`slice-02-still-green.txt` compares it case by case to `../evidence-02/after/`:
22 of 28 byte-identical, and the 6 that differ do so only by the renamed
`--tool-results` flag in `show`'s hidden-kind note plus, in one case, the new
empty-selection notice on stderr. `ranges-capture.log` is that run's log.

## Not run

No bundle build, packaging check or relocation test: no entry point, dependency
or packaging file was touched, and `packaging/verify.py` already carries
unrelated uncommitted edits from earlier remediation. Nothing was published,
installed or released. Linux and x86_64 are unavailable on this machine.
Command surfaces other than `show` were exercised only through the test suite
and the 67-check historical contract suite.
