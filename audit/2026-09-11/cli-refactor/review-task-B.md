# Review packet — SXR-CLI-RECONCILE: adopt upstream's prompts work under D-08 and D-09

Delivered 2026-09-12. `HEAD` is still `48b11c6c`, nothing committed, no stashes.

## 1. Rows, and a before/after invocation

Six surfaces published in `v0.12.3`–`v0.13.0` have no row in the 408-row CSV,
because the review predates them. They are recorded in `disposition.json` under
`upstream_rows`, outside `dispositions` so that map still matches the CSV
id-for-id and still passes its completeness assertion:
`UP-prompts-typer-latest`, `-default-session`, `-navigation`, `-empty-scope`
(all `task:SXR-CLI-RECONCILE`, delivered), `-catalog` (`rejected:D-08`) and
`-catalog-json` (`rejected:D-09`). Six existing rows had their notes corrected —
`CMD-prompts-typer`, `PAR-prompts-typer-arg`, `-json_out`, `-include_all`,
`-limit`, `-file` — because the error is in their `before` cells, which describe
the audited base rather than the published surface. The CSV itself is not edited;
its SHA-256 is unchanged and re-asserted.

The behavior change, in a scope whose newest session is a subagent transcript and
whose second-newest has no human input:

```
before   $ sxr --codex prompts --path /w
         #0001  12:01:00  user   text    "subagent ask"
         # 1 of 1 human prompts shown

after    $ sxr --codex prompts --path /w
         # prompts: @3 01999991-… (skipped 2 newer empty or background sessions)
         # sessions: env CODEX_HOME=… sxr --codex --path /w list
         #0002  12:01:00  user   text    "real human ask"
         # 1 of 1 human prompts shown
```

Both notice lines are on stderr, so the rows on stdout are unchanged in shape.

## 2. The bounded diff

`task-B.patch`, 3193 lines, +2788 / −77 across 21 files. Ten are not evidence:

| File | Change |
|---|---|
| `src/sxr/prompt_selection.py` | new, 92 lines. Upstream's `human_sessions`, `prompt_session`, `prompt_navigation`, kept close to its shape |
| `src/sxr/prompt_command.py` | new, 61 lines. The `prompts` command, moved out of `cli.py` the way `show` already is |
| `tests/test_prompt_sessions.py` | new, 297 lines, 28 cases, adapted from upstream's module |
| `src/sxr/cli.py` | 312 → 264 lines: `prompts` registered rather than defined |
| `src/sxr/navigation.py` | upstream's `scope_command`, applied mechanically |
| `src/sxr/primer_text.py` | primer teaches `--latest` and the reading default |
| `packaging/verify.py` | bundle checks for the new default; one stale `--all` assertion fixed |
| `README.md`, `CLAUDE.md` | the D-08 migration and `--latest` |
| `tests/test_primer_guard.py` | fixture flag repointed, see §4 |

Taken against `baseline-B/worktree-snapshot.tar.gz` (1045 files), whose restore
was rehearsed before anything was touched: 1045 extracted, 1045 hashes verified,
0 failures. `evidence-B/recaptures/` (158 files of verbatim re-run output) is
excluded from the patch and compared programmatically instead.
sha256 `5ecee4c949253727…`.

## 3. How it was done, and what was run

The reconciled tree was built in `/tmp/recon`, outside the repository, from the
snapshot. The full suite passed there (951) before ten files were copied into the
working tree. No git index, checkout, merge, rebase or stash operation was
performed at any point; `git rev-parse HEAD` is `48b11c6c` and `git stash list`
is empty.

**The 11 rejected hunks, resolved deliberately.** The measured conflict set was
`README.md` 2, `pyproject.toml` 1, `src/sxr/__init__.py` 1, `src/sxr/cli.py` 2,
`src/sxr/onboard.py` 2, `src/sxr/views_read.py` 2, `uv.lock` 1.

| Hunk | Resolution and why |
|---|---|
| `pyproject.toml`, `__init__.py`, `uv.lock` (3) | **Skipped.** The version stays `0.14.0`; the reviewer is holding that question |
| `src/sxr/views_read.py` (2) | **Already satisfied.** Upstream removes `_prompt_record` and rewires `prompts` there; slice 1 had already moved both into `views_prompts.py`, so there was nothing left to change. Verified by grep: no `_prompt_record` and no `prompts` in `views_read.py` |
| `src/sxr/cli.py` (2) | **Taken, adapted.** `--latest` and the session-selection call adopted; upstream's catalog branch and its `--all needs a session ID` guard not adopted, both being consequences of the listing default D-08 rejects |
| `src/sxr/onboard.py` (2) | **Taken, adapted.** Help-text only. The primer body now teaches `--latest` and the reading default; the text lives in `primer_text.py` since Task A |
| `README.md` (2) | **Taken, adapted.** `--latest` and session filtering documented; upstream's catalog paragraphs replaced with the D-08 migration statement |

Two files upstream changed were **not** adopted at all:
`origin/HEAD:src/sxr/prompt_catalog.py`, the catalog itself, which therefore does
not exist in this tree (D-08); and `tests/test_file_selection.py`, whose two added
lines exist only because a bare `prompts` stopped reading — under D-08 it still
reads, so the original assertions hold unchanged.

Verified after copying back:

| Check | Result |
|---|---|
| `uv run pytest` | **951 passed** (923 after Task A, plus 28) |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | 183 files formatted |
| `uv run konpy validate` / `check` | valid; 109 files, 0 violations |
| `konpy: ignore` added | none |
| `verify_cli.py --output evidence-B/historical-contracts.json` | 66 passed, 1 failed |
| `verify_prompts.py --output evidence-B/migrated-contracts.json` | **5 passed, 0 failed** |
| per-check comparison against `evidence-A/` | **no historical contract changed status** |
| slice 3, 4, 5 recaptures | byte-identical to `evidence-03/04/05-after` |
| slice 2 recapture | 6 of 28 files differ, and identically before this work — see below |
| user's tree | 1045 snapshot files re-hashed: 0 missing, 7 changed, all 7 intended |
| module lengths | largest source 288 (`views_grep.py`), largest test 376; all under limits |

**The slice-2 drift is not from this work.** Re-capturing from the
pre-reconciliation snapshot produces the same 6 differences, and that recapture
is byte-identical to this one. Both differences are slice 3 reaching output slice
2 had already recorded: the hidden-rows hint now reads `--tool-results` instead of
`--tools`, and an empty selection now says which `--type` matched nothing. Worth
noting as a pre-existing inconsistency in slice 2's stored evidence rather than a
regression.

Not run: the packaged-bundle build. `packaging/verify.py` is updated and lints
clean, but it only executes inside a bundle build, which is out of scope here.
While updating it I found a **pre-existing** stale assertion at its old line 125:
it asserted that `prompts --all` includes injected context, which slice 1 changed
and `PROMPTS-all-keeps-selection` pins the other way. That assertion would have
failed on the next bundle build; it now checks `--include-context` instead and
asserts `--all` does *not* widen.

## 4. Compatibility, deviations, limits

- **The published 0.13.0 default is deliberately reversed.** A bare `sxr prompts`
  reads; it does not list. Stated in `README.md` (a two-part migration
  paragraph), in `prompts --help`, and in the primer, as D-08 requires.
- **`--latest` is accepted but redundant**, byte-identical to the bare form on
  both streams, because the default already reads the newest human conversation.
  Kept for compatibility with scripts written against 0.13.0. It is rejected with
  exit 2 alongside an id, a range or `--file`.
- **`--json` is unchanged**, per D-09: original records, never a projection.
  Pinned by a test that also asserts `prompt_session`, `first_prompt` and
  `follow_up` appear nowhere in the output.
- **Two deviations from upstream's notices.** The `# sessions:` line points at
  `list` rather than `prompts`, because `prompts` reads here, so the command that
  shows the skipped sessions is the session list. And an explicitly selected
  session — id, range or `--file` — prints no notice at all, matching `show`,
  `cmds` and `errors`; upstream printed `# prompts: <id> (--file)`.
- **Four of upstream's test expectations were corrected, not weakened.** Its
  module encodes upstream's `--all`, which both lifts limits and widens
  selection. Here `--all` lifts limits and `--include-context` widens, which is
  slice 1's design, D-01's precedence and the `PROMPTS-all-keeps-selection`
  contract. So: `--include-context` was added to the parametrized default case
  and the injected-context assertion keyed to it; reading an
  instructions-only session uses `--include-context` rather than `--all`; the
  `--all needs a session ID` case was dropped as a consequence of the listing
  default; and the `--file` notice case was inverted to assert silence. Its 22
  session-filtering cases are unchanged in substance.
- **One Task A test fixture was repointed.** The guard tests used `--latest` as
  their example of a lost surface; this work documents `--latest`, so the guard
  correctly stops refusing. The fixture now uses a synthetic flag, and the test
  that pinned the gap now asserts it is closed — which is a stronger check.
- **Still open:** whether to commit this, and as a rebase onto `8f93114` or a
  merge. The tree carries upstream's improvements but git does not know it;
  recorded as open decision 7.

## 5. Ledger, and the next slice

`ledger.md` records SXR-HAZ-01 and SXR-CLI-RECONCILE as delivered, adds D-08,
D-09 and D-10 to the resolved table, moves open decision 6 to D-08, marks open
decision 5 half-closed, adds open decision 7, and records at the reviewer's
request that `upstream-reconciliation.md`, `evidence-06/` and the three
`probe_*.py` scripts are this run's work.

Stopping here, as instructed. SXR-CLI-06 is not started. The natural next step,
once the reviewer accepts these two packets, is SXR-CLI-06 on a tree that now
matches the published product surface.
