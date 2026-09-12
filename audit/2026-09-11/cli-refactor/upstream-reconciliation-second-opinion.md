# Upstream reconciliation assessment

**Question put to this assessment:** slices 1–5 were built on `48b11c6c`, which is
three published releases behind `origin/HEAD`, and those releases rework `prompts` —
the exact command slice 1 rewrote. Can the refactor continue, or must it reconcile
first?

**Answer: it can continue. Reconciliation is required before any release, not before
the next slice.** Upstream did not change human-prompt detection at all (its predicate
is a byte-identical *move* of the same function slice 1 inherited), it does not fix
either half of the original complaint, and it does not fix the range defect slice 2
fixed. What it does add is one genuinely valuable capability the working tree lacks —
skipping empty and background sessions when choosing a session by default — and one
default that genuinely conflicts with slice 1. The conflict surface is 7 files, and
`views_read.py`'s share of it is positional rather than semantic.

Read-only assessment. Nothing in the repository was modified except this file and
`ledger.md`. All execution happened in throwaway clones under `/tmp/sxr-recon/`
(`up` at `8f93114f`, `base` at `48b11c6c`, `now` = an `rsync` copy of the working
tree). `HEAD` is still `48b11c6cf08200de363e108924e42fdbc52d83e8` and `git status`
still reports 60 entries.

## Facts established first

Everything in the briefing that I could check, I checked.

| Claim | Verdict | How |
|---|---|---|
| `HEAD` = `48b11c6c`, `origin/HEAD` = `8f93114f` | confirmed | `git rev-parse` |
| `HEAD` is an ancestor, behind by exactly 3 | confirmed | `git rev-list --left-right --count HEAD...origin/HEAD` → `0  3` |
| The 3 commits are releases 0.12.3 / 0.12.4 / 0.13.0 | confirmed | `v0.12.3`→`3280f00`, `v0.12.4`→`9f5fe09`, `v0.13.0`→`8f93114`; `v0.12.2`→`48b11c6` |
| 13 files, +572/−34 | confirmed | `git diff --stat 48b11c6c origin/HEAD` |
| `prompt_catalog.py`, `prompt_selection.py`, `test_prompt_sessions.py` are new; the last is 312 lines | confirmed | same diff |
| Homebrew tap points at the v0.13.0 assets | **confirmed** | `$(brew --repository)/Library/Taps/ivorpad/homebrew-tap/Formula/sxr.rb` has `version "0.13.0"` and four `.../download/v0.13.0/...` URLs |
| CSV is the byte authority the handoff pinned | confirmed | `commands-before-after.csv` is 388855 bytes, sha256 `c24d00ed…1f63e4`, exactly as the handoff states; 408 data rows, 21 columns |
| 903 tests pass in the working tree | confirmed | `pytest -q` on the `/tmp` copy: 903 passed |

One correction to the briefing's framing, and it changes the recommendation: the
briefing describes the working tree as the stale side. It is stale by three commits.
`origin/HEAD` is stale by far more — **the entire 17-finding audit remediation is
uncommitted and therefore absent from every published release.** Measured directly:

```
sxr prompts -n -1      0.13.0 → exit 0 (accepted)    working tree → exit 2
sxr show --budget -5   0.13.0 → exit 0 (accepted)    working tree → exit 2
sxr errors --compact   0.13.0 → exit 2 (no option)   working tree → exit 1 (works)
```

`SXR-AUD-011` / `SXR-AUD-012` (negative limits are usage errors) are not in 0.13.0.
Neither side is a superset of the other, so "rebase onto the better base" is not the
shape of this problem. The reconstructed working tree is 59 files, +4371/−523 against
`48b11c6c`; upstream is 13 files, +572/−34.

## 1. Overlap and conflict, per slice

### The authoritative conflict list

I reconstructed the working tree as a commit on `48b11c6c` inside the throwaway clone
and asked git to merge `8f93114f`. Seven files conflict:

| File | Conflict hunks | Nature |
|---|---|---|
| `src/sxr/cli.py` | 3 | **semantic** — the `prompts` signature, docstring and body |
| `src/sxr/views_read.py` | 3 | **positional** — see below |
| `src/sxr/onboard.py` | 3 | text — 3 hunks in `EPILOG`, 1 in `PRIMER_BODY` |
| `README.md` | 4 | text — the `prompts` documentation |
| `pyproject.toml` | 1 | `0.14.0` vs `0.13.0` |
| `src/sxr/__init__.py` | 1 | `0.14.0` vs `0.13.0` |
| `uv.lock` | 1 | `0.14.0` vs `0.13.0` |

Merging cleanly, with no conflict: `packaging/verify.py`, `tests/test_file_selection.py`,
and all three new upstream modules (`prompt_selection.py`, `prompt_catalog.py`,
`tests/test_prompt_sessions.py`). `src/sxr/navigation.py` is purely additive upstream
(+9/−0: a new `scope_command`; the existing `command` is untouched), and the working
tree does not modify that file at all, so it merges silently.

**The `views_read.py` conflict is not a semantic clash.** Slice 1 *deleted* `prompts()`
and `_prompt_record` from `views_read.py` (moving them to `views_prompts.py`), and
slice 4 put `error_records` / `error_line` / `errors` into the vacated region. Upstream
edited `prompts()` *in place* in that same region. Git therefore reports slice 4's
error code against upstream's prompt code, which are unrelated behaviors. Once
`prompts()` is accepted as gone from `views_read.py`, this file's conflict resolves
mechanically.

### Per-slice verdict

**SXR-CLI-01 — complete human prompts. Genuine conflict, on the default only.**
Shared files: `cli.py`, `views_read.py`, `onboard.py`, `README.md`. Slice 1's
`views_prompts.py` and upstream's `prompt_selection.py` / `prompt_catalog.py` are not
rival implementations of the same thing:

- `views_prompts.py` owns *record* selection and presentation within one session.
- `prompt_selection.py` owns *record* selection (identical logic, see §2) **plus**
  session-level discovery, which slice 1 has no equivalent of.
- `prompt_catalog.py` is a new listing view with no counterpart on either side.

Three behaviors collide:

| Behavior | Slice 1 | Upstream 0.13.0 | Verdict |
|---|---|---|---|
| Bare `prompts` | prints complete human prompts of the selected session | prints a *table of sessions*, no prompt text | **outright conflict** |
| `--all` | lifts limits only | widens selection to injected context and tool results | **outright conflict** |
| `--all` with no selection | works | usage error, exit 2 | conflict, follows from the above |
| Human-prompt predicate | `human_prompt` | `_prompt_record` | **identical** (§2) |

**SXR-CLI-02 — multi-session ranges. No conflict; upstream did not fix this.**
Shared files: `cli.py`, `views_read.py`, `onboard.py`, `README.md`. Measured on one
five-session Codex corpus:

```
sxr prompts --codex @1:@3
  0.13.0        → reads @1 only ("# 1 user records shown"); @2 and @3 never opened
  working tree  → three banners, three sessions, one shared row allowance
```

Upstream's `prompt_session` still ends in `resolve(arg, refs)[0]`, so `EXTRA-004`'s
"show, prompts and tools then take [0]" is still an accurate description of
`origin/HEAD`. Slice 2 remains entirely necessary.

On `9f5fe09`'s session navigation versus slice 2's banners — these occupy the same
output slot with different content, and both go to stderr under `--json`:

```
0.13.0        # prompts: @4 human (skipped 3 newer empty or background sessions)   [stderr]
              # sessions: env CODEX_HOME=… sxr --codex --path … prompts            [stderr]
working tree  # session @1  review  /…/rollout-…-review.jsonl                      [stdout; stderr if --json]
```

This is a **cosmetic collision with one substantive idea inside it**. The banner
formats are a `D-04` question and `D-04` already chose the uniform form. But upstream's
parenthetical *"skipped 3 newer empty or background sessions"* is real information the
working tree cannot produce, because it never skips anything. That disclosure belongs
under the existing `contracts.md` rule that a view may disclose that it defaulted its
scope — it is not a `D-04` reversal.

**SXR-CLI-03 — one selection pipeline for `show`. File overlap only, no behavior overlap.**
Shared files: `views_read.py`, `onboard.py`, `README.md`. Upstream's `views_read.py`
edit is confined to `prompts()`; slice 3 works on `show`. Confirmed from the other
direction: `sxr show --help` is **byte-identical** between `48b11c6c` and
`origin/HEAD`.

**SXR-CLI-04 — `errors` identity and complete text. File overlap only, no behavior overlap.**
Shared files: `cli.py`, `views_read.py`, `onboard.py`, `README.md`. `sxr errors --help`
is byte-identical between `48b11c6c` and `origin/HEAD`. The `views_read.py` conflict
here is the positional artifact described above.

**SXR-CLI-05 — `cmds` scope. No behavior overlap; direct collision on version and primer.**
Shared files: `cli.py`, `onboard.py`, `README.md`, `pyproject.toml`, `__init__.py`,
`uv.lock`. `sxr cmds --help` is byte-identical between `48b11c6c` and `origin/HEAD`, so
`cmds` itself is untouched upstream. The collision is in the artifacts slice 5 had to
move: the version triple, and `PRIMER_BODY` — upstream changed `PRIMER_BODY` too
(hunk at base line 108, inside the `56`–`116` block). **The primer needs a third
reissue after reconciliation**, because the current `CLAUDE.md` v0.14.0 primer still
says "No ID means newest" and carries none of upstream's `prompts` text.

## 2. Whose human-prompt detection is better

**Neither. They are the same code.** This is the central finding of the assessment and
it dissolves most of the apparent risk.

`48b11c6c:src/sxr/views_read.py::_prompt_record` and
`origin/HEAD:src/sxr/prompt_selection.py::_prompt_record` are **byte-identical** — I
extracted both functions and compared them. The three published commits *moved* the
predicate out of `views_read.py`; they did not change one character of it. Slice 1
inherited the same function as `human_prompt`, factoring the Codex label lookup into
`_content_item_kinds` and adding `context_label` for provenance display.

So the comparison the briefing asks for is a comparison of a refactor against its own
origin. I ran both predicates over 23 record shapes × 2 selection kinds = 46 cases:
**0 disagreements.** Cases covered, all agreeing:

| Record shape | Both predicates |
|---|---|
| Claude plain human text | select |
| Claude `isMeta` | reject |
| Claude `isCompactSummary` | reject |
| Claude both flags, and `isMeta: false` | reject / select |
| Claude `tool_result` content (`kind="result"`) | reject |
| Claude 40 000-char human input | select |
| Codex `user.text`, `user.text` + extras | select |
| Codex legacy, no metadata key at all | select (legacy stays human) |
| Codex `agents_md.instructions`, `hooks.additional_context`, `generic.turn_aborted` | reject |
| Codex `content_item_kinds: []`, all-non-string, mixed non-string + `user.` | reject / reject / select |
| Codex malformed `content_item_kinds` (dict, str, `null`), `payload: null`, empty record | select (falls back to legacy) |

The refactor is behaviour-preserving on the one axis that carries the most risk. The
only difference is additive: slice 1 can *label* a rejected record
(`context_label` → `compact`, `meta`, the Codex label, or `tool_result`), which is what
makes `--include-context` legible. Upstream has no equivalent.

**Is the shared predicate itself sound?** I checked it against the real corpus rather
than trusting the fixtures — 3850 Codex rollout files, 6544 records carrying
`content_item_kinds`, reading label names only:

- The most frequent label by far is `["unknown"]` (3864 occurrences). It appears
  **only on `role: assistant`** records, never on user-role records, so the predicate
  never sees it. Both are safe; there is no latent bug here.
- `hooks.additional_context` (245) appears only on `role: developer` records, so the
  caller's `event.role == "user"` guard excludes it before the predicate runs. Both
  behave identically.
- The **only** `user.`-prefixed labels that exist in the corpus are `user.text` and
  `user.image`. The `startswith("user.")` test is therefore well-grounded, not a
  guess. My hypothetical adversarial case (`user.instructions`, which both predicates
  would wrongly accept) does not occur in the corpus.
- Real injected labels on user-role records — `agents_md.instructions`,
  `environments.environment_context`, `plugins.recommendations`,
  `skills.selected_skill_instructions`, `goal.internal_context`,
  `generic.turn_aborted` — are all correctly rejected by both.

**Where they do differ is a defect, and slice 1 fixed it.** `-n` is ignored in the
JSON path at `48b11c6c` and still ignored at `origin/HEAD`:

```
sxr prompts --json -n 1     0.13.0 → 3 records     working tree → 1 record
```

`contracts.md` requires that "a row limit counts distinct physical records" for
`show`, `prompts` and `errors`. Upstream violates that; the working tree honours it.
Note this makes the CSV's own `PAR-prompts-typer-limit` "before" text ("distinct
physical source records in JSON") **wrong as of the audit**, not merely stale — an
inaccuracy in the preserved review, worth recording.

Upstream also introduces two new flag defects in its catalog path, both of which the
working tree does not have:

```
sxr prompts --codex --budget 0        0.13.0 → --budget silently ignored (budget is not passed to prompt_catalog)
sxr prompts --codex -n 1             0.13.0 → -n now limits *session rows*, a unit change
```

The `-n` unit change is precisely the class of question the ledger records as
unresolved for `tools --json` (`PAR-tools-typer-limit`). Upstream answered it for
`prompts` unilaterally, in the direction the ledger says no task may assume.

## 3. Redundant, partially redundant, still needed

**Nothing in any slice is made redundant by upstream. Upstream fixes neither half of
the original complaint.**

The complaint had two parts. Measured, not inferred:

**(a) `sxr prompts --codex @2 --all` included material that was not human prompts.**
Still true at `origin/HEAD`. On a Claude session holding one human prompt, one
`isMeta` record, one `isCompactSummary` record, one `tool_result`, one long human
prompt and a second human prompt:

```
sxr prompts @1 --all
  0.13.0        → 6 records, including "(meta) INJECTED-META", "(compact) INJECTED-COMPACT",
                  "result () TOOL-OUTPUT"      ← the complaint, unchanged
  working tree  → 3 human prompts; --include-context is the separate way to ask for the rest
```

Upstream's own README makes this explicit: "`prompts @N --all` includes every
user-role record, including injected context and tool results." The published release
ships the behavior the user objected to.

**(b) Needing `-n 0 --budget 0` to get complete prompts is poor CLI behavior.**
Still true at `origin/HEAD`. With three human prompts of ~15 000 chars each (45k
total), **no environment variable set and no flags passed**:

```
sxr prompts --latest
  0.13.0        → "# trimmed to 200-char lines (45k chars > 40k budget); whole text: --budget 0 or --json"
  working tree  → complete text, no trim notice
```

`_trim_decision` and `scan_budget` are untouched by all three commits, so the
40 000-char default still trims, and `SXR_BUDGET` still trims (at `SXR_BUDGET=200`,
0.13.0 trims a 9k conversation; the working tree does not). Slice 1 is the only thing
that fixes (b), and upstream's new default makes (b) *worse* in one respect: bare
`prompts` no longer prints prompt text at all, and the one preview column it does
print is capped (248 characters in my run).

**Do the two defaults conflict outright? Yes.** "Bare `prompts` lists human
conversations" and "bare `prompts` prints complete human prompts" cannot both hold.
This is the one real design decision in the reconciliation. Assessed against the
user's stated complaint, **slice 1's default serves it better and upstream's default
works against it**: the user asked to stop having to type flags to see complete
prompts, and upstream's answer requires typing `--latest` (or a handle) to see any
prompts at all, then `--budget 0` to see them completely — two flags where the
complaint was about two flags.

**But upstream's session discovery is a real fix that the working tree needs.** It is
separable from the default. Measured on the same corpus, where the newest session in
scope is a `guardian_review` session:

```
sxr prompts --codex
  0.13.0        → lists @4 human (4 prompts) and @5 older (1 prompt), hiding 3 background sessions
  working tree  → reads @1, the guardian_review session, and prints "REVIEW-REQUEST"
```

The working tree lands on a review session and calls its content a human prompt.
`prompt_selection.human_sessions` — skip `agent` / `subagent` / `guardian_review`
kinds and any ref carrying `parent_id` / `parent_thread_id`, then skip sessions with
no human records — is the fix, and it is orthogonal to whether the result is listed
or printed. **This is the one piece of upstream that must be carried forward on
merit, not for compatibility.**

Summary: slice 1 needs one addition (default session discovery) and keeps its default;
slices 2, 3, 4, 5 are untouched on merit by upstream.

## 4. How stale the audit is

**Attributable to upstream: small and tightly bounded. Attributable to the working
tree's own 59-file diff: large, and already tracked in `disposition.json`.** These are
two different axes and conflating them would overstate the problem.

### What I sampled

1. **All 27 prompts-related rows**, read in full (`default_before`, `before`,
   `example_before`): the 25 rows whose `command` is `sxr prompts`, plus `EXTRA-004`
   (`show, prompts, tools`) and `EXTRA-006` (`show, prompts, errors, grep, cmds`).
2. **The complete help surface**, 0.12.2 vs 0.13.0 — all 18 command surfaces, captured
   from the two clones at fixed `COLUMNS=100` and compared byte for byte.
3. **The 45 non-prompts rows** whose `source` column names `views_read.py` or
   `navigation.py`, identified mechanically (26 `show` rows, 15 `errors` rows,
   `EXTRA-005`, `EXTRA-008`, `EXTRA-011`, `EXTRA-015`).
4. Targeted re-measurement of six specific row claims against both trees
   (`--budget`, `-n` in both paths, `--line-limit`, `--coverage`, `@A:@B`).

### The bound that makes extrapolation safe

Upstream changed the `--help` output of exactly **2 of 18** command surfaces:

- `sxr (root)` — the command one-liner, the ids paragraph, the `--json` sentence, and
  the examples block
- `sxr prompts` — docstring and the new `--latest` option

The other **16 are byte-identical**: `list`, `show`, `errors`, `tools`, `stats`,
`path`, `cmds`, `grep`, `find`, `index`, `init`, `serve`, `skills`, `secrets`,
`secrets audit`, `secrets clean`. Combined with the source diff — whose only
behavioral reach is the `prompts` code path, plus a purely additive
`navigation.scope_command` (+9/−0) — no row outside `prompts` and the root can have
had its `before` invalidated by upstream. That is what licenses the extrapolation
rather than 408 hand checks.

### Verdicts on the 27 prompts rows

| Class | Rows | IDs |
|---|---|---|
| **`before` / `default_before` now wrong** | 8 | `CMD-prompts-typer` (default "Newest session" and "All human-selected rows"), `PAR-prompts-typer-arg` ("Newest session by default"), `PAR-prompts-typer-include_all` (new precondition), `PAR-prompts-typer-budget` (ignored in the bare path), `PAR-prompts-typer-line_cap` (now a preview cap, budget-independent), `PAR-prompts-typer-json_out` (emits `prompt_session`, not source JSONL), `PAR-prompts-typer-limit` (unit changed to session rows), `PAR-prompts-typer-help` (text changed) |
| **Partially stale** | 1 | `EXTRA-006` — "Read `--json` emits whole provider JSONL objects" no longer holds for bare `prompts` |
| **Contract current, `example_before` now misleading** | 10 | `use_codex`, `use_claude`, `path`, `file`, `recursive`, `worktrees`, `claude_roots`, `include_agents`, `archives`, `coverage` — semantics unchanged, but every `sxr prompts …` example now produces a session listing instead of prompts |
| **Still accurate** | 2 | `EXTRA-003` (predicate unchanged — the strongest confirmation of §2), `EXTRA-004` ("then take [0]" still true) |
| **Proposals, unaffected** | 6 | `EXTRA-021`, `EXTRA-040`, `EXTRA-043`, `EXTRA-055`, `EXTRA-073`, `EXTRA-074`. `EXTRA-040` (`--include-context`) now competes with upstream's `--latest` + catalog design rather than being simply open |

Outside `prompts`, upstream invalidates `PAR-root-typer-help` and the root help
material in `CMD-root-typer`.

### Estimate

**Upstream-caused staleness: ~9–11 of 408 rows (about 2–3%) have an inaccurate
contract description, plus ~10 more whose examples mislead while their contracts
hold.** The 45 `show` / `errors` / `navigation` rows I checked are unaffected by
upstream, because upstream's edits to `views_read.py` never leave `prompts()` and its
`navigation.py` change adds a function without touching the existing one.

Two caveats I will not paper over. First, the far larger staleness driver is the
working tree itself: the CSV was captured against `48b11c6c` *without* the
uncommitted 17-finding remediation, and 138 rows are scoped into tasks with 5 slices
now implemented — that axis is `disposition.json`'s job and I did not re-audit it.
Second, 312 of the 408 rows cite a `help/` capture as evidence; the root capture
(`help/root-typer.txt`) and the prompts capture (`help/prompts-typer.txt`) are the two
whose *bytes* no longer reproduce at `origin/HEAD`. Both are preserved 2026-09-10
evidence and must stay byte-identical, so this is a note in the disposition, never a
re-capture.

## 5. Recommended reconciliation strategy

**Recommendation: merge `origin/HEAD` into this tree and port upstream's session
discovery into slice 1's design, keeping slice 1's default. Do it as an explicit sixth
slice, `SXR-CLI-06`, before any release and after the reviewer accepts SXR-CLI-05.**

Rejecting the alternatives, with reasons:

- **Rebase the five slices onto `origin/HEAD`.** Not literally available: the slices
  are not commits, they are one uncommitted 59-file working tree, so there is nothing
  to replay. Committing first to enable a rebase would also put the reviewer's
  bounded-diff scheme (five recorded baselines) behind a commit boundary it was
  designed to avoid. The merge produces the same content with less ceremony.
- **Drop the parts of slice 1 that upstream supersedes.** This set is **empty**.
  Upstream supersedes no part of slice 1: the predicate is identical, and neither half
  of the complaint is fixed upstream.
- **Restart from `origin/HEAD` carrying the decisions forward.** The most expensive
  option by a wide margin, and it inverts the actual staleness: it would discard 59
  files of work including all 17 audit remediations to inherit 3 prompt commits, then
  re-implement the remediations. Only justified if the reviewer decides upstream's
  catalog default wins outright, which §3 argues against.

### What SXR-CLI-06 does

1. Capture `baseline-06/` first, exactly as slices 1–5 did, then merge. Record the
   merge resolution as `slice-06.patch` so it is reviewable as its own artifact.
2. **Resolve the 7 conflicts** as follows. `views_read.py`: accept that `prompts()`
   is gone and keep slice 4's `errors` code (mechanical). `cli.py`: keep slice 1's
   `prompts` signature and `prompts_scope` call, and add upstream's `--latest`.
   `pyproject.toml` / `__init__.py` / `uv.lock`: keep `0.14.0` — see below.
   `onboard.py` and `README.md`: hand-merge, then reissue the primer.
3. **Port `human_sessions` into the default selection path.** This is the merit-based
   adoption: when no selector is given, skip `agent` / `subagent` / `guardian_review`
   sessions and sessions with no human records, and disclose the skip
   ("skipped N newer empty or background sessions") under the existing
   defaulted-scope rule. This fixes the working tree's real defect of reading a
   `guardian_review` session by default.
4. **Accept `--latest` as a compatible spelling.** 0.13.0 is on the Homebrew tap, so
   agents and primers in other repositories may already use it. Under slice 1's
   default with step 3 applied, `--latest` describes what a bare invocation already
   does, so honouring it costs almost nothing and avoids a hard break.
5. **Keep `--all` = lift limits**, and keep bare `prompts --json` emitting original
   provider records. Consider adding upstream's catalog later as an explicit opt-in
   (a `--sessions` / `--list` flag) rather than a default — that gives upstream's real
   use case, discovering *which* session, without taking the default away from the
   complaint. Scope it as a new task, not part of SXR-CLI-06.

### Cost and risk

**Cost: roughly one slice's work, weighted toward tests, not source.** Source
resolution is small: 3 semantic hunks in `cli.py`, 3 mechanical hunks in
`views_read.py`, 3 version one-liners, plus prose in `onboard.py` and `README.md`.
Step 3 is a contained addition to session selection. The real cost is test
reconciliation: I copied upstream's `tests/test_prompt_sessions.py` into the working
tree and ran it — **12 test functions, 23 parametrized cases, all 23 fail**, because
they assert the catalog default, `--latest`, and upstream's stderr notice format. Each
needs a decision: keep (retargeted at the reconciled behavior), rewrite, or drop with
a recorded reason. That file is 312 lines against a 400-line test module cap, so it
will need splitting if largely kept.

**Risks.** The one that matters: **step 5 reverts a published default.** 0.13.0 is
tagged, released, and on the tap, so users may have `sxr prompts` producing a session
table today. Reverting that in 0.14.0 is a compatibility decision, not a bug fix, and
it needs a migration note at least as prominent as the one `D-03` approved for
`--all`. Secondary risks are low: the predicate identity in §2 means the merge cannot
silently change which records count as human, and 903 tests plus the five
`verify_prompts.py` contracts will catch drift.

### What happens to each artifact

**Decisions D-01 to D-07.** Six survive untouched; one needs widening.

| # | Effect of upstream | Action |
|---|---|---|
| D-01 | None. Upstream's `--all` does not lift limits either, so it does not contest the precedence rule. | keep |
| D-02 | None. Upstream has no view on negative `prompts` budgets. | keep |
| D-03 | **Needs widening.** It approved "README + `prompts --help` note is sufficient" for a purely local `--all` change. The change now also reverts a *published* 0.13.0 default and must document `--latest` and the disappearance of the catalog. | **reviewer to re-affirm at wider scope** |
| D-04 | Cosmetic collision only. Upstream's `# prompts:` / `# sessions:` stderr notice occupies the same slot; the uniform banner still wins. Its "skipped N…" disclosure lands under the existing defaulted-scope rule, not as a D-04 reversal. | keep, add a note |
| D-05 | None — and reinforced: 0.13.0 accepts `--budget -5` (exit 0), so the asymmetry is entirely a working-tree matter. | keep |
| D-06 | None. Upstream touches no audit script. | keep |
| D-07 | Behaviorally none (`cmds --help` byte-identical upstream). But upstream edits `PRIMER_BODY`, so the primer reissue must be **redone** on the merged body, and the version stamp folds into the question below. | keep; redo the reissue |

**`verify_prompts.py`'s five contracts.** All five pass on the working tree. Run
against `origin/HEAD` with the same audit corpus, **one passes and four fail**:

| Check | 0.13.0 | working tree |
|---|---|---|
| `PROMPTS-default-selection` | passed | passed |
| `PROMPTS-include-context` | failed — no such option | passed |
| `PROMPTS-all-keeps-selection` | failed — `--all` changed which records qualify | passed |
| `PROMPTS-all-lifts-limits` | failed — `-n 1` did not cap records | passed |
| `PROMPTS-default-complete` | failed — environment budget trimmed the default view | passed |

Under the recommended strategy **all five survive unchanged and need no rewrite**,
which is a strong argument for it: they encode exactly the four behaviors upstream
lacks. Under the alternative (adopt upstream's default) four of five would have to be
rewritten or retired, which would mean retiring the recorded fix to the user's
complaint.

**The five baseline snapshots and patches.** Untouched and still valid. Each is a diff
against its own recorded pre-slice tree, so none depends on `HEAD` or on
`origin/HEAD`. What stops working after the merge is only the
`README.md` reproduction recipe for the *current* tree, because the tree gains
upstream content that no baseline contains. Capturing `baseline-06/` before the merge
and recording `slice-06.patch` keeps every existing patch reproducible against its own
baseline and makes the merge a separately reviewable artifact. No existing evidence
needs regenerating.

**The 0.14.0 question.** Keep `0.14.0`, but only if the merge lands first. The number
itself is still correct and uncollided: published tags stop at `v0.13.0`, so `0.14.0`
is the next unused number and the primer stamp still moves, which `D-07` established
is required for `init --check` to notice the reissued body. The hazard is not the
number but the content: **a `0.14.0` cut from the tree as it stands today would
silently regress three published releases** — it would drop `--latest`, drop the
catalog, and revert 0.13.0's default while claiming a higher version. After the merge
that hazard is gone. This does not change the standing rule that nothing here
publishes and `just release` is the reviewer's to run.

## 6. Would the published releases change an accepted decision?

**One documented upstream contract change does conflict with the preserved contract
set, and it is upstream's, not the refactor's.**

`contracts.md` states: "`--json` in read views emits the original provider JSONL
records, complete and untruncated." Upstream's bare `prompts --json` emits a
synthesized aggregate on stdout:

```
{"type": "prompt_session", "handle": "@1", "id": "cc-human", "provider": "claude",
 "cwd": "…", "started": "…", "path": "…", "prompts": 3, "first_prompt": "…",
 "follow_up": "…"}
```

That is not a provider record. It is a new `--json` schema in a read view, introduced
in a release, on stdout. Three consequences:

- It **conflicts with the raw-record contract** the refactor has been preserving, and
  with `EXTRA-006`'s description of read `--json`.
- It **pre-empts the three `decision-needed` CSV rows** (`PAR-tools-typer-limit`,
  `PAR-secrets-clean-typer-json_out`, `EXTRA-017`), all of which ask whether a
  `--json` schema may grow. The ledger records that no task may assume the answer.
  Upstream assumed it for `prompts`, and separately changed `-n`'s unit in the same
  view — which is the exact shape of `PAR-tools-typer-limit`. **The reviewer's answer
  to those three rows is now partly a question about whether to keep a published
  behavior.**
- Upstream also had to **weaken its own `--file` parity test** to accommodate this:
  `tests/test_file_selection.py` gained `if command[0] == "prompts": command = [*command, ref.id]`,
  because under `--path` bare `prompts` lists while under `--file` it reads. That is
  an erosion of the `--file`/`--path` byte-identity contract in `contracts.md`, and
  it is upstream's doing.

**D-01 and D-02 are not in conflict with upstream.** D-01 governs `--all` against
explicit `-n` / `--budget`; upstream's `--all` does not lift limits at all, so it takes
no position. D-02 governs negative `prompts` budgets; upstream is silent.

**Does upstream change the `PROMPTS-filter` calculus? No — it sharpens the wording
required.** `PROMPTS-filter` asserts "Prompts omit metadata and tool results; `--all`
restores user-role records." Run against `origin/HEAD` it **passes**; against the
working tree it **fails**. So upstream does not merely leave the old behavior in place,
it *ships* it. The failure remains a correct, intentional divergence — but its
description must be upgraded: it is no longer "we intentionally broke a preserved
audit check," it is **"we intentionally diverge from behavior published in v0.13.0 and
installed by the Homebrew tap."** Same test result, materially stronger claim, and it
is the same claim as the D-03 migration-note question. I recommend recording it in
those terms rather than leaving it as an ordinary expected failure.

## The one decision I need from the reviewer

**Does slice 1's default stand against the published 0.13.0 default?**

I recommend yes, on the evidence in §3: upstream's default prints no prompt text,
still truncates at 40k once you ask for text, and still widens `--all` to injected
context and tool results — so it leaves both halves of the original complaint
unaddressed, while slice 1 fixes both. But it is a revert of a released, tap-installed
default, so it is a compatibility call and not mine to make silently.

- **If yes** (recommended): SXR-CLI-06 as scoped in §5. D-01, D-02, D-04–D-07 stand,
  D-03 widens to cover the published surface, all five `verify_prompts.py` contracts
  survive, `0.14.0` holds once merged, and upstream's `human_sessions` is adopted on
  merit.
- **If no**: the cost is much larger than the merge. Slice 1's default,
  `--include-context`, four of the five `verify_prompts.py` contracts, and the recorded
  fix to the user's complaint would all be retired, and `EXTRA-040`'s proposal would
  be superseded by `--latest`. In that case restarting from `origin/HEAD` becomes the
  more honest option than merging, and the 17 audit remediations would need
  re-landing on top.

## What I could not determine

- **Whether the v0.13.0 release assets match `8f93114f`.** I verified the tap formula
  names v0.13.0 and carries four asset SHA-256 values, but verifying those digests
  would mean downloading the release artifacts, which is outside a read-only local
  assessment.
- **Whether `/opt/homebrew/bin/sxr` is currently 0.13.0.** I did not run the installed
  binary; the handoff records it as untouched by earlier work, and all my measurements
  used the two clones instead.
- **The staleness of the 138 task-scoped CSV rows relative to the working tree.** I
  bounded only upstream's contribution. That axis belongs to `disposition.json` and I
  did not re-audit it.
- **Whether any real transcript would exercise the shared predicate's one theoretical
  gap** (a `user.`-prefixed label that is not human input). No such label exists in
  the 3850-file corpus I sampled, so the gap is hypothetical.

## Reproducing this assessment

Scratch scripts live under `/tmp/sxr-recon/` and are not part of the repository. They
are listed here so the measurements can be rebuilt, not as committed artifacts:
`diff_predicates.py` (46-case predicate matrix), `corpus.py` (synthetic Claude+Codex
corpus), `run_both.py` / `run_focus.py` / `run_default_trim.py` / `run_rowcheck.py`
(paired invocations against both trees), `run_contracts.py` / `run_filter.py`
(`verify_prompts.py` and `PROMPTS-filter` against both trees, by repointing
`audit_support.REPO`), `surface_diff.py` (all 18 help surfaces, 0.12.2 vs 0.13.0),
`csv_stale.py` / `csv_prompts_rows.py` (CSV row classification).

No audit script was run with a defaulted `--output`; nothing under `audit/2026-09-10/`
was written; no test or evidence file in the repository was created or modified by
this assessment.
