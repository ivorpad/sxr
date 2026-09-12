# Review packet — SXR-CLI-03, one documented selection pipeline for show

Delivered 2026-09-11. Nothing was committed; the change sits in the working tree
alongside the pre-existing remediation work, slice 1 and slice 2.

## 1. What was asked, and what the invocation looks like now

Task `SXR-CLI-03`. CSV rows, re-read against this slice's baseline source before
any edit (`audit/2026-09-10/command-review/commands-before-after.csv`):

| row | its ask | closed here? |
|---|---|---|
| `CMD-show-typer` | compose filters in a documented order; add `--tool-results` | yes |
| `EXTRA-008` | one sequence window, then kind/error filters, then tail, then count/format | yes |
| `PAR-show-typer-around` | require a positive coordinate; intersect `--type`; reject `--range` | yes |
| `PAR-show-typer-context` | require a nonnegative half-width; require `--around` | yes |
| `PAR-show-typer-range_` | positive ordered bounds; intersect `--type`; keep the `A-B` alias | yes |
| `PAR-show-typer-type_` | name the kind in help, list known kinds, compose with windows, informative empty notice | yes for sequence windows; `show` has no time window to compose with |
| `PAR-show-typer-thinking` | document the combination rules, no silent override | yes |
| `PAR-show-typer-errors` | filter errors *inside* the window / `--full` set | yes |
| `PAR-show-typer-full` | `--full` = all kinds + no trim; explicit filters still narrow it; `-n` still applies | yes |
| `PAR-show-typer-tools` | `--tool-results` primary, `--tools` alias | yes (was `deferred`; see §4) |
| `PAR-show-typer-arg` | the filter-precedence and `--tools` clauses left over from slice 2 | yes — the row is now fully closed |
| `PAR-show-typer-tail` | state the unit; keep `0`/negative behavior | partly: the JSON-counts-distinct-records clause is **not** done (§4) |
| `PAR-show-typer-budget` | reject negatives, keep `0` as disabled | the negatives clause only; the row stays owned by SXR-CLI-21 |
| `PAR-show-typer-line_cap` | reject negatives, `0` = no per-line trim | the negatives clause only; the uniform-cap clause stays with SXR-CLI-21 |
| `EXTRA-049` | `--tool-results` as a clear primary name | yes (was `deferred`; same clause as `PAR-show-typer-tools`) |

Concrete before/after, on the synthetic 9-record fixture:

```
$ sxr show --full --errors          # before
#0001  08:00:00  user   text    "human ask one"
#0002  08:00:01  asst   think   "weighing options"
#0003  08:00:02  asst   text    "short answer"
#0004  08:00:03  asst   tool    Bash "true" -> ok
#0005  08:00:04  user   result  (Bash) "fine"
#0006  08:00:05  asst   tool    Bash "false" -> err
#0007  08:00:06  user   result  (Bash, is_error) "exploded on purpose"
#0008  08:00:07  sys    system. a meta record
#0009  08:00:08  asst   text    "a long assistant answer that repeats itself. ..."

$ sxr show --full --errors          # after
#0006  08:00:05  asst   tool    Bash "false" -> err
#0007  08:00:06  user   result  (Bash, is_error) "exploded on purpose"
```

`--full` used to short-circuit `_default_pick` before the error branch, so asking
for "every error, whole text" printed the whole transcript. Two more:

```
$ sxr show --type tool --around 6 --context 1
  before: both tool calls (#0004 and #0006) -- --type discarded the window
  after:  #0006 only -- the window and the kind intersect

$ sxr show --around 5 --range 1:3
  before: exit 0, the --around window; --range was silently ignored
  after:  exit 2, "error: --around and --range are two different windows; use one"
```

## 2. The bounded diff

`slice-03.patch` (1031 lines, 667 added, 133 removed, 11 files) is
`diff -ruN` from `baseline-03/worktree-snapshot.tar.gz` to the working tree, over
the same file set (`src tests docs packaging README.md CLAUDE.md konpy.json
pyproject.toml justfile`, tracked plus untracked). Regenerating it twice gives
byte-identical output (`sha256 32240fa03cf68c37f7e70bec306c7236988720fbf0153cb951656b97d611be9a`).
`slice-03-after-sha256.txt` hashes all 112 files of the resulting tree.

The baseline was taken before the first edit and is stored separately from slice
1's `baseline/` and slice 2's `baseline-02/`, both of which are unchanged:

| artifact | sha256 |
|---|---|
| `baseline/worktree-snapshot.tar.gz` | `9558a49cddbfc8e4b7df872b4518bcbab96133b04455bb24465212f4dc696360` |
| `baseline-02/worktree-snapshot.tar.gz` | `b96e220b00d590dfc16411ccef878dcfb650748bf54582863a223d2719ca2dbc` |
| `slice-01.patch` | `6397a67f211c6a09687e8efae72e825678e6b0448c5ce68bb23048eaf72c0af2` |
| `slice-02.patch` | `54427770fd1594cbcc6ee64fa70dd9251c5538806f9b5476770b8be9c837f1b6` |

## 3. Source identity, files, and verification

`HEAD` is still `48b11c6cf08200de363e108924e42fdbc52d83e8`, matching
`baseline-03/head.txt`. `git stash list` is empty. All 48 `git status` entries
recorded in `baseline-03/git-status.txt` are still present; nothing was stashed,
reset, reverted or committed.

Changed files:

| file | change |
|---|---|
| `src/sxr/show_select.py` | **new**, 163 lines: `ShowOpts`, `validate`, `parse_range`, the four pipeline stages, `is_zoom`/`is_skeleton`, `empty_reason` |
| `src/sxr/views_read.py` | 254 -> 189 lines: selection moved out; it now only displays what survived, and reports an empty selection on stderr |
| `src/sxr/show_command.py` | new option bounds and names, `--tool-results`/`--tools`, `--context` defaulted to `None` so "explicitly supplied" is knowable, `validate` before discovery |
| `src/sxr/flags.py` | `min=0` on `BudgetF` and `LineLimitF` (both used only by `show`; `prompts` has its own `PromptBudgetF`/`PromptLineLimitF`, untouched) |
| `src/sxr/read_positions.py` | imports the pipeline from its new home; the cached path reuses the same code |
| `src/sxr/onboard.py` | `EPILOG` gains a `show selection` paragraph and one example; `PRIMER_BODY` deliberately untouched, so no primer version bump |
| `README.md` | the selection order, the rejected inputs, and two examples |
| `tests/test_show_pipeline.py` | **new**, 376 lines, 80 cases across both providers |
| `tests/test_read_cache.py`, `tests/test_views.py`, `tests/test_codex_outcomes.py` | import the pipeline from `show_select`; the hidden-kind note now names `--tool-results` |

Commands, all `uv run` against this checkout. The installed
`/opt/homebrew/bin/sxr` was never invoked.

| command | baseline | after |
|---|---|---|
| `uv run pytest -q` | 745 passed, 0 failed | **825 passed, 0 failed** (+80) |
| `uv run ruff check .` | exit 0 | exit 0 |
| `uv run ruff format --check .` | exit 0, 153 files | exit 0, 159 files |
| `uv run konpy validate` | exit 0 | exit 0 |
| `uv run konpy check` | 100 files, 0 violations | 102 files, 0 violations |
| `audit/2026-09-10/verify_cli.py` | 66 passed, 1 failed | 66 passed, 1 failed |
| `cli-refactor/verify_prompts.py` | 5 passed, 0 failed | 5 passed, 0 failed |

Logs and JSON for every row are in `evidence-03/`, named `baseline-*` and
`after-*`/plain. No `konpy: ignore` suppression exists anywhere in `src` or
`tests`.

**New failures: none.** **Pre-existing failures: one.** `PROMPTS-filter` in
`audit/2026-09-10/contract_checks.py` fails at this slice's baseline and after
it, for the reason it has failed since slice 1: it asserts the pre-slice-1
meaning of `prompts --all`. **No historical contract changed status.** Every
other one of the 67 checks passes.

Compatibility by capture: `evidence-03/before/` and `evidence-03/after/` hold the
same 48 `show` invocations. `before/` was produced by running the same harness
with `sys.path` pointed at the extracted `baseline-03` snapshot, after confirming
all 110 extracted files hash-match `baseline-03/sha256.txt`.
`evidence-03/before-after-index.txt` marks each case and gives a reason for every
change: **17 unchanged, 31 changed.**

The 17 byte-identical cases are the shapes existing scripts use: `--around`,
`--around --context`, `--range`, `--range` with the `A-B` alias, `--tail`,
`--type text`, `--type result`, `--type` with `--tail`, `--full`, `--full --type`,
`--tools`, `--errors --json`, `--errors --tail`, `--around --thinking`, plain
`--json`, and two Codex cases.

Slices 1 and 2 re-verified: `verify_prompts.py` is 5/5, and
`capture_ranges.py` was rerun into `evidence-03/ranges-after/` and compared case
by case to `evidence-02/after/` in `evidence-03/slice-02-still-green.txt` — 22 of
28 byte-identical, and the 6 that differ do so only by the renamed
`--tool-results` flag in `show`'s hidden-kind note plus, in one case, the new
empty-selection notice on stderr. Banners, the shared `-n` allowance, the
`--json` record contracts and the exit codes all reproduce unchanged, and
`test_single_session_output_is_unchanged` still pins `@1 == @1:@1` inside this
slice's own run.

Preserved and proven by test:

- Raw JSON is still whole physical records, deduplicated per transcript
  (`test_json_prints_whole_physical_records_once`), and the pipeline decides the
  same set in both formats (`test_json_selection_matches_the_text_selection`).
- Physical line identity: `#0006` still means source line 6; the window stages
  read `event.seq` and nothing renumbers.
- Exit codes: 0 with content, 1 on an empty selection, 2 on usage. SXR-AUD-011
  (`--tail 0` -> 1, negative tail -> 2), SXR-AUD-012 (negatives rejected before
  discovery — `test_context_is_rejected_before_discovery` monkeypatches
  `flags.sessions` to fail if discovery runs), SXR-AUD-005/006/007 all still
  covered by the untouched `tests/test_output_contracts.py`.
- Provider defaults and `--file` selection: unchanged, and every pipeline test
  runs against both a Claude transcript and a Codex rollout.
- Cache parity: `test_cached_and_uncached_selections_agree` runs five
  combinations warm, warm again, and with `SXR_NO_CACHE=1`, requiring identical
  stdout and exit code, because `read_positions.select_rows` reuses the same
  pipeline over event metadata.

## 4. Compatibility, decisions, limitations

**Intentional behavior changes** (all in `before-after-index.txt`):

1. `--full --errors` prints only error records. `--full` now means "all kinds,
   no trimming" and stops overriding explicit filters.
2. `--type` intersects `--around`/`--range` instead of discarding them.
3. `--around`/`--range` intersect `--errors` instead of discarding it.
4. `--around` below 1, negative `--context`, `--context` without `--around`,
   `--range` outside `0 < A <= B`, and `--around` together with `--range` are
   usage errors (exit 2). Each was previously a quiet empty success, or a silent
   winner.
5. Negative `--budget`/`--line-limit` on `show` are usage errors (see the
   decision below).
6. `--tool-results` is the primary name; `--tools` still selects the same
   records. `show`'s hidden-kind note names the new primary spelling, which is
   the only reason six otherwise-unchanged captures differ.
7. An empty selection now says on stderr which selectors emptied it, and for a
   mistyped `--type` points at `sxr stats` for the kinds a session recorded.
   `--json` stdout stays empty, so the record contract is untouched.
8. `show --errors` no longer prints the `# hidden:` note. That note explains what
   the *default skeleton* held back; under an explicit error filter it listed
   "hidden tool results" while error-bearing tool results were being printed. Not
   requested by a CSV row — flagged here as a judgment call.

**Decision made — negative `--budget`/`--line-limit` on `show` (ledger open
decision 1, inherited from D-02): reject them, exit 2.** Reasoning:

- `PAR-show-typer-budget` and `PAR-show-typer-line_cap` both ask for it, and the
  former's acceptance clause is explicit: "negative input is a usage error".
- The negative spelling is a redundant synonym today. `--budget -1` means exactly
  what `--budget 0` means, and only `0` is documented, so nothing is lost that
  has a name.
- This slice already rejects the same class of meaningless input (`--around 0`,
  `--range 5:1`, `--context -1`). Accepting a negative budget while rejecting a
  negative context would be inconsistent inside one command.
- It does not touch `prompts`. Since slice 1 the two commands have separate
  option types, so D-02's "keep meaning no trimming" survives verbatim for
  `prompts`, and `test_negative_character_limits_never_truncate` was not
  modified and still passes.

The cost is a deliberate asymmetry: `sxr show --budget -1` exits 2 while
`sxr prompts --budget -1` prints complete text. That is defensible because the
flags mean different things (`show`'s is a threshold with a positive default;
`prompts` has no default and supplying the flag is what requests compact text),
but if the reviewer prefers symmetry, D-02 has to be reopened rather than this
slice changed.

**D-04 honored.** The `# session @N <short id> <file>` banner is byte-identical
across `show`, `prompts` and `tools`; `session_scope.py` was not touched. The
duplication with `show`'s `file:` header line remains. This slice reworked
`show`'s *selection*, not its header, so the natural-consequence permission never
came into play, and the three formats were not diverged.

**Not closed, and named as such:**

- `PAR-show-typer-tail`'s clause "make JSON selection limits count complete
  distinct source records". `--tail 3 --json` still tails 3 normalized events,
  which can dedup to fewer physical records. Changing it would redefine `--tail`
  per output format and interacts with SXR-AUD-005/007, so it needs its own
  decision rather than a quiet change here.
- `PAR-show-typer-line_cap`'s clause "apply the same explicit cap policy to all
  displayed event kinds". Tool-result bodies still go through
  `util.middle_trim`'s fixed widths and ignore `--line-limit`. That row stays
  owned by SXR-CLI-21.
- `PAR-show-typer-type_`'s "compose with time windows": `show` has no time
  window (`--since`/`--before` are scope filters), so there is nothing to
  compose with. Recorded in the disposition note rather than claimed as done.

**Disposition changes.** Two rows moved: `PAR-show-typer-tools` and `EXTRA-049`
from `deferred` to `task:SXR-CLI-03`, because `CMD-show-typer`'s `after` cell —
this slice's canonical row — carries the same `--tool-results` clause, so
delivering the command row delivered them. Tallies in `disposition.md` now read
task 138, deferred 35, and a check asserts the markdown and the JSON agree on all
408 rows. Recorded under `verified_against_source["2026-09-11 SXR-CLI-03"]`.

**A defect I introduced in slice 2, found while auditing this slice.**
`audit/2026-09-10/verify_cli.py` defaults `--output` to
`audit/2026-09-10/evidence/contracts.json`. During slice 2 I ran it once without
`--output`, which overwrote that historical file at 13:57 local with the
post-slice-1 result (66 passed / 1 failed). The original 2026-09-10 audit
measurement is no longer in that JSON. What survives:
`audit/2026-09-10/evidence/contracts.log` (untouched, 2026-09-10 10:52) is the
text output of the same original run and lists every check's PASSED/FAILED, and
the post-remediation 67/0 measurement is intact in
`audit/2026-09-10/remediation/final-contracts.json`. I did not try to
reconstruct the JSON, because inventing bytes for a historical evidence file is
worse than reporting the gap. Every slice-3 invocation passed `--output`
explicitly into `evidence-03/`, and nothing else under `audit/2026-09-10/` has an
mtime later than 2026-09-10.

**Not done / not available:** no bundle build, packaging check or relocation
test — no entry point, dependency or packaging file was touched, and
`packaging/verify.py` already carries unrelated uncommitted edits. Nothing was
published, installed or released. No real transcript was read or rewritten; every
fixture is synthetic, written into a temporary directory, with temporary cache
roots. No secret value appears in any output. Linux and x86_64 are unavailable on
this machine. Command surfaces other than `show` were exercised only through the
test suite and the 67-check contract suite.

## 5. Ledger and the next slice

`ledger.md` now records SXR-CLI-01 and SXR-CLI-02 as **accepted 2026-09-11**,
SXR-CLI-03 as **delivered 2026-09-11** with this packet, `slice-03.patch` and
`evidence-03/` as its evidence, and D-04 in the resolved-decisions table
(originating reviewer, 2026-09-11). Open decision 0 (the banner question) is gone
because D-04 answered it; open decision 1 (negative budgets) moved into a new
"Decided by a slice, awaiting the reviewer's confirmation" table as **S-01**,
with the asymmetry against `prompts` stated, because that choice was mine and
still needs your sign-off rather than sitting among your own decisions.
`tasks.md`
marks SXR-CLI-02 accepted and SXR-CLI-03 delivered, and lists the two clauses
this slice did not close.

Proposed next slice: **SXR-CLI-04 — `errors`: source identity and complete text
by default.** It is the next `intentional-behavior-change` in dependency order,
its rows (`CMD-errors-typer` and three `PAR-errors-typer-*`) are already scoped,
and it touches `views_read.errors`, the one function left in `views_read.py` that
this slice did not rework — so the module's second concern gets resolved while the
file is fresh. It also needs the same range-identity treatment slice 2 gave the
other three commands, which is now a settled pattern.
