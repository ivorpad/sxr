# Baseline, measured 2026-09-11 before any edit

Everything below was measured in this checkout, not carried over from the
2026-09-10 reports. The working tree already contained substantial uncommitted
remediation work; nothing was stashed, reset, reverted or committed.

## Source identity

| Fact | Value |
|---|---|
| HEAD | `48b11c6cf08200de363e108924e42fdbc52d83e8` ("fix: exclude injected context from prompts") |
| Package version | 0.12.2 |
| Working tree | dirty: 24 modified tracked files, 18 untracked paths (see `baseline/git-status.txt`) |
| Command-review CSV | `audit/2026-09-10/command-review/commands-before-after.csv`, SHA-256 `c24d00ed08a09caed659c8ab3298db0b2b1166fa97f204742447f3662b1f63e4` — matches the handoff |
| Python | 3.14.2 via `uv` |

`HEAD` predates the remediation work, so a diff against `HEAD` does not isolate
any new contribution. The starting working tree is therefore captured
byte-for-byte:

- `baseline/worktree-snapshot.tar.gz` — every tracked and untracked file under
  `src/`, `tests/`, `docs/`, `packaging/`, plus `README.md`, `CLAUDE.md`,
  `konpy.json`, `pyproject.toml`, `justfile` (106 files).
- `baseline/sha256.txt` — SHA-256 of each of those files.
- `baseline/files.txt` — the file list.
- `baseline/git-status.txt`, `baseline/head.txt`, `baseline/tracked-vs-head.patch`.

To reproduce a slice's bounded diff: extract the snapshot to a scratch
directory and `diff -ruN <scratch> <same file list from the current tree>`.

## Measured check state at baseline

| Check | Command | Result | Evidence |
|---|---|---|---|
| Tests | `uv run pytest -q` | **642 collected, 8 failed, 0 errors** | `evidence/baseline-pytest.log`, `evidence/baseline-pytest.xml` |
| Lint | `uv run ruff check` | pass (exit 0) | `evidence/baseline-lint.log` |
| Format | `uv run ruff format --check` | pass (exit 0) | `evidence/baseline-format.log` |
| Conventions | `konpy check` | pass, 96 files, 0 violations | `evidence/baseline-konpy-check.log` |
| CLI contracts | `audit/2026-09-10/verify_cli.py` | not run at baseline; see note | — |

The 8 baseline failures are all in `tests/test_prompt_defaults.py`, the
interrupted proposal tests (`EXTRA-021`). They are exactly the 8 failures the
2026-09-10 report recorded, so the baseline is the state that report describes.
No other test failed.

The historical "632 passing tests" figure is superseded: this tree collects 642.

Lint and format were measured against the extracted baseline snapshot so the
numbers describe the starting tree, not the edited one (101 files there versus
139 in the live tree, because the live run also covers `audit/` scripts).

## Scope isolation used by behavioral tests

`tests/conftest.py` already redirects `SXR_CACHE_DIR` into each test's
`tmp_path` and clears `SXR_NO_CACHE`. All prompt tests read synthetic
transcripts through `--file`, so no live session data or shared cache is
consulted. The installed `/opt/homebrew/bin/sxr` was never invoked; every
observation in this directory ran the checkout through `uv run`.
