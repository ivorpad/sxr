# Ledger

One row per task. `state` is the only field a resuming agent has to trust;
everything else lives in [tasks.md](tasks.md) and the per-slice review notes.

States: `delivered` (implemented, verified, waiting on the reviewer),
`accepted`, `approved` (scoped, not started), `blocked`, `deferred`.

| Task | Title | Class | State | Evidence |
|---|---|---|---|---|
| SXR-CLI-01 | complete human prompts | intentional-behavior-change | **accepted 2026-09-11** by the originating reviewer | [review-slice-01.md](review-slice-01.md), [slice-01.patch](slice-01.patch), `evidence/` |
| SXR-CLI-02 | honor multi-session ranges in show, prompts, tools | defect | **accepted 2026-09-11** by the originating reviewer | [review-slice-02.md](review-slice-02.md), [slice-02.patch](slice-02.patch), `evidence-02/` |
| SXR-CLI-03 | one documented selection pipeline for show | intentional-behavior-change | **accepted 2026-09-11** by the originating reviewer | [review-slice-03.md](review-slice-03.md), [slice-03.patch](slice-03.patch), `evidence-03/` |
| SXR-CLI-04 | errors: source identity and complete text by default | intentional-behavior-change | **accepted 2026-09-11** by the originating reviewer | [review-slice-04.md](review-slice-04.md), [slice-04.patch](slice-04.patch), `evidence-04/` |
| SXR-CLI-05 | cmds: a filter no longer changes session scope | intentional-behavior-change | **accepted 2026-09-12** by the originating reviewer. Deferral lifted: it was pending the upstream reconciliation decision, which D-08 through D-11 and `SXR-MERGE-01` settled. The `cmds` substance was never in question — the defect it fixed is live in the published README — and its primer and version work was superseded by `SXR-HAZ-01` and the merge. | [review-slice-05.md](review-slice-05.md), [slice-05.patch](slice-05.patch), `evidence-05/` |
| SXR-HAZ-01 | init --write can no longer replace a newer primer with an older one (D-10) | hazard fix, not a slice | **delivered 2026-09-12** | [review-task-A.md](review-task-A.md), [task-A.patch](task-A.patch), `evidence-A/` |
| SXR-CLI-RECONCILE | adopt upstream's prompts session filtering, `--latest` and notices, under D-08 and D-09 | intentional-behavior-change | **delivered 2026-09-12** | [review-task-B.md](review-task-B.md), [task-B.patch](task-B.patch), `evidence-B/` |
| SXR-MERGE-01 | record the reconciliation in git history as a merge of the published releases (D-11) | history only, no file changed | **delivered 2026-09-12** | [review-task-M.md](review-task-M.md), `baseline-M/`, `evidence-M/` |
| SXR-AUDIT-02 | audit a second opinion's six findings against the merged tree, and record two upstream defects | correctness audit | **delivered 2026-09-12** | [review-task-M.md](review-task-M.md), `evidence-M/`, `disposition.json` |
| SXR-DOCS-01 | commit the audit trail's documents and reproducers, excluding snapshots and captures | record keeping, no behavior | **delivered 2026-09-12** as `f42b1ad`, with finding 6's wording as `b70f3ac` | [audit/README.md](../../README.md), `.gitignore`, `evidence-commit/` |
| SXR-CLI-06 | grep/cmds: valid JSON in every mode, one record per physical line | defect | **accepted 2026-09-12** by the originating reviewer (D-12 resolved with it) | [review-slice-06.md](review-slice-06.md), [slice-06.patch](slice-06.patch), `baseline-06/`, `evidence-slice-06/` |

## All five slices were built on a base three releases stale

Recorded 2026-09-12, after the fact and after measuring it. The handoff pinned
`HEAD 48b11c6c` and version `0.12.2`, and the 2026-09-10 command review was
captured against that tree. `origin/HEAD` is
`8f93114f8a1712cc7f02f2cfb91cf10d3040bb04`; local `HEAD` is an **ancestor** of
it, behind by 3 and ahead by 0, so the checkout is stale rather than diverged.
The three commits are the releases `v0.12.3` (`3280f00`), `v0.12.4` (`9f5fe09`)
and `v0.13.0` (`8f93114`): 13 files, +572 / -34, all of it about `prompts`.

Slices 1 through 5 therefore assumed a `prompts` command that the published
tool no longer has. The full assessment, with per-slice overlap verdicts, a
differential predicate probe, a three-way behavioral comparison and a
recommended strategy, is in
[upstream-reconciliation.md](upstream-reconciliation.md) with evidence in
`evidence-06/`. Two consequences that bind any later slice:

- **Do not run `sxr init --write` from this tree, in any repository.** Its
  0.14.0 primer stamp is higher than the published 0.13.0 primer while its
  prompts guidance is older, and `check_primer` compares only the stamp, so the
  rewrite silently deletes published instructions. Demonstrated in
  `evidence-06/primer-lineage.log`. **Closed 2026-09-12 by SXR-HAZ-01**: a write
  that would drop a documented flag or command, or overwrite a later stamp, now
  exits 2 without touching the file and needs `--force`; `init --check` reports
  the same condition and stops recommending the write. The primer body was also
  rebuilt on the published v0.13.0 body, so the guidance is no longer older.
  Before/after transcripts against the real published primer are in
  `evidence-A/primer-guard.log`.
- **Every baseline snapshot, evidence directory and patch in this folder is
  keyed to `48b11c6c`.** They remain valid as records of what was measured and
  decided; they are not diffs that still apply to the published tree. Since
  2026-09-12 the current commit is the merge `d2021d9`, whose tree is identical
  to `f806ede`, so a patch keyed to `48b11c6c` is still reproducible as
  `git diff 48b11c6c d2021d9 -- <paths>` for tracked files.

## How this tree relates to the published release, measured

Recorded 2026-09-12 from the findings audit, because the merge commit message
had to describe the relationship and "ahead by N commits" says nothing useful
about behavior. The preserved 67-check contract suite was run against three
trees, one fresh corpus per check, by
[probe_upstream_contracts.py](probe_upstream_contracts.py):

| Tree | Passed | Failed |
|---|---|---|
| `48b11c6c`, the audited base | 36 | 31 |
| `8f93114`, published v0.13.0 | 36 | 31 |
| this tree | 66 | 1 |

The published releases fixed **none** of the 17 audit findings: the base and the
published release fail the identical 31 checks. Exactly one check runs the other
way, `PROMPTS-filter`, which passes on both of them and fails here by design
under D-08. So the divergence this refactor introduces is one contract wide, and
the divergence it removes is thirty-one. Receipt:
`evidence-M/upstream-contracts.json`.

## Two defects in the published v0.13.0, recorded not fixed

Verified 2026-09-12 against `8f93114` in a scratch tree extracted with
`git archive`, read-only, never against this repository. The reviewer chose
verify-and-record; upstream's code is not changed here and nothing is published.
Recorded in `disposition.json` under `upstream_defects`.

- **`prompts --budget` is silently ignored without a selector.** `cli.prompts`
  calls `prompt_catalog(refs, parse, json_out, limit, line_cap)` and never passes
  `budget`, so bare `prompts`, `--budget 0` and `--budget 50` print
  byte-identical output. Confirmed behaviorally and in source
  (`evidence-M/upstream-defects.json`). Cannot reach this tree: the catalog path
  is not adopted, and `prompt_command.py` passes `budget` into `PromptOpts` on
  both paths.
- **`prompts -n` changes unit without saying so.** With two human sessions in
  scope, `-n 1` prints one *session row* and `# +1 more`, and `-n 2` prints both
  rows; a negative `-n` prints no rows and exits 0. That answers, by shipping,
  the `PAR-tools-typer-limit` question this ledger says no task may assume — may
  a limit change unit — in the affirmative. Confirmed
  (`evidence-M/limit-unit.json`). Cannot reach this tree: `-n` counts prompt
  records on every path here, and the question stays open above.

A third, smaller divergence found while measuring, recorded for completeness
rather than as a defect: on `8f93114` a bare `prompts --line-limit N` caps the
listing's first-prompt preview column unconditionally, with no budget involved
(measured at 10, 40 and 200), which is not what the flag documents.

Provenance, recorded at the reviewer's request. The coordinator concluded this
run had died and launched a second agent for the same assessment at 06:26 on
2026-09-12; this agent delivered at 06:46 while that one was working.
[upstream-reconciliation.md](upstream-reconciliation.md), `evidence-06/` and the
three `probe_*.py` scripts are this agent's work. The second agent's document is
kept separately as `upstream-reconciliation-second-opinion.md`, and the
coordinator's own account of what was overwritten and restored is in
`RECOVERY-NOTE.md`. Both were written by the coordinator, not by this run; the
restored assessment was spot-checked against eleven of its own measured claims
before being cited again.

Out-of-slice maintenance, reviewer-approved, recorded in
[maintenance-2026-09-11.patch](maintenance-2026-09-11.patch): the D-06 hazard fix
in two audit scripts, and the approved annotation of
`docs/session-search-hints-research.md`. Neither touches `src/` or `tests/`.
| SXR-CLI-08 | one timestamp parser for every sort, filter and format | defect | **delivered 2026-09-12** | [review-slice-08.md](review-slice-08.md), [slice-08.patch](slice-08.patch), `baseline-08/`, `evidence-slice-08/` |
| SXR-CLI-07 … 24 | see [tasks.md](tasks.md) | mixed | proposed | — |

**Queue order, resequenced 2026-09-12 (reviewer-approved): `SXR-CLI-08` runs
before `SXR-CLI-07`.** SXR-CLI-06 redefined `--sort`, `-l --json` and the
`--json` record unit, and SXR-CLI-07 redefines `-n 0` and `--all`; two
consecutive slices changing documented flag meanings makes a reader unable to
tell which migration note explains a behavior change. SXR-CLI-08 also has no
dependencies and is what makes `--sort started` correct, which SXR-CLI-07 keeps
using. The full sequence with the reason is in [tasks.md](tasks.md).

## Disposition coverage

All 408 CSV rows are mapped in [disposition.json](disposition.json) and
[disposition.md](disposition.md); a completeness check against the CSV is
recorded in the JSON (`checked_complete`). Tallies:

| Disposition | Rows |
|---|---|
| duplicate of a canonical row | 195 |
| scoped into a task | 138 |
| retain current behavior | 37 |
| deferred | 35 |
| decision needed | 3 |

The 3 rows needing a human decision are `PAR-tools-typer-limit`,
`PAR-secrets-clean-typer-json_out` and `EXTRA-017`; all three ask whether a
`--json` schema may grow, which no task may assume.

`PAR-tools-typer-limit` is the sharpest of the three: the CSV proposes that `-n`
cap the keys inside the `tools --json` aggregate, which directly contradicts
`SXR-AUD-007` ("JSON aggregate objects retain all fields"). One of the two has
to give, and the choice is the reviewer's, not a task's.

## Resolved decisions

Recorded only after the reviewer answered, never in anticipation. D-01 to D-03
were decided on accepting SXR-CLI-01 and all three confirm the behavior slice 01
already implemented; D-04 was decided on accepting SXR-CLI-02 and confirms the
behavior slice 02 already implemented. None required a code change; they are
recorded here so a later slice cannot silently reopen them.

| # | Decision | Resolution | Decider / date |
|---|---|---|---|
| D-01 | Precedence of `--all` against an explicit `-n` / `--budget` on `prompts` | **`--all` keeps overriding them.** Not last-flag-wins. Pinned by `tests/test_prompt_limits.py::test_all_overrides_explicit_limits` at both flag positions. | originating reviewer, 2026-09-11 |
| D-02 | Negative `--budget` / `--line-limit` | **Keep meaning "no trimming".** Not usage errors. The reasoning that rejecting them is a `show` change was accepted, so it moves to SXR-CLI-03 as an open question rather than being dropped. Pinned by `test_negative_character_limits_never_truncate`. | originating reviewer, 2026-09-11 |
| D-03 | Migration path for the `--all` semantic change | **README + `prompts --help` note is sufficient.** No stderr deprecation warning for `--all`. | originating reviewer, 2026-09-11 |
| D-04 | The per-session banner format in a range, and its duplication with `show`'s `file:` header line | **Keep the uniform `# session @N <short id> <file>` banner across `show`, `prompts` and `tools`, duplication included.** Consistency across the three commands wins. SXR-CLI-03 may revisit the duplication only as a consequence of reworking `show`'s header, and must not diverge the three banner formats to remove it. | originating reviewer, 2026-09-11 |
| D-05 | Negative `--budget` / `--line-limit` on `show` (raised as S-01 by SXR-CLI-03, inherited from D-02) | **Reject with exit 2, as SXR-CLI-03 implemented it.** `prompts` keeps D-02's "no trimming" meaning. The asymmetry is accepted deliberately: reopening D-02 would undo tested slice-1 behavior for no user-visible gain. Recorded in `contracts.md` so a later slice does not harmonize the two commands by accident. | originating reviewer, 2026-09-11 |
| D-06 | May a preserved 2026-09-10 audit script be edited to close a data-loss hazard? | **Yes, as a deliberate exception.** `audit/2026-09-10/verify_cli.py`'s `--output` defaulted into `evidence/contracts.json`, and one bare run destroyed the receipt there. `--output` is now required in that script and in `verify_prompts.py`, which had the same defect. Nothing else about either script changed; the 67-check suite runs identically (see below). | originating reviewer, 2026-09-11 |
| D-07 | Whether `cmds` may drop its implicit all-sessions `--grep` scope, given that the generated primer advertises it inside other repositories | **Yes, including a `PRIMER_BODY` reissue and a version bump.** Approved before SXR-CLI-05 started. Scope now comes from the selector alone and `--all-sessions` names the old reach. The bump turned out to be required for correctness, not ceremony: `init --check` compares only the version stamp, never the body, so a reissued primer under an unchanged stamp is reported "up to date" (measured in `evidence-05/primer-staleness.log`). | originating reviewer, 2026-09-11 |
| D-08 | Is `prompts` a read command or a discovery command? (open decision 6) | **A read command.** A bare `sxr prompts` prints complete human prompts, as slice 1 implemented and D-01/D-02 pinned. Upstream's session filtering, `--latest` and navigation notices are adopted; its default-to-listing is not. The recorded complaint was about reading, and a conversation catalog duplicates `sxr list`. The published 0.13.0 default is therefore deliberately reversed, and the migration is stated in `README.md`, in `prompts --help` and in the primer. | originating reviewer, 2026-09-12 |
| D-09 | Does upstream's synthesized `prompt_session` object become the default `prompts --json` output? | **No. Raw source records remain the `--json` contract.** A catalog projection, if it is ever worth keeping, needs its own flag or command and must be documented as a distinct schema, never replacing raw records. | originating reviewer, 2026-09-12 |
| D-11 | Commit the reconciliation as a rebase onto `8f93114` or as a merge? (open decision 7) | **A merge, so history records that 0.12.3, 0.12.4 and 0.13.0 happened and were reconciled rather than burying them.** Done 2026-09-12: `f806ede` carries the five slices and the hazard fix, and `d2021d9` merges `8f93114` into it with this tree's content as the resolution. The merge tree is byte-identical to `f806ede`'s, so the merge changed no file. Nothing is pushed. | originating reviewer, 2026-09-12 |
| D-13 | Is `--since @N` selecting a different set an acceptable consequence of SXR-CLI-08's corrected ordering? | **Accept it.** `@N` is documented as temporary and recomputed per invocation, `CMD-list-typer`'s own compatibility cell sanctions renumbering, and the alternative — resolving `@N` against the old string order for window bounds only — would let one handle name two different sessions in a single command line. A *literal* bound keeps exactly the sessions it always kept; only an `@N` bound moves. Recorded in `contracts.md` so a later slice does not "restore" the old numbering as a bug fix. | originating reviewer, 2026-09-12 |
| D-12 | Is `grep -l --json`'s `grep_session` object a projection D-09 permits, or an invented schema? | **Accept it as implemented.** It sits within D-09 rather than against it: the flag already existed, the schema is documented in `README.md` and `grep --help`, and it exposes nothing a caller could not already get from `list`. Recorded in `contracts.md` so a later slice neither "corrects" it back to raw records nor adds a match count, which would make `-l` and `-c` indistinguishable. | originating reviewer, 2026-09-12 |
| D-10 | Does the `init --write` primer hazard wait for the reconciliation slice? | **No, it goes first and on its own.** It can corrupt other repositories while it sits there. Delivered as SXR-HAZ-01 with its own patch and evidence, separate from the rebase. | originating reviewer, 2026-09-12 |

## Open decisions

1. **`--compact` as an explicit name for `prompts`** (`EXTRA-043`) is deferred:
   `--budget` and `--line-limit` already request compact prompts and one of them
   is required to get it. Revisit only if the reviewer wants a memorable alias.
   `errors` is different and did get `--compact` in SXR-CLI-04 (`EXTRA-041`),
   because it has no budget flag at all, so there was no other way to ask.
2. The three `decision-needed` CSV rows above (`tools --json` limit unit,
   `secrets clean --json` summary record) remain unanswered.
3. **Should `errors` and `show --errors` select the same records?** They do not:
   `errors` keeps `is_error` records only, while `show --errors` also keeps the
   *call* paired with a failed result (`tag == "err"`). SXR-CLI-04 left both
   sides alone because `CMD-errors-typer` says to keep the recorded property as
   the selection rule; unifying them would move counts and could move
   `ERRORS-api-error`. A later slice's call.
4. **Which version number the next release actually takes, and whether this
   checkout should be reconciled with the published history first.** SXR-CLI-05
   needed a version bump, and found that this working tree is behind what is
   published: `pyproject.toml` said `0.12.2`, while origin carries tags up to
   `v0.13.0` (`v0.12.3` and `v0.12.4` too, none of them present locally) and the
   Homebrew tap formula already points at the `v0.13.0` release assets. The slice
   took `0.14.0`, the next unused number, so the primer stamp moves and nothing
   collides with a published tag. But a `0.14.0` built from this tree would not
   contain whatever `0.12.3`, `0.12.4` and `0.13.0` shipped. Nothing is published
   by this slice, and `just release-check` would refuse anyway (dirty tree), so
   the number is provisional and the reconciliation is the reviewer's call.
   **Updated 2026-09-12:** the reviewer decided to hold `0.14.0` in place for
   now. The reconciliation half of this item is assessed in
   [upstream-reconciliation.md](upstream-reconciliation.md) and is now decision 6.
5. **Nothing tells an already-installed primer that it is stale.** After this
   slice, every repository carrying an older `<!-- sxr:primer -->` block keeps
   instructions the tool no longer honors until someone runs `sxr init --write`
   there by hand. `init --check` is the only detector, it must be pointed at the
   file, and it compares only the version stamp. This repository's own
   `CLAUDE.md` sat at `v0.3.0` — nine minor versions stale, still teaching
   `sxr cmds --grep "git push"  # ALL sessions, one call` — which is the evidence
   that the manual path does not get walked. Whether the tool should detect this
   (a body hash in the marker, or a check on other commands) is a design question
   this slice deliberately did not answer. **Updated 2026-09-12:** the stamp-only
   comparison is worse than "does not detect staleness". Because this tree's
   0.14.0 primer carries *older* prompts guidance than the published 0.13.0
   primer, `init --check` recommends a rewrite that loses information
   (`evidence-06/primer-lineage.log`). **Partly closed by SXR-HAZ-01
   (2026-09-12).** `check_primer` now compares the installed body as well as the
   stamp, so a block reissued under an unchanged version is reported rather than
   called up to date, and no write that would drop a documented surface is
   recommended or performed. What remains open is the *push* side: nothing tells
   an installed primer it is stale until someone runs `init --check` against that
   file, and no other command mentions it.
6. *Answered 2026-09-12 as D-08 and moved to the resolved table above.*
   `prompts` is a read command; upstream's session filtering, `--latest` and
   notices are adopted, its default-to-listing is not.
7. **Whether a released `0.14.0` should be cut from this reconciled tree.**
   *The history half of this item was answered 2026-09-12 as D-11 and is done:
   the reconciliation is now a merge commit.* What remains open is only whether
   and when a release is actually cut. Nothing is published and nothing is
   pushed; the version stays `0.14.0`.
8. *Answered 2026-09-12 as D-12 and moved to the resolved table above.* The
   `grep_session` projection stands as implemented, and `contracts.md` records
   its shape so a later slice does not undo it.

9. *Answered 2026-09-12 as D-13 and moved to the resolved table above.* The
   `--since @N` scope change stands; `contracts.md` keeps the literal-versus-`@N`
   distinction explicit so a later slice does not undo the numbering as a fix.
   The evidence and reasoning that produced the question are kept below.

   **Is `--since @N` selecting a different set an acceptable consequence of
   SXR-CLI-08?** The reviewer asked to be told if unifying the parser changed
   scope for an existing valid invocation. It does, in exactly one shape, and the
   before/after evidence is in `evidence-slice-08/scope-report.txt`: on both
   providers `--since @2` kept 4 of 4 sessions and now keeps 2, `--since @3` kept
   2 and now keeps 4, and `--before @2` kept 0 and now keeps 2. The window did
   not change — every *literal* bound keeps exactly the sessions it kept before,
   checked case by case — and neither did `_stamp`, which still resolves `@N` and
   takes that session's start. What changed is which session `@N` names, because
   the ordering is now chronological. My recommendation is to accept it, for
   three reasons: `@N` is documented as temporary and recomputed per invocation,
   so nothing durable pointed at the old numbering; the row's own compatibility
   cell already sanctions renumbering (`Corrected chronology can change @N
   numbering for offset-bearing records`); and the alternative — resolving `@N`
   against the old string order for window bounds only — would mean the same
   handle meant two different sessions in one command line. A corpus of `Z`-only
   timestamps, which is what both providers write today, is unaffected. The
   `README.md` migration note states all of this. Flagged rather than assumed
   because it is a scope change, not a display one.

## Known evidence gap: audit/2026-09-10/evidence/contracts.json

**What was lost.** That file held the original audit-time contract receipt, the
JSON sibling of `audit/2026-09-10/evidence/contracts.log`. The log is intact from
2026-09-10 10:52 and records **67 checks: 37 passed, 30 failed**. The JSON now
holds an unrelated later run — 66 passed, 1 failed (`PROMPTS-filter`),
`generated_at` 2026-09-11T11:57:12Z. The per-check JSON detail of the original
audit run (each check's `expected` text, `detail` message, `duration_seconds` and
`calls` receipt) is gone. Only the pass/fail line per check survives, in the log.

**What it was not.** It was *not* the post-remediation 67-passed/0-failed result.
That measurement is a different run and is intact in
`audit/2026-09-10/remediation/final-contracts.json` (2026-09-10 13:11). An
earlier report of mine cited that file as though it covered the loss; it does
not, and the two must not be conflated.

**When and how.** `verify_cli.py` defaulted `--output` to that path, so a bare
invocation overwrote it. The write is stamped 2026-09-11 13:57:12 local
(`generated_at` 11:57:12Z, matching the file mtime exactly). That is 12 minutes
after SXR-CLI-02's after-measurement (13:45:24 local) and 70 minutes before
SXR-CLI-03's baseline measurement (15:07:55 local), so it belongs to neither
slice. **It was the coordinating agent's own acceptance check**, which ran
`uv run python audit/2026-09-10/verify_cli.py` with no `--output` while
independently re-verifying SXR-CLI-02 (shell started 11:56:22Z, a second bare
run at 11:57). Every slice-2 and slice-3 `verify_cli.py` invocation did pass
`--output` explicitly.

**A second, milder instance.** `verify_prompts.py` had the same defaulting
defect, and a bare run at 15:38:52 local — again the coordinating agent's
acceptance check for SXR-CLI-03, not the slice itself — rewrote
`cli-refactor/evidence/migrated-contracts.json` (slice 1's receipt). Here nothing
substantive was lost: the file still records the same 5 checks with the same
5 `passed` statuses, and differs from slice 1's own run only in `generated_at`
and per-check `duration_seconds`. Its `.log` sibling is untouched from 06:10.

**Unrecoverable, confirmed four ways.** The file is untracked, so git has no
blob (`git log --all` and `git ls-files` both find nothing). None of the three
per-slice baseline snapshots contain any `audit/` path — verified by listing each
tarball. `tmutil listlocalsnapshots /` reports no APFS local snapshots. No other
file under `audit/` holds a 37-passed contract receipt. **No replacement JSON was
fabricated or reconstructed**, and none should be.

**Cause closed (D-06).** `--output` is now required in
`audit/2026-09-10/verify_cli.py` and in `cli-refactor/verify_prompts.py`; a bare
run exits 2 without writing anything. Proof, plus a before/after comparison
showing the 67-check suite unchanged, is in `evidence-04-prep/`. The residual
hazard that remains, unfixed and out of scope: the 2026-09-10 *generator* scripts
(`build_report.py`, `render_report.py`, `command-review/collect.py`,
`assemble.py`, `verify.py`) write their own products to hardcoded paths under
`audit/2026-09-10/`. That is their purpose rather than an output-flag default, but
rerunning any of them would still replace preserved evidence.

## Not started, visible on purpose

`EXTRA-055` (`--events-json`) and the other 34 deferred rows remain unfinished
scope, listed in `disposition.md` with a reason rather than dropped.
`EXTRA-073`/`EXTRA-074` (`--since`/`--before` after `prompts`) are scoped into
SXR-CLI-14, not deferred — `prompts` still rejects them today.
