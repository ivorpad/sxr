# evidence-slice-06 — SXR-CLI-06

`grep`/`cmds`: valid JSON in every mode, one record per physical line.
Measured 2026-09-12 on `HEAD` `f42b1ad`, with `baseline-06/` as the starting
tree. Named `evidence-slice-06` because `evidence-06/` is already the upstream
reconciliation assessment's.

## Gates

| Check | Before this slice | After |
|---|---|---|
| `pytest` | 951 passed, 0 failed | **996 passed, 0 failed** (`pytest.log`, `pytest.xml`) |
| `ruff check .` | exit 0 | exit 0 (`ruff-check.log`) |
| `ruff format --check .` | 195 files | 200 files, exit 0 (`ruff-format.log`) |
| `konpy check` | 109 files, 0 violations | 111 files, 0 violations, no suppressions (`konpy.log`) |
| `verify_cli.py` (2026-09-10, 67 checks) | 66 passed, `PROMPTS-filter` failed | **unchanged**: 66 passed, `PROMPTS-filter` failed (`historical-contracts.{log,json}`) |
| `verify_prompts.py` (migrated) | 5 passed | **unchanged**: 5 passed, 0 failed (`migrated-contracts.{log,json}`) |

The 45 new tests are `tests/test_grep_modes.py`. `PROMPTS-filter` has failed by
design since SXR-CLI-01 and D-08; nothing in this slice touches it.

The baseline column is measured on the `baseline-06/` tree, the format figure by
extracting its snapshot and running ruff there. That figure is ruff's own summary
number and is larger than the count of `.py` files on disk, so it is reported as
ruff prints it rather than reconciled to a file list; both runs exit 0.

## Before/after captures

`before/` and `after/` hold 92 cases each: 36 `grep` and 10 `cmds` cases on both
providers, written by `capture_grep.py` over `fixture_grep.py`. Each file records
the invocation, the exit code, stdout and stderr, and every `--json` case also
records whether every stdout line parses.

- **58 of 92 byte-identical.** The 34 that changed are listed in `changed.txt`.
- **JSON validity: 6 cases emitted non-JSON on stdout before, 0 after.** Those
  six were `grep -l --json`, `--files-with-matches --json` and `-l --json -n 1`
  on both providers.
- Every changed case is one of: raw-JSON deduplication (Claude only), the new
  `grep_session` identity objects, a mode conflict now exiting 2, the `--budget`
  note under `-c`, or `--help` text.

The Claude and Codex halves diverge on purpose. Claude yields one event per
content block, so one physical line carrying two matching blocks was printed
twice; Codex yields one event per record and could not duplicate. Every
`grep-codex-*json*` and `cmds-codex-*json*` raw case is byte-identical.

## Earlier slices preserved

`recaptures/` re-runs the four earlier harnesses and compares against
`evidence-B/recaptures/`, the set verified at the merge:

| Harness | Byte-identical |
|---|---|
| `capture_ranges.py` (SXR-CLI-02) | 28 of 28 |
| `capture_show.py` (SXR-CLI-03) | 48 of 48 |
| `capture_errors.py` (SXR-CLI-04) | 38 of 38 |
| `capture_cmds.py` (SXR-CLI-05) | 42 of 44 |

The two differences are `cmds --help` on each provider, and the whole difference
is the two sentences added to the `cmds` docstring about the `--json` record
unit. No `cmds` output changed: slice 5's fixture records one tool call per line,
so it has nothing to deduplicate.

## Tree integrity

`integrity.log` checks all 1434 paths in `baseline-06/sha256.txt`: 1427 OK, 7
changed, 0 missing. The 7 are exactly the files this slice edits. `grep_counts.py`
and `test_grep_modes.py` are new, so they are absent from that manifest by
construction.
