# SXR-CLI-05 evidence: `cmds` scope, and the primer reissue

Every command here ran through `uv run` in this checkout. The installed
`/opt/homebrew/bin/sxr` was read once, to establish which versions are already
published, and never invoked as the tool under test.

## Baseline, measured before any edit

Tree recorded in `../baseline-05/` (130 files including `CLAUDE.md` and
`docs/`, `sha256.txt`, `worktree-snapshot.tar.gz`, HEAD `48b11c6c`).

| gate | result |
| --- | --- |
| `baseline-pytest.log` / `.xml` | 863 passed, 0 failed |
| `baseline-lint.log` | ruff check clean |
| `baseline-format.log` | 164 files already formatted |
| `baseline-konpy-validate.log` | configuration valid |
| `baseline-konpy-check.log` | 103 files, 0 violations |
| `baseline-historical-contracts.{log,json}` | 66 passed, 1 failed (`PROMPTS-filter`) |
| `baseline-migrated-contracts.{log,json}` | 5 passed, 0 failed |

## After the change

| gate | result |
| --- | --- |
| `after-pytest.log` / `.xml` | 903 passed, 0 failed (40 new, all in `tests/test_cmds_scope.py`) |
| `lint.log` | ruff check clean |
| `format.log` | 169 files already formatted |
| `konpy-validate.log` | configuration valid |
| `konpy-check.log` | 104 files, 0 violations, no suppressions added |
| `historical-contracts.{log,json}` | 66 passed, 1 failed — same ids, no status change |
| `migrated-contracts.{log,json}` | 5 passed, 0 failed — same ids, no status change |

Both contract suites were invoked with an explicit `--output` into this
directory, as D-06 now requires.

## Compatibility captures

`before/` and `after/` hold 44 invocations each (22 cases × 2 providers),
captured by `../capture_cmds.py` from `../fixture_cmds.py`. `before/` imports
`sxr` from the hash-verified baseline snapshot at `/tmp/sxr-b05`; `after/` from
the working tree. `before-after-index.txt` classifies every case: **24 are
byte-identical**, 20 changed with a named reason, none unexplained. Re-running
the `after/` capture reproduced all 44 files byte for byte.

The 20 changed cases are only these three groups:

* four `--all-sessions` cases per provider, where the flag did not exist before
  (exit 2 → 0, and one deliberate usage error);
* five defaulted-scope `--grep` cases per provider, which is the fix itself;
* `--help`, which now lists `--all-sessions`.

Every case that named its own scope — `@1`, `@2`, `@1:@2`, with or without
`--grep` — is byte-identical, including `--json` and the negative-limit usage
error.

## Slices 1 through 4, re-verified against their own references

| recheck | reference | result |
| --- | --- | --- |
| `errors-recheck/` (38) | `../evidence-04/after/` | 38 identical, 0 changed |
| `show-recheck/` (48) | `../evidence-04/show-recheck/` | 48 identical, 0 changed |
| `ranges-recheck/` (28) | `../evidence-04/ranges-recheck/` | 28 identical, 0 changed |

`show-recheck/` is also 48/48 identical to `../evidence-03/after/`.
`ranges-recheck/` differs from `../evidence-02/after/` in the same six files
slice 3 changed and slice 4 recorded; comparing against slice 4's own recheck is
what isolates this slice.

## Primer investigation

`primer-staleness.log` records what happens to an already-installed primer when
the version stamp moves, measured rather than reasoned:

* `sxr init --check FILE` is the only detector, and it compares **only the
  version stamp** — a primer whose body was edited under a matching stamp is
  reported "up to date", exit 0.
* nothing else in `src/sxr/` calls `check_primer`; no other command warns, and
  there is no automatic re-render.
* a bare `sxr init --check` in this repository exits 1 saying "no AGENTS.md
  found", because the default target is `AGENTS.md` and this repo keeps its
  primer in `CLAUDE.md`.
* `sxr init --write FILE` is the refresh path. It replaces only the marker span
  and leaves surrounding prose intact.
