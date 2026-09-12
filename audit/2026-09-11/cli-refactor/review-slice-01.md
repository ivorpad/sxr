# Review packet — SXR-CLI-01, complete human prompts

Delivered 2026-09-11. **Accepted 2026-09-11 by the originating reviewer.**
Nothing was committed; the change sits in the working tree alongside the
pre-existing remediation work.

## Decisions, as resolved on acceptance

The reviewer answered all three questions in section 4 on 2026-09-11. Every
answer confirms the behavior already implemented, so no code changed after
acceptance; the slice-01 patch, evidence and baseline snapshot are unmodified.

| # | Question | Reviewer's decision |
|---|---|---|
| D-01 | Should `--all` beat an explicit `-n` / `--budget`? | **Yes, keep it.** Do not switch to last-flag-wins. |
| D-02 | Should negative `--budget` / `--line-limit` become usage errors? | **No, keep them meaning "no trimming."** The reasoning that rejecting them is a `show` change was accepted, so it is recorded as an open question against SXR-CLI-03 rather than dropped. |
| D-03 | Is the README + `prompts --help` migration note enough? | **Yes.** Do not add a stderr deprecation warning for `--all`. |

Decider: the originating reviewer, 2026-09-11. Also recorded in
[ledger.md](ledger.md) under "Resolved decisions".

## 1. What changed

**Task:** SXR-CLI-01. **CSV rows:** `CMD-prompts-typer`,
`PAR-prompts-typer-include_all`, `PAR-prompts-typer-budget`,
`PAR-prompts-typer-line_cap`, `EXTRA-003`, `EXTRA-021`, `EXTRA-040`.

Selection and completeness are now separate flags in `sxr prompts`.

| Aspect | Before | After |
|---|---|---|
| plain `sxr prompts` | trims once selected text passes `--budget`/`SXR_BUDGET` (default 40000), lines capped at `SXR_LINE_LIMIT` | prints complete human prompts; no default budget, so no environment variable can trim it |
| `--all` | dropped the provenance predicate: added injected instructions, compaction summaries and tool results | lifts every row and character limit, in text and `--json`, and overrides an explicit `-n`/`--budget` at either flag position; selection is untouched |
| injected context | only reachable via `--all` | `--include-context`, which labels each record with its recorded provenance |
| `--budget` | implicit default 40000 | explicit compact request; `--budget 0` asks for whole text and beats `--line-limit`; negatives never truncate |
| `--line-limit` | applied only after the budget fired | supplying a positive value is itself the compact request; it can never truncate the plain view |
| `--json` | complete distinct physical records, `-n` counts records | unchanged, plus `--all` lifts the record limit |

Concrete before/after on a synthetic Codex rollout with one 54k-char human
prompt, one short human prompt, one `agents_md.instructions` record and one
`function_call_output` (`evidence/demo-*.txt`, fixture built by the command in
`evidence/README.md`):

```
$ sxr prompts --file /tmp/sxr-demo/rollout-demo.jsonl
# before: 493 bytes of stdout, ending in
  # trimmed to 200-char lines (54k chars > 40k budget); whole text: --budget 0 or --json
# after: 54195 bytes of stdout, ending in
  # 2 of 2 human prompts shown; 2 other user-role records hidden (injected context, tool results): --include-context

$ sxr prompts --file /tmp/sxr-demo/rollout-demo.jsonl --all
# before: 4 records, including "# AGENTS.md instructions" and "tool stdout", still trimmed
# after:  the same 2 human prompts as the plain run, complete, no injected material

$ sxr prompts --file /tmp/sxr-demo/rollout-demo.jsonl --include-context
# after:  4 of 4 user records, with #0002 rendered as
  (agents_md.instructions) "# AGENTS.md instructions ..."
```

The user's original complaint — `sxr prompts --codex @2 --all` returning
material that was not a human prompt — is what the `--all` row above fixes.

## 2. Bounded diff

`slice-01.patch` (769 lines, 475 added / 95 removed) is `diff -ruN` between the
extracted baseline snapshot (`baseline/worktree-snapshot.tar.gz`, taken before
any edit) and the same file set in the current tree. It therefore isolates this
slice only; `git diff HEAD` would also contain the earlier remediation work.

Nine files, two of them new and untracked:

| File | Change |
|---|---|
| `src/sxr/views_prompts.py` | **new (untracked)**, 157 lines — the whole prompts view |
| `src/sxr/views_read.py` | `prompts`/`_prompt_record` removed (285 → 230 lines); `_print_events` renamed to `print_events` |
| `src/sxr/cli.py` | `prompts` signature and docstring; builds `PromptOpts` |
| `src/sxr/flags.py` | new `PromptAllF`, `IncludeContextF`, `PromptBudgetF`, `PromptLineLimitF` |
| `src/sxr/onboard.py` | `--help` epilog: budgets paragraph and the `prompts` example |
| `README.md` | prompts section rewritten, with the `--all` migration note |
| `tests/test_prompt_limits.py` | **new (untracked)**, 33 cases across both providers |
| `tests/test_prompts.py` | `--all` migrated to `--include-context`; one new provenance-label test |
| `tests/test_views.py` | unit calls moved to `PromptOpts`; asserts the new recovery hint |

`tests/test_prompt_defaults.py` is byte-identical to the draft: all 10 of its
expectations were assessed as correct and none needed weakening or correcting.
Per-file hashes after the slice are in `slice-01-after-sha256.txt`.

## 3. Verification

Source identity: HEAD `48b11c6cf08200de363e108924e42fdbc52d83e8`, version
0.12.2, dirty tree, `uv`-managed Python 3.14.2. Every run used the checkout via
`uv run`; `/opt/homebrew/bin/sxr` was never invoked or modified.

| Check | Command | Baseline | After | Evidence |
|---|---|---|---|---|
| Full suite | `uv run pytest -q` | 642 tests, **8 failed** | **676 tests, 0 failed** | `evidence/baseline-pytest.{log,xml}`, `evidence/after-pytest.{log,xml}` |
| Affected matrix | `uv run pytest -q tests/test_views.py tests/test_prompts.py tests/test_prompt_defaults.py tests/test_prompt_limits.py tests/test_output_contracts.py tests/test_file_selection.py tests/test_read_cache.py tests/test_codex_outcomes.py tests/test_lazy_discovery.py tests/test_show_boundaries.py tests/test_audit_retrieval.py` | — | 208 passed, exit 0 | `evidence/matrix-pytest.log` |
| Lint | `uv run ruff check .` | exit 0 | exit 0 | `evidence/baseline-lint.log`, `evidence/lint.log` |
| Format | `uv run ruff format --check .` | exit 0 | exit 0 | `evidence/baseline-format.log`, `evidence/format.log` |
| Conventions | `uv run konpy validate` + `konpy check` | 96 files, 0 violations | 98 files, 0 violations | `evidence/baseline-konpy-check.log`, `evidence/konpy-{validate,check}.log` |
| Historical CLI contracts | `uv run python audit/2026-09-10/verify_cli.py --output …` | not measured | **66 of 67 passed**, `PROMPTS-filter` failed | `evidence/historical-contracts.{log,json}` |
| Migrated prompt contracts | `uv run python audit/2026-09-11/cli-refactor/verify_prompts.py` | — | 5 of 5 passed | `evidence/migrated-contracts.{log,json}` |

**Baseline failures (8, all pre-existing):** every case in
`tests/test_prompt_defaults.py` — the interrupted proposal tests of `EXTRA-021`.
All 8 now pass. **New failures: none.**

**The one intentional historical break.** `PROMPTS-filter` in the preserved
2026-09-10 contract suite asserts `len(prompts --all --json) == 6`. That is the
old `--all` meaning this task deliberately replaces, so the check now fails by
design; the historical file is left untouched as evidence. Its intent is
re-verified under the new names by `verify_prompts.py`, which runs against the
same audit corpus and confirms: default selects exactly the 3 human prompts,
`--include-context` restores all 6 user-role records, `--all` produces
byte-identical output to the default, `--all` lifts an explicit `-n 1`, and no
environment budget trims the plain view.

**Checks not run, and why.** Bundle build and relocation verification
(`packaging/`) — no entry point, dependency or packaging file was touched, and
`packaging/verify.py` already carries unrelated uncommitted edits. No release,
install, publish or real-transcript rewrite (out of handoff scope). Linux and
x86_64 behavior — unavailable on this machine. The other 20 command surfaces were
exercised only through the test suite and the 67-check contract suite, not
re-probed by hand.

## 4. Compatibility and limitations

**Breaking:** `--all` no longer widens selection. Scripts relying on
`sxr prompts --all` to capture injected context or tool results must move to
`--include-context`. The migration note is in the README prompts section and in
`prompts --help`. `sxr prompts` default output can now be far larger — that is
the point of the change, and `--budget N` restores compact output.

**Preserved:** provider defaults, `--file` selection equivalence, raw-record
JSON shapes, physical-record dedup with omission counts on stderr
(`SXR-AUD-005`), `-n 0` unlimited, negative `-n` exits 2 at both flag positions
(`SXR-AUD-012`), exit 1 on an empty prompt selection, and every other
`SXR-AUD-0xx` fix (66 of 67 contracts pass unchanged).

**Limitations.**

1. `sxr prompts @1:@2` still reads only the first resolved session. Unchanged by
   this slice; scoped as SXR-CLI-02. This boundary was kept deliberately because
   honoring ranges needs per-session identity in `show`, `prompts` and `tools`
   together.
2. Under `--include-context`, an unpaired tool result renders as
   `result  () "text"` — the empty parentheses come from
   `views_read.event_line`, shared with `show`, and predate this slice. Fixing
   it changes `show` output, so it belongs to SXR-CLI-03/04.
3. `--line-limit` alone uses `SXR_BUDGET` (or 40000) as its threshold. The
   option is an explicit compact request, so an environment budget can influence
   *how much* is trimmed, but never *whether* the plain view trims.

**Decisions the reviewer needed to make — all three resolved on 2026-09-11; see
the table at the top of this file. The questions are kept verbatim below so the
reasoning behind each answer stays readable.**

1. **Is `--all` beating an explicit `-n`/`--budget` the precedence you want?**
   This slice implements it that way, matching the draft test
   `test_all_lifts_explicit_limits_without_adding_context`. The alternative —
   last-flag-wins, or explicit limits beating `--all` — is defensible and would
   be a one-line change plus test updates.
2. **Should negative `--budget`/`--line-limit` become usage errors** as
   `PAR-prompts-typer-line_cap` proposes? Slice 01 defines them as "no
   trimming" because both are shared `flags.py` types also used by `show`;
   rejecting them is a `show` change belonging to SXR-CLI-03.
3. **Is the migration note sufficient**, or should `--all` warn on stderr for a
   release or two when it is used with a limit flag it now overrides?

## 5. Ledger and next slice

[ledger.md](ledger.md): SXR-CLI-01 `delivered`, awaiting review. 23 remaining
tasks proposed. All 408 CSV rows mapped — 136 into tasks, 195 duplicates of a
canonical row, 37 retained, 37 deferred, 3 needing a human decision.

One of those 3 needs your attention before its task can be scoped at all:
`PAR-tools-typer-limit` proposes that `-n` cap the keys inside the
`tools --json` aggregate, which contradicts the already-fixed `SXR-AUD-007`
contract that aggregate objects retain all their fields. The other two ask
whether `secrets clean --json` may gain a typed operation-summary record, and
whether skipped-live files would then change its exit code.

**Next proposed slice: SXR-CLI-02 — honor multi-session ranges in `show`,
`prompts` and `tools`.** It depends on this one: both slices edit the prompts
renderer and its `cli.py` call site, and per-session identity headers only make
sense once the record shape and completeness rules are settled. It is also the
smallest next step that closes a silent data-loss defect — `handles.resolve`
returns every reference of `@A:@B` while all three commands take `[0]`.

Work stops here for review, per the handoff. No second slice was started.
