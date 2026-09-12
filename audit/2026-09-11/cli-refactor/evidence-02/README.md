# SXR-CLI-02 evidence — baseline, defect reproduction, implementation, verification

Two agents worked this slice in the same working tree on 2026-09-11. This
directory now holds both contributions, reconciled. Read "Concurrency" last if
you only want the result.

## Pre-edit baseline, measured 2026-09-11 13:29–13:33

Snapshot of the tree at that moment: `../baseline-02/` (108 tracked and
untracked files, `sha256.txt`, `files.txt`, `git-status.txt`, `head.txt`,
`tracked-vs-head.patch`, `worktree-snapshot.tar.gz`). HEAD was
`48b11c6cf08200de363e108924e42fdbc52d83e8`; the tree was dirty with 46 entries.
The snapshot was verified byte-identical to the tree before use, which is
independent confirmation that no source or test file changed between the end of
slice 1 and the start of this work.

| Check | Command | Result | File |
|---|---|---|---|
| Tests | `uv run pytest -q` | 676 passed, 0 failed, exit 0 | `baseline-pytest.log`, `baseline-pytest.xml` |
| Lint | `uv run ruff check .` | exit 0 | `baseline-lint.log` |
| Format | `uv run ruff format --check .` | exit 0, 147 files | `baseline-format.log` |
| Conventions | `uv run konpy validate` | exit 0 | `baseline-konpy-validate.log` |
| Conventions | `uv run konpy check` | exit 0, 98 files, 0 violations | `baseline-konpy-check.log` |
| Historical CLI contracts | `uv run python audit/2026-09-10/verify_cli.py` | exit 1 — 66 passed, 1 failed (`PROMPTS-filter`) | `baseline-historical-contracts.log`, `.json` |
| Migrated prompt contracts | `uv run python verify_prompts.py` | exit 0 — 5 of 5 | `baseline-migrated-contracts.log` |

`PROMPTS-filter` was already failing before this slice began: it is the
intentional break SXR-CLI-01 documented and the reviewer accepted. It is a
baseline failure, not a regression, and its status did not change in this slice.

## Defect reproduction and fix, `before/` and `after/`

`before/` and `after/` each hold 28 captures, one file per invocation, recording
argv, exit code, stdout and stderr. Both were produced by `../capture_ranges.py`
against the synthetic two-session corpora `../fixture_ranges.py` builds: two
Claude sessions and two Codex rollouts written into a temporary root with
`CLAUDE_CONFIG_DIR`, `CODEX_HOME` and `SXR_CACHE_DIR` redirected into it. No
live session data is read and `/opt/homebrew/bin/sxr` is never invoked.

`before/` was captured from the unmodified tree. It was then **independently
reproduced** from `../baseline-02/worktree-snapshot.tar.gz` (extracted to a
clean directory whose 108 file hashes all matched `baseline-02/sha256.txt`, then
imported ahead of the project source): all 28 captures came out byte-identical.
See `before-reproduction.log`. So `before/` is verifiably the pre-slice
behavior, not a mid-edit snapshot.

The defect, established by byte comparison rather than by reading the source:

| Comparison in `before/` | Result |
|---|---|
| `claude-show-single.txt` vs `claude-show-range.txt` | identical |
| `claude-prompts-single.txt` vs `claude-prompts-range.txt` | identical |
| `claude-tools-single.txt` vs `claude-tools-range.txt` | identical |

`sxr show/prompts/tools @1:@2` produced exactly the output of `@1` alone: the
second session was discarded with no notice on either stream, exit 0. The same
held for Codex and for the inverted `@2:@1`, which `handles.resolve` normalizes
and the views then truncated identically.

`before-after-index.txt` lists every case as CHANGED or UNCHANGED. The seven
UNCHANGED cases are the compatibility guarantee of this slice:

| Unchanged case | What it pins |
|---|---|
| `claude-show-single`, `claude-prompts-single`, `claude-tools-single` | a single `@N` invocation is byte-identical |
| `claude-prompts-range-self` | `@2:@2`, a range naming one session, is byte-identical to `@2` |
| `claude-show-range-overrun` | `@1:@5` still exits 2 with `@5 out of range; 2 sessions in scope` |
| `claude-list`, `codex-list` | discovery and the list view are untouched |

Every other case changed, and every change is a session that used to be
discarded now appearing under its own `# session @N  <id>  <file>` banner.

## Post-implementation verification

| Check | Command | Result | File |
|---|---|---|---|
| Tests | `uv run pytest -q` | 745 passed, 0 failed, exit 0 | `after-pytest.log`, `after-pytest.xml` |
| Lint | `uv run ruff check .` | exit 0 | `lint.log` |
| Format | `uv run ruff format --check .` | exit 0, 152 files at the time of the run (153 after this directory's own docs were added) | `format.log` |
| Conventions | `uv run konpy validate` | exit 0 | `konpy-validate.log` |
| Conventions | `uv run konpy check` | exit 0, 100 files, 0 violations | `konpy-check.log` |
| Historical CLI contracts | `uv run python audit/2026-09-10/verify_cli.py` | exit 1 — 66 passed, 1 failed (`PROMPTS-filter`), unchanged from baseline | `historical-contracts.log`, `.json` |
| Migrated prompt contracts | `uv run python verify_prompts.py` | exit 0 — 5 of 5 | `migrated-contracts.log`, `.json` |
| Range captures | `uv run python ../capture_ranges.py after` | 28 of 28 captured | `after-capture.log` |

676 → 745 tests is the 69 cases of `tests/test_session_range.py`. No test was
weakened, renamed away or skipped.

`demo-before-*.txt` are an earlier, smaller two-session reproduction kept
because it is the first recorded evidence of the defect in this slice.

## Concurrency

Two agents were assigned SXR-CLI-02 and both wrote here. One measured the
baseline, built `fixture_ranges.py` / `capture_ranges.py`, captured `before/`,
detected the other's concurrent source edits and stopped without implementing.
The other implemented the fix (`src/sxr/session_scope.py`,
`tests/test_session_range.py`, and the changes in `../slice-02.patch`).

The two contributions were reconciled rather than one being discarded:

- No source or test file was written by both. `src/` and `tests/` edits came
  only from the implementing run; `fixture_ranges.py`, `capture_ranges.py`,
  `before/` and the `baseline-*` logs came only from the capturing run.
- The capturing run's `before/` was re-derived from the verified baseline
  snapshot and matched byte-for-byte, so it is trustworthy as a pre-fix
  reference even though it was written while the other edits were in flight.
- `fixture_ranges.py` and `capture_ranges.py` needed `ruff format` to make the
  repository's format check pass again; the reformat was verified to leave both
  files' parse trees identical, so no content was altered.
