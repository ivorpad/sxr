# Upstream reconciliation assessment

Slices 1 through 5 were built on a base three releases behind the published
history. This document measures the overlap, says which of the two `prompts`
designs is better on which axis, estimates how much of the 2026-09-10 command
review is stale, and recommends a reconciliation strategy.

Nothing here changed the repository. No merge, rebase, cherry-pick, reset,
checkout or version edit was performed. Upstream code was run by extracting
refs with `git archive` into temp directories outside the repository; the two
probe scripts in this directory do the same and clean up after themselves.
Verified after the investigation: `HEAD` is still `48b11c6c`, there are no
stashes, 35 tracked files remain modified, and `src/sxr/__init__.py` still
reads `0.14.0`.

## The divergence, measured independently

Confirmed with `git rev-parse`, `git merge-base --is-ancestor`, `git log` and
`git diff --stat`:

- `HEAD` = `48b11c6cf08200de363e108924e42fdbc52d83e8`.
- `origin/HEAD` = `origin/main` = `8f93114f8a1712cc7f02f2cfb91cf10d3040bb04`.
- `HEAD` is an ancestor of `origin/HEAD`: behind by 3, ahead by 0. Not diverged.
- `3280f00` carries tag `v0.12.3`, `9f5fe09` carries `v0.12.4`, `8f93114`
  carries `v0.13.0`.
- Aggregate: 13 files, +572 / -34.

All three commits are about one command. `src/sxr/cli.py`'s four upstream hunks
sit at lines 10 (two imports), 99, 111 and 113; the `prompts` function spans
lines 95 to 119 at `HEAD`, with `errors` starting at 120. `navigation.command`
is byte-identical between the two refs — upstream only *added* `scope_command`
beside it. `onboard.py`'s changes are help text only. So **upstream changed no
command's behavior except `prompts`**, and that is checkable from the hunk
offsets rather than taken on faith.

## What upstream actually did

`3280f00` (0.12.3) stopped bare `prompts` reading whatever session happened to
be newest. It added `human_sessions`, which skips refs whose `kind` is `agent`,
`subagent` or `guardian_review`, or which carry a `parent_id` /
`parent_thread_id`, and skips sessions with no human records; and
`prompt_session`, which honors an explicit id or `--file` but otherwise walks
to the newest session that actually contains human prompts.

`9f5fe09` (0.12.4) added `prompt_navigation`, which prints `# prompts: @N <id>
(skipped N newer empty or background sessions)` and `# sessions: <command>` to
**stderr**, plus `navigation.scope_command`.

`8f93114` (0.13.0) changed the default: bare `prompts` now prints a table of
human conversations (`prompt_catalog`), added `--latest` to read the newest
human conversation, and made `--all` a usage error without a selection.

The predicate did not change. `_prompt_record` was **moved verbatim** from
`views_read.py` into `prompt_selection.py`: the removed block and the new one
are byte-identical (`cmp` on the extracted functions).

## 1. Overlap and conflict, slice by slice

| Slice | Upstream touched the same code? | The same behavior? | Verdict |
| --- | --- | --- | --- |
| 1 — prompts completeness and `--include-context` | Yes: `views_read.prompts`, `cli.prompts`, `README.md`, `onboard.py` | Yes, the same command, different axis | **Genuine conflict** on `--all`, and on what a bare `prompts` prints |
| 2 — session ranges and per-session identity | Partly: `cli.prompts` selection, and identity output for `prompts` | Overlapping intent, different mechanism and stream | **Overlaps, does not conflict**; upstream has no range support |
| 3 — `show` selection pipeline | No | No | **No overlap** |
| 4 — `errors` view | No | No | **No overlap** |
| 5 — `cmds --all-sessions`, primer reissue, version bump | Yes: `onboard.py` (`PRIMER_BODY` and `EPILOG`), `README.md`, and the version files | The primer text and the version number | **Conflict in the primer, and the version bump is actively harmful as it stands** |

### Slice 1 versus `prompt_selection.py` and `prompt_catalog.py`

These solve **different halves of the same complaint** and collide on one flag.

- Record selection: no conflict at all. My `views_prompts.human_prompt` and
  upstream's `_prompt_record` are the same predicate (see section 2), and
  upstream's copy is the one that was already at `HEAD`.
- Session selection: upstream fixed something slice 1 did not touch. On a
  synthetic Codex corpus whose newest two sessions are a subagent session and a
  context-only session, bare `prompts` reads the **subagent** session at `HEAD`
  and in this tree, and skips both upstream
  (`evidence-06/prompts-three-way.log`, case `bare`).
- Default output: hard conflict. Slice 1's contract is "a plain `sxr prompts`
  prints complete human prompts". Upstream's plain `sxr prompts` prints a
  session table and reads nothing. Those are different commands, not different
  formatting.
- `--all`: hard conflict. Slice 1 redefined it as "lift presentation limits,
  selection unchanged", moving context inclusion to `--include-context`.
  Upstream kept `--all` = "include injected context and tool results" and
  additionally made it require a selection. Measured: `prompts @3 --all` emits
  the injected record at `HEAD` and upstream, and does not in this tree.
- Flag names do not collide. The option surfaces are `HEAD` plus
  `--include-context` (mine, 17 options) and `HEAD` plus `--latest` (upstream,
  17 options) — `evidence-06/prompts-option-surface.log`.

### Slice 2's banners versus `9f5fe09`'s navigation

Different streams and different jobs, so they coexist mechanically but overlap
in message.

- Slice 2 prints `# session @N  <short id>  <path>` on **stdout** (on stderr
  under `--json`), once per session in a range, to make each block attributable.
- Upstream prints `# prompts: @N <id> (skipped …)` and `# sessions: <command>`
  on **stderr**, once, to explain which single session it chose.
- Upstream's `prompts` still reads one session: `prompt_session` returns a
  single ref. In the range case `prompts @3:@4`, this tree prints 7 stdout lines
  with per-session banners; `HEAD` and upstream print 3, having silently
  dropped `@4`. Slice 2's range work therefore remains entirely unimplemented
  upstream, and EXTRA-004's "then take [0]" description is still accurate for
  upstream.
- Cost of combining them: upstream's `prompt_handle` / `prompt_skipped` extras
  and slice 2's `session_scope.render` both want to own the "which session is
  this" line. That is a merge of two notice designs, not a code conflict.

### Slice 5's primer versus upstream's primer

This is the one place where the current state is not merely stale but harmful.
Both edited `PRIMER_BODY` and `EPILOG`, and the version stamp that gates
refreshes is now higher on the tree carrying the *older* prompts guidance.

Demonstrated in `evidence-06/primer-lineage.log` against a scratch `AGENTS.md`
holding the published v0.13.0 primer:

```
$ sxr init --check AGENTS.md     # this tree, 0.14.0
primer v0.13.0 installed in AGENTS.md, binary is v0.14.0; run sxr init --write
$ sxr init --write AGENTS.md
replaced primer v0.14.0 in AGENTS.md
```

The rewrite deletes upstream's three published lines about bare `prompts`,
`prompts @N` and `prompts --latest`, and stamps the result 0.14.0. Because
`check_primer` compares the stamp only, nothing afterwards reports the loss.
So this tree's `init --write` is a silent downgrade for any repository that
already has the published primer, and `init --check` actively recommends it.

Full text of both divergences is in `evidence-06/primer-bodies.log`:
`PRIMER_BODY` differs in three hunks (62 upstream lines versus 60 here);
`EPILOG` differs substantially in both directions, since slices 2 through 4
rewrote the same paragraphs upstream rewrote.

## 2. Whose human-prompt detection is better

**Neither. They are the same predicate**, and the interesting difference is one
level up, in session selection, where upstream is better.

`audit/2026-09-11/cli-refactor/probe_prompt_predicates.py` imports upstream's
module from `git show origin/HEAD:src/sxr/prompt_selection.py` and runs both
predicates over 23 record shapes: Claude plain user text, `isMeta`,
`isCompactSummary`, `isMeta: false`, a tool-result record in a text session; and
Codex `user.text`, `user.image`, `environment_context`, `user_instructions`, a
hooks label, a tool-output label, user-label-first and user-label-last mixtures,
an empty `content_item_kinds`, an all-non-string list, a mixed-type list, a
non-list value, a missing key, an unlabelled legacy record, a payload-free
record, `user.text` overridden by `isMeta`, and a kind mismatch. The predicate's
`kind` argument is the session-wide prompt kind, so it is passed separately from
the event's own kind; otherwise the `event.kind != kind` rejection is never
exercised.

Result: **23 cases, 0 divergences** (`evidence-06/prompt-predicates.log`). The
extracted function bodies are byte-identical, so this is confirmation rather
than luck. My only change was to factor the label lookup into
`_content_item_kinds`, which returns `None` for "unlabelled" and a
string-filtered list otherwise; upstream filters non-strings inline. Both treat
an empty or all-non-string list as not-human and a missing or non-list value as
human, so the refactor is behavior-preserving.

Neither has a bug the other avoids. Where they differ in capability:

- Mine adds `context_label`, so `--include-context` can name each hidden
  record's provenance (`compact`, `meta`, the first content-item kind, or a
  fallback of `tool_result` / `context`) without inferring authorship from
  wording. Upstream has no equivalent because it has no `--include-context`.
- Upstream adds session-level filtering: `human_sessions` skips agent,
  subagent and `guardian_review` refs, refs with a parent, and sessions with no
  human records. **This is strictly better than anything in slices 1 through 5**
  and fixes a real failure mode that my work leaves in place: bare `prompts`
  reading a subagent transcript, verified above.

## 3. Which slices are redundant, partial, or still needed

| Slice | Status after upstream |
| --- | --- |
| 1 | **Partially superseded, and partially still the only fix.** Its record-selection half is a no-op relative to upstream. Its completeness half and `--include-context` exist nowhere upstream. Its default-output claim is contradicted by upstream's default. |
| 2 | **Still needed, unimplemented upstream.** Ranges for `prompts`, `show`, `tools`; shared row allowance; per-session banners. Upstream still drops all but the first ref. |
| 3 | **Still needed, untouched upstream.** |
| 4 | **Still needed, untouched upstream.** |
| 5 | **Still needed for `cmds`; its primer and version halves must be redone** on top of upstream's primer (see the lineage regression above). Upstream's README still carries `sxr cmds --grep "git push"   # commands that did X, across all sessions`, so the defect slice 5 fixed is live in the published release. |

### Does upstream satisfy the original complaint?

The recorded complaint had two halves: `prompts --codex @2 --all` returned
non-human material, and getting complete prompts required `-n 0 --budget 0`.

- Half one, **not fixed** upstream. `--all` still means "include injected
  context and tool results"; upstream only forbids it without a selection.
- Half two, **not fixed** upstream. Running my five migrated contracts against
  each tree (`probe_contracts_vs_upstream.py`) shows
  `PROMPTS-default-complete` — no `SXR_BUDGET` / `SXR_LINE_LIMIT` may trim the
  default text view — **failing on both `HEAD` and upstream**, and passing only
  here.
- Upstream fixes a third facet neither the complaint nor the audit named: the
  session chosen. If the newest session is a subagent or empty rollout, `@2`
  and bare `prompts` were pointing at the wrong transcript.

So the two efforts are complementary on substance and incompatible on one flag.

### Does upstream's default-listing change conflict with slice 1's default?

Yes, directly, and it is the largest single decision in this document. Slice 1's
premise is that `prompts` is a read command whose default should be complete.
Upstream's premise is that `prompts` is a discovery command whose default should
be a list, with reading behind `@N` or `--latest`. Both are defensible; they
cannot both be the default. Measured on the same corpus
(`evidence-06/prompts-three-way.log`):

| Invocation | HEAD | this tree | upstream |
| --- | --- | --- | --- |
| `prompts` | reads newest (a subagent) | reads newest (a subagent) | session table, 2 of 4 sessions listed |
| `prompts --json` | raw records | raw records | `prompt_session` metadata objects |
| `prompts --all` | reads, widened | reads, limits lifted | exit 2, usage error |
| `prompts @3 --all` | +injected record | no injected record | +injected record |
| `prompts --latest` | exit 2, unknown option | exit 2, unknown option | reads newest human session |
| `prompts @3:@4` | 1 session | 2 sessions with banners | 1 session |

## 4. What the audit and the handoff got wrong

The handoff pinned `HEAD 48b11c6c` and version 0.12.2, and the command review
was captured against that tree, so every `before` cell describes a tree that is
now three releases old. Two concrete errors follow.

**The version was already taken.** The handoff's premise that the next release
is 0.12.3 or 0.13.0 was wrong before slice 1 started; both are published, and
0.13.0's content is upstream's prompts work.

**The `prompts` surface is under-described.** The CSV has 408 rows, of which 27
have a `prompts` command surface. No row anywhere in the file mentions
`--latest`, and none proposes a session listing or catalog (searched the
`after`, `item`, `example_after` and `problem` columns). The audit therefore has
no row for upstream's largest new surface: the bare-prompts catalog, `--latest`,
the `prompt_session` JSON schema, the stderr navigation notices, or the
subagent/empty-session skipping rules. Those are roughly four to six rows that
need to *exist*, which no re-verification of existing rows would surface.

### What I sampled, and what I found

I did not re-check all 408 rows. I sampled deliberately:

1. **All 27 rows with a `prompts` surface**, by id, reading their
   `default_before`, `before`, `after`, `default_after` and `compatibility`
   cells against upstream's measured behavior.
2. **The 11 most load-bearing of those** in full (`CMD-prompts-typer`,
   `PAR-prompts-typer-arg`, `-include_all`, `-json_out`, `-limit`, `-file`,
   `EXTRA-003`, `EXTRA-004`, `EXTRA-006`, `EXTRA-040`, `EXTRA-055`).
3. **A structural check instead of a row-by-row sweep for the other 381**: the
   212 rows whose `source` column names a file upstream changed are dominated by
   `cli.py`, which every command's row cites. Rather than reading them, I
   located upstream's `cli.py` hunks (lines 10, 99, 111, 113) inside the
   `prompts` function's span (95–119) and confirmed `navigation.command` is
   byte-identical. No other command's behavior moved, so those rows are stale
   only where they quote primer or README text.

Classification of the 27:

- **Stale, `before` cell now wrong**: 3 rows, 4 cells.
  `CMD-prompts-typer.default_before` ("Newest session. All human-selected
  rows.") and its `before` (the default prints rows);
  `PAR-prompts-typer-arg.before` ("Newest session by default");
  `PAR-prompts-typer-json_out.before` ("Complete original source JSONL objects")
  — true for `@N --json`, false for the bare form.
- **Incomplete rather than wrong**: 3. `PAR-prompts-typer-include_all` omits
  that `--all` now requires a selection; `PAR-prompts-typer-limit` describes `-n`
  as capping prompt events, which is still true when reading but not for the
  catalog's session rows; `PAR-prompts-typer-file` omits that upstream's own
  `--file` equivalence test had to append an id for `prompts`.
- **Still accurate**: 21, including `EXTRA-003` (provenance and legacy records —
  the predicate is unchanged), `EXTRA-004` (`prompts` still takes `[0]`),
  `EXTRA-040` (`--include-context` still unavailable), `EXTRA-055`
  (`--events-json` still unavailable) and the 13 inherited scope options.

Estimate: **about 6 of 408 rows have a factually stale cell (1.5%), all of them
on the `prompts` surface, plus 4 to 6 rows missing entirely.** The audit's
findings for `show`, `errors`, `cmds`, `find`, `tools`, `path`, `stats`,
`skills`, `serve`, `secrets` and the root command are unaffected. The handoff's
pinned base and version, by contrast, are wrong in a way that has already caused
one bad decision.

## 5. Recommended strategy

**Recommendation: keep this working tree, port upstream's three improvements
into it, and re-decide `--all` and the `prompts` default explicitly.** Do that
as a dedicated reconciliation slice before SXR-CLI-06.

Concretely, in one slice:

1. Rebase the working tree onto `origin/HEAD` mechanically. The cost is small
   and measured: applying the cumulative `git diff HEAD` (35 files, 2481 lines)
   to an extracted upstream tree leaves **11 rejected hunks in 7 files**
   (`evidence-06/rebase-conflicts.log`). Three are the version bump
   (`pyproject.toml`, `src/sxr/__init__.py`, `uv.lock`) and resolve by choosing
   a number. The remaining eight are `README.md` (2), `src/sxr/cli.py` (2),
   `src/sxr/onboard.py` (2) and `src/sxr/views_read.py` (2), all in the
   prompts-and-primer area. The eight new source modules and the new test
   modules are additions upstream does not have, so they carry no conflict.
2. Adopt upstream's `human_sessions` session filtering wholesale. It is strictly
   better than what slices 1–5 do and there is no reason to reimplement it.
3. Adopt `--latest` as a name, since it is published and costs nothing.
4. Put the `prompts` default to the reviewer as a decision (see below), and
   implement whichever is chosen once, in `views_prompts.py`, so selection,
   presentation and catalog stay one module family instead of two.
5. Re-render the primer from upstream's v0.13.0 body, re-apply slice 5's one
   `cmds` line, and pick a version above 0.13.0. Do not ship the current
   0.14.0 primer.

**Cost.** Roughly one slice's work for the mechanical rebase and the two
adoptions, plus a second slice if the default flips, because that touches
`verify_prompts.py`, the README, the primer and 83 of 903 collected tests
(`pytest -k prompt`). Upstream's `tests/test_prompt_sessions.py` gives 15 test
functions / 28 cases for free; **23 of those 28 currently fail against this
tree** (`evidence-06/upstream-tests-vs-this-tree.log`), which is a fair measure
of the behavior still to be ported.

**Risk.** The rebase touches the same four files five times, so it must be done
once, carefully, with the existing capture-based before/after machinery pointed
at `origin/HEAD` instead of `48b11c6c`. Every baseline snapshot, evidence
directory and patch in this folder is keyed to the old base and stays valid as a
record of what was decided, not as a diff that still applies.

**Alternatives considered.**

- *Rebase and keep both defaults* is not available; there is one default.
- *Drop the superseded parts of slice 1* would cost the completeness fix and
  `--include-context`, which are the only fixes for the recorded complaint, and
  upstream does not replace them. Rejected.
- *Restart from `origin/HEAD` carrying the decisions forward* throws away four
  slices that upstream never touched (3, 4, most of 2, the `cmds` half of 5) to
  avoid eight rejected hunks. Rejected as disproportionate.
- *Continue as-is and reconcile later* is the worst option, because the primer
  and the version stamp are distributed artifacts and the current tree's
  `init --write` silently downgrades published guidance.

### What happens to D-01 through D-07

| Decision | Under the recommendation |
| --- | --- |
| D-01 `--all` lifts limits and overrides explicit `-n` / `--budget` | **Needs re-affirming against upstream's published `--all`.** Upstream ships the opposite meaning in 0.13.0, so this is now a documented breaking change to a released flag, not a change to an unreleased one. Recommend keeping D-01 and adding upstream's "`--all` needs a selection" guard, with the migration note D-03 already requires. |
| D-02 `prompts` never trims by default; negative `--budget` is a usage error only on `show` | **Unaffected and still the only fix.** `PROMPTS-default-complete` fails on `HEAD` and upstream. |
| D-03 migration note for the `--all` rename | **Grows.** It must now name a published release, and say that 0.12.3–0.13.0 users of `--all` move to `--include-context`. |
| D-04 range banner format `# session @N  <short id>  <path>` | **Unaffected as a format, needs merging with upstream's stderr notices** so a range and a defaulted single session do not describe themselves twice in two idioms. |
| D-05 negative `--budget` / `--line-limit` on `show` | **Unaffected.** Upstream did not touch `show`. |
| D-06 audit scripts require `--output` | **Unaffected.** Local audit convention. |
| D-07 drop `cmds --grep`'s implicit all-sessions scope, with primer reissue | **Substance unaffected, delivery must be redone.** The `cmds` fix applies cleanly; the primer edit must be re-applied on upstream's body, and the version chosen above 0.13.0. |

### What happens to `verify_prompts.py`'s five contracts

Measured per tree (`evidence-06/contracts-vs-upstream.log`):

| Contract | HEAD 48b11c6 | this tree | upstream 8f93114 |
| --- | --- | --- | --- |
| `PROMPTS-default-selection` | passed | passed | passed |
| `PROMPTS-include-context` | failed | passed | failed |
| `PROMPTS-all-keeps-selection` | failed | passed | failed |
| `PROMPTS-all-lifts-limits` | failed | passed | failed |
| `PROMPTS-default-complete` | failed | passed | failed |

Under the recommendation all five survive unchanged, because they are asserted
through `--file` selection and so are independent of what a bare `prompts`
prints. They are also the precise statement of what adopting upstream wholesale
would cost: **four of five would start failing.** If the reviewer flips the
default to upstream's catalog, `verify_prompts.py` needs one added contract for
the catalog form and no changes to these five.

## 6. Does anything published change an accepted decision?

Yes, two things, and one of them is a raw-record contract.

**The `prompts --json` contract.** With a selection or `--latest`, upstream's
`--json` still emits the original source records, so `@N --json` is unaffected.
Bare `prompts --json`, though, now emits synthesized objects —
`{"type": "prompt_session", "handle", "id", "provider", "cwd", "started",
"path", "prompts", "first_prompt", "follow_up"}` — one per session, containing
`first_prompt` text lifted out of a record rather than the record itself. That
conflicts with the contract this refactor has been preserving, that a read
view's `--json` emits complete distinct physical source records. It does not
conflict with D-01 or D-02, which are about limits and selection, not shape.
Measured: the bare `--json` case in `evidence-06/prompts-three-way.log` reports
`session catalog JSON` for upstream and `raw records` for `HEAD` and this tree.

Two honest readings, and the reviewer should pick one: either the raw-record
contract binds only views that read a session, and a catalog is a listing view
like `sxr list` (whose `--json` is also derived), or bare `prompts --json`
breaks the contract and the catalog belongs on its own verb. The first reading
is the one upstream implicitly took; it is defensible, and it needs writing down
in `contracts.md` either way.

**The `--file` equivalence contract.** `tests/test_file_selection.py` asserts
that `--file <path>` and the equivalent `--path`-scoped invocation produce
identical output for every session view. Upstream had to weaken it for
`prompts`, appending `ref.id` to the command before comparing, because bare
`prompts` no longer reads a session. That is a contract this refactor has been
preserving unconditionally, and adopting upstream's default means qualifying it.

## Decision needed

One question blocks the reconciliation slice: **is `prompts` a read command
whose default prints complete human prompts (slice 1, D-01, D-02), or a
discovery command whose default lists human conversations (published 0.13.0)?**

Everything else follows mechanically from the answer. My recommendation is to
keep reading as the default and add upstream's session filtering, `--latest` and
`# prompts:` notice, because the recorded complaint was about reading and the
catalog duplicates `sxr list`'s job — but this is a product judgment, upstream
already published the other answer, and I should not pick it silently.

Two things should happen regardless of that answer, and soon:

1. **Do not run `sxr init --write` from this tree in any repository**, including
   this one, until the primer is rebuilt on upstream's body. It silently deletes
   published guidance and stamps the result as newer.
2. **Choose the next version after reconciling, not before.** 0.14.0 is fine as
   a placeholder because nothing is published, but the tree it currently labels
   is missing 0.12.3, 0.12.4 and 0.13.0.

## Evidence

All paths relative to `audit/2026-09-11/cli-refactor/`.

| Path | What it records |
| --- | --- |
| `probe_prompt_predicates.py` | Differential predicate probe; imports upstream's module via `git show` |
| `probe_prompts_three_way.py` | Same `prompts` invocations against `HEAD`, this tree and `origin/HEAD` |
| `probe_contracts_vs_upstream.py` | The five migrated prompt contracts run against all three trees |
| `evidence-06/prompt-predicates.log` | 23 record shapes, 0 divergences |
| `evidence-06/prompts-three-way.log`, `.json` | 12 invocations × 3 trees, with raw stdout and stderr |
| `evidence-06/contracts-vs-upstream.log`, `.json` | 5 contracts × 3 trees |
| `evidence-06/upstream-tests-vs-this-tree.log` | Upstream's 28 prompt-session cases against this tree: 23 failed, 5 passed |
| `evidence-06/prompts-option-surface.log` | `prompts --help` option lists: 16 / 17 / 17 |
| `evidence-06/primer-lineage.log` | `init --check` and `init --write` from this tree over the published v0.13.0 primer |
| `evidence-06/primer-bodies.log` | Full `PRIMER_BODY` and `EPILOG` diffs, upstream versus this tree |
| `evidence-06/rebase-conflicts.log` | Cumulative `git diff HEAD` applied to an extracted upstream tree: 11 rejected hunks in 7 files |
