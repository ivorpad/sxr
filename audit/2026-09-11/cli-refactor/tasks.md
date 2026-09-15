# sxr CLI refactor: staged task list

Derived from `audit/2026-09-10/command-review/commands-before-after.csv` (408 rows, SHA-256 `c24d00ed08a09caed659c8ab3298db0b2b1166fa97f204742447f3662b1f63e4`). Every row's outcome is in [disposition.md](disposition.md) / [disposition.json](disposition.json). `SXR-CLI-01` is reserved and already in flight; the rest are proposals awaiting approval, in the sequence below.

**Preserved contracts (SXR-AUD-001..017, already fixed — no task may undo them).** Cleaning row limits affect reporting only, never which files are processed or rewritten; `-n 0` is unlimited; negative row limits and negative tails exit 2; `--tail 0` selects nothing and exits 1; an empty session listing still exits 0; `show`/`prompts`/`errors` deduplicate complete physical JSON records and report omission counts on stderr; tools/stats JSON aggregate objects keep all their fields.

**Both dispatch paths.** `sxr find|skills|serve` as `argv[1]` go to argparse (`src/sxr/__init__.py`); everything else, and any root-flag-prefixed invocation, goes to Typer. Tasks 15, 16, 17, 18, 21 and 22 touch shared option or root-flag behavior and must land the change, help and validation on **both** paths. Tasks 02–14 are Typer-only unless stated.

**Conventions (every task).** `src/**/*.py` ≤ 300 lines, `tests/**/*.py` ≤ 400 lines, docstrings on every module, public class and public function in `src/sxr/**`, and never add a `konpy: ignore[...]` suppression — split the module or ask a human instead.

**Source snapshot.** HEAD is `48b11c6` but the working tree carries the uncommitted 17-finding
remediation plus the in-flight SXR-CLI-01 slice, so line numbers below are from the tree as read on
2026-09-11 and will drift. Where a CSV `before` cell no longer matches the tree, the task states the
tree's behavior, not the cell's.

**Classes.** `defect` = current behavior contradicts its own help or another command. `intentional-behavior-change` = a deliberate, documented break. `optional-addition` = new surface, nothing existing changes. `mechanical` = help/visibility/wiring with no behavior change.

---

## SXR-CLI-01 — complete human prompts  *(ACCEPTED 2026-09-11)*

- **class:** intentional-behavior-change
- **rows:** CMD-prompts-typer, PAR-prompts-typer-include_all, PAR-prompts-typer-budget, PAR-prompts-typer-line_cap, EXTRA-003, EXTRA-021, EXTRA-040
- **before:** `sxr prompts` trims prompt text as soon as the selected text exceeds `--budget` / `SXR_BUDGET` (default 40000) with lines capped at `SXR_LINE_LIMIT`, so complete prompts require `-n 0 --budget 0`; `--all` drops the provenance predicate and adds injected instructions and tool results. As of 2026-09-11 the in-flight slice has already moved this view to `src/sxr/views_prompts.py` and added `--include-context`, so these CSV `before` cells are now historical.
- **after:** plain `sxr prompts` prints every qualifying human prompt verbatim and ignores `SXR_BUDGET`/`SXR_LINE_LIMIT`; `--all` lifts output limits without changing which records qualify; new `--include-context` is the explicit selector for other user-role records (injected instructions, tool results) with provenance labelled; explicit `-n`/`--budget`/`--line-limit` still give compact output with tested precedence against `--all`; `--json` keeps complete source records with physical-record dedup.
- **files as delivered:** `src/sxr/views_prompts.py` (new), `src/sxr/views_read.py`, `src/sxr/cli.py`, `src/sxr/flags.py`, `src/sxr/onboard.py`, `README.md`; `tests/test_prompt_limits.py` (new), `tests/test_prompts.py`, `tests/test_views.py`. `tests/test_prompt_defaults.py` and `src/sxr/output.py` were left unchanged.
- **deps:** none
- **accept:** under `SXR_BUDGET=1 SXR_LINE_LIMIT=5`, every human prompt appears in full; `--all` selects the same record set as the default; `--include-context` adds the injected records and labels each with its recorded provenance; `--all` **lifts** an explicit `-n`/`--budget` at either flag position (this is the chosen precedence — `--all` means completeness, so it wins); `--budget 0` beats `--line-limit`; negative `--budget`/`--line-limit` never truncate; negative `-n` still exits 2; `prompts --json` emits each physical line exactly once; Claude and Codex plus legacy unlabelled provenance and a Codex compaction boundary all covered.
- **review:** selection logic separated from display logic; each of the 10 expectations in `tests/test_prompt_defaults.py` accounted for. See `review-slice-01.md`.
- **decisions resolved on acceptance (originating reviewer, 2026-09-11), all scoped to `sxr prompts`:** `prompts --all` keeps overriding an explicit `-n`/`--budget` (D-01; `grep --all` was given the same precedence by SXR-CLI-07, and `--all` means completeness on both); negative `--budget`/`--line-limit` keep meaning "no trimming" **on `prompts` only** (D-02 -- `show` rejects them per D-05 and `grep` followed `show` in SXR-CLI-21, so do not read this row as a rule for every command); the README plus `prompts --help` note is a sufficient migration path, with no stderr deprecation warning. See `ledger.md`.

## SXR-CLI-02 — honor multi-session ranges in show, prompts, tools  *(ACCEPTED 2026-09-11)*

- **class:** defect
- **rows:** PAR-show-typer-arg, PAR-prompts-typer-arg, PAR-tools-typer-arg, EXTRA-004
- **before:** `handles.resolve` returns every reference of `@A:@B`, but `show_command.py:38`, `cli.py:116` (prompts) and `cli.py:159` (tools) take `[0]`, so `sxr show @1:@3` silently reads one session and reports nothing about the discarded ones.
- **after:** all three commands process every resolved reference in scope order and identify the owning session and file per block (text) or per record (JSON); exit 1 only when no selected session produced output. **Boundary:** this task adds no selection flags and does not change prompt completeness (01) or show filter composition (03); it is deliberately separate from 01.
- **files:** `src/sxr/show_command.py`, `src/sxr/cli.py`, `src/sxr/views_read.py`, `src/sxr/views_prompts.py`, `src/sxr/views_info.py`; `tests/test_show_boundaries.py`, `tests/test_record_shape.py`
- **deps:** SXR-CLI-01 (same renderer; prompt output shape settles first)
- **accept:** `show @1:@2` prints two session headers; `prompts @1:@2` prints prompts from both; `tools @1:@2` prints one identified summary per session; single-reference output is byte-identical to today; `-n` remains one allowance shared across the range.
- **review:** no `[0]` truncation of a resolved reference list remains; every text block names its session; JSON records still deduplicated per physical line.
- **files as delivered:** `src/sxr/session_scope.py` (new), `src/sxr/show_command.py`, `src/sxr/cli.py`, `src/sxr/views_read.py`, `src/sxr/views_prompts.py`, `src/sxr/views_info.py`, `src/sxr/output.py`, `src/sxr/flags.py`, `src/sxr/onboard.py`, `README.md`; `tests/test_session_range.py` (new, 69 cases). `tests/test_show_boundaries.py` and `tests/test_record_shape.py` needed no change: the existing contracts they pin all still hold.
- **as delivered:** identity is one banner, `# session @N  <short id>  <file>`, printed only when the selection holds more than one session — stdout for text, stderr for `--json` so raw JSONL stdout stays parseable. `-n` is one allowance for the whole invocation; selection filters (`--around`, `--range`, `--type`, `--tail`, `--errors`) stay per session. Single-session and `@N:@N` output are byte-identical, proven by capture (`evidence-02/before-after-index.txt`). See `review-slice-02.md`.
- **decision resolved on acceptance (originating reviewer, 2026-09-11, D-04):** keep the uniform `# session @N <short id> <file>` banner across all three commands, duplication with `show`'s `file:` header line included. Consistency wins; SXR-CLI-03 may revisit the duplication only as a consequence of reworking `show`'s header, and must not diverge the three banner formats to remove it.

## SXR-CLI-03 — one documented selection pipeline for show  *(ACCEPTED 2026-09-11)*

- **class:** intentional-behavior-change
- **rows:** CMD-show-typer, PAR-show-typer-around, PAR-show-typer-context, PAR-show-typer-range_, PAR-show-typer-type_, PAR-show-typer-tail, PAR-show-typer-thinking, PAR-show-typer-errors, PAR-show-typer-full, EXTRA-008
- **before:** `views_read._base_selection` branches in order `--type` → `--around` → `--range` → skeleton, so `--type` silently discards `--around`; `--full --errors` prints non-error records; `--around 0`/negative and negative `--context` are accepted; a reversed `--range 5:1` returns empty.
- **after:** one order — window (`--around` xor `--range`), then kind (`--type`), then `--errors`, then `--tail`, then `-n`/format. `--full` means all kinds plus no trimming, and explicit filters still narrow it. `--around` requires ≥ 1, `--context` requires ≥ 0 and requires `--around`, `--range A:B` requires 0 < A ≤ B, `--around` with `--range` exits 2.
- **files:** `src/sxr/views_read.py`, `src/sxr/show_command.py`; `tests/test_show_boundaries.py`
- **deps:** SXR-CLI-02
- **accept:** `--full --errors` prints only error-bearing events, untrimmed; `--type tool --around 40` intersects; `--around 0`, `--range 5:1`, `--around 10 --range 1:5`, `--context -1` all exit 2; `--tail 0` still exits 1 and negative tails still exit 2.
- **review:** the precedence order printed in `show --help` matches the implemented order; audit-fixed exit codes unchanged.
- **rows also closed:** PAR-show-typer-arg (its leftover filter-precedence and `--tools` clauses), PAR-show-typer-tools and EXTRA-049 (both moved from `deferred`, because CMD-show-typer's `after` cell carries the same `--tool-results` clause).
- **files as delivered:** `src/sxr/show_select.py` (new, 163 lines: the whole pipeline), `src/sxr/views_read.py` (254 → 189 lines; display only), `src/sxr/show_command.py`, `src/sxr/flags.py`, `src/sxr/read_positions.py`, `src/sxr/onboard.py` (`EPILOG` only), `README.md`; `tests/test_show_pipeline.py` (new, 80 cases, both providers), `tests/test_read_cache.py`, `tests/test_views.py`, `tests/test_codex_outcomes.py` (imports plus the renamed flag in the hidden-kind note). `tests/test_show_boundaries.py` needed no change: every contract it pins still holds.
- **as delivered:** four stages, in `show_select.selected` — window (`--around` ± `--context`, or `--range A:B`, never both), then kind (`--type`, else the skeleton widened by `--thinking`/`--tool-results`, else every kind once a window/`--full`/`--errors` asked for more), then `--errors`, then `--tail`; `-n` and trimming stay in `views_read.show`. `--tool-results` is the primary name with `--tools` as the alias. An empty selection reports on stderr which selectors emptied it, and `--json` stdout stays a pure record contract. Byte compatibility proven by capture: 17 of 48 invocations unchanged, every change reasoned in `evidence-03/before-after-index.txt`. See `review-slice-03.md`.
- **decision made here, accepted as D-05 (originating reviewer, 2026-09-11):** negative `--budget`/`--line-limit` on `show` are usage errors (exit 2), on `PAR-show-typer-budget`'s own acceptance clause and for consistency with the other meaningless windows this slice rejects. The asymmetry with `prompts` is accepted deliberately and is now pinned in `contracts.md` so a later slice cannot harmonize the two by accident. `prompts` is untouched — the two commands have had separate option types since slice 1 — so `tests/test_prompt_limits.py::test_negative_character_limits_never_truncate` was not modified and still passes. The resulting asymmetry is stated in `review-slice-03.md` §4.
- **not closed by this slice:** PAR-show-typer-tail's "JSON selection limits count complete distinct source records" (`--tail` still counts normalized events before per-record dedup; it interacts with SXR-AUD-005/007 and needs its own decision), and PAR-show-typer-line_cap's "same explicit cap policy for all event kinds" (tool-result bodies still use `util.middle_trim`'s fixed widths; that clause stays with SXR-CLI-21).

## SXR-CLI-04 — errors: source identity and complete text by default  *(ACCEPTED 2026-09-11)*

- **class:** intentional-behavior-change
- **rows:** CMD-errors-typer, PAR-errors-typer-arg, PAR-errors-typer-limit, EXTRA-041
- **before:** `views_read.errors` middle-trims every text row to 200+120 chars and prints only `#seq  time  tool`, so two errors at seq 12 in different sessions are indistinguishable and whole error text needs `--json` or another command.
- **after:** each text row carries the owning session short id plus sequence; complete error text prints by default; new `--compact` restores the trimmed one-line form; `-n` stays a single global allowance across selected sessions and `--json` keeps complete distinct records.
- **files:** `src/sxr/views_read.py`, `src/sxr/cli.py`; `tests/test_output_contracts.py`, `tests/test_record_shape.py`
- **deps:** none (errors already resolves ranges)
- **accept:** two synthetic sessions each with an error at seq 12 → both rows distinguishable; a 5000-char error prints whole by default and trimmed under `--compact`; `-n 1` across two sessions prints one row and the omitted count (stderr in JSON mode).
- **review:** `middle_trim` reachable only via `--compact`; the shared row allowance of SXR-AUD-006 intact.
- **delivered:** `views_read.errors` split into `error_records`/`error_line`/`errors`; `--compact` added in `cli.py`; `EPILOG` and `README.md` document the order; `tests/test_errors_view.py` adds 38 cases across both providers. 863 tests pass, 0 failures; konpy 103 files, 0 violations; both contract suites unchanged. Within `errors`, `middle_trim` is now reached only from the `--compact` branch of `error_line`. Also fixed two latent zoom-hint defects (it read the last ref's `picked` list, and was suppressed for ranges). Evidence: `evidence-04/`, packet: `review-slice-04.md`, diff: `slice-04.patch`.
- **deferred clauses:** `--tail` under `--json` (a `show` clause) is **left** untouched — `errors` has no `--tail` and already collapses to distinct physical records before counting. SXR-CLI-21's `--line-limit` clause is **touched, not closed**: the default path no longer trims at all, but `--compact` still uses `middle_trim`'s fixed widths and `errors` has no `--line-limit`.

## SXR-CLI-05 — cmds: a filter no longer changes session scope  *(ACCEPTED 2026-09-12)*

- **class:** intentional-behavior-change
- **rows:** CMD-cmds-typer, PAR-cmds-typer-arg, PAR-cmds-typer-grep_, EXTRA-044
- **before:** `cli.py:270` reads `sessions if arg is None and grep_ else resolve(arg, sessions)`, so a nonempty `--grep` with no selector silently searches every session in scope; the generated primer advertises exactly that (`cmds --grep "git push"  # ALL sessions`).
- **after:** no selector always means the newest session; new `--all-sessions` selects every scoped session with or without `--grep`; help, README and the generated primer teach `--all-sessions`.
- **files:** `src/sxr/cli.py`, `src/sxr/views_info.py`, `src/sxr/search_index.py`, `src/sxr/onboard.py`; `tests/test_search_index.py`, `tests/test_output_contracts.py`
- **deps:** none
- **accept:** with two matching sessions, `cmds --grep "git push"` prints newest-session rows only; `cmds --all-sessions --grep "git push"` prints both; `cmds --all-sessions` alone lists every session's calls; no match exits 1.
- **review:** the scope decision no longer reads the filter value, **and** a human signs off on breaking the documented primer recipe (it ships inside `AGENTS.md`/`CLAUDE.md` blocks in the wild).
- **delivered:** `cli.py` gained `--all-sessions`; the scope line reads `sessions if all_sessions else resolve(arg, sessions)`, so the filter value no longer reaches it. `--all-sessions` with a selector is exit 2. A filtered search that *defaulted* its scope discloses what it skipped and names the flag — on stderr when empty, otherwise as one `#` note — while any chosen scope prints nothing new, which is what keeps 24 of 44 captures byte-identical. `PRIMER_BODY`'s `cmds` recipe, the `EPILOG` example and `README.md` teach `--all-sessions`; the version moved 0.12.2 → 0.14.0 in `__init__.py`, `pyproject.toml` and `uv.lock`, and this repo's own `CLAUDE.md` primer was reinstalled with `sxr init --write` (it had been stale at v0.3.0). `tests/test_cmds_scope.py` adds 40 cases across both providers. 903 tests pass, 0 failures; konpy 104 files, 0 violations; both contract suites unchanged. Evidence: `evidence-05/`, packet: `review-slice-05.md`, diff: `slice-05.patch`.
- **scope correction:** the files touched were `cli.py`, `views_info.py`, `search_index.py`, `onboard.py`, `README.md`, `CLAUDE.md`, the three version files, and `tests/test_scope.py` — not `tests/test_search_index.py` or `tests/test_output_contracts.py`, which needed no change. `tests/test_scope.py::test_cmds_grep_honors_the_window` did change: it pinned exit 1 for an empty `--since` window *with* `--grep`, which only differed from the 2 you get without `--grep` because the filter bypassed selector resolution. Both are now 2.
- **clauses left open, unweakened:** complete call text by default and `--events-json` (`CMD-cmds-typer`), `-F`/`--fixed` for literal matching (`PAR-cmds-typer-grep_`), and the `--json` duplicate-record clause, which is SXR-CLI-06's.

## SXR-CLI-06 — grep/cmds: valid JSON in every mode, one record per physical line

- **class:** defect
- **rows:** EXTRA-006, EXTRA-007, PAR-grep-typer-json_out, PAR-grep-typer-count, PAR-grep-typer-ids_only, PAR-grep-typer-context, PAR-grep-typer-sort, PAR-cmds-typer-json_out, PAR-cmds-typer-limit
- **before:** `views_grep._emit` tests `ids_only` before `json_out`, so `grep -l --json` prints bare ids that are not JSON; raw grep JSON prints one record per matching event, so a physical line with two matching blocks is emitted twice; `-c` silently overrides `-l`, `-C` and the budget; `--sort` is accepted and ignored outside `-c`; `views_info.cmds_view` can repeat a physical record in JSON.
- **after:** every JSON mode emits valid JSON (`-l --json` → one object per session with id, provider and file); raw JSON emits each physical record once, deduplicated before `-n` applies; conflicting modes (`-c` with `-l`, `-c` with `-C`) exit 2 with a targeted message; `--sort` is rejected outside `-c` and declares its choices; `-C` requires N ≥ 0.
- **files:** `src/sxr/views_grep.py`, `src/sxr/grep_options.py`, `src/sxr/search_index.py`, `src/sxr/views_info.py`, `src/sxr/output.py`; `tests/test_output_contracts.py`, `tests/test_search_index.py`
- **deps:** none
- **accept:** every line of `grep -l --json` parses as JSON; a session whose single line holds two matching blocks emits one raw record; `grep -c -l x` and `grep x --sort started` (no `-c`) exit 2; `cmds --json -n 2` prints two distinct physical records; `-c` totals unchanged.
- **review:** dedup reuses `output.record_events`/`RowBudget` rather than new machinery.
- **delivered:** `_emit` decides `json_out` before `ids_only`, so every JSON mode emits JSON; `-l --json` prints one `grep_session` object per matching session with the full id, provider and source `path`, under the key `list --json` already uses. Raw grep and `cmds` JSON pass their events through `output.record_events`, so one physical line is one record and `-n` counts records: `cmds --json` on a line with two tool calls went from three lines to two, and `cmds --json -n 2` from the same record twice to two distinct ones. `GrepOpts.check()` refuses `-c` with `-l`/`--ids`, `-c` with `-C`, `--sort` without `-c`, and negative `-C`, each naming both flags; `--budget` under `-c` prints one stderr line saying what it caps. `--sort`'s default became `None` so an explicit value is distinguishable, with `GrepOpts.order` spelling the default. `--ids` joins `-l`/`--files-with-matches`. `views_grep.py` would have passed 300 lines, so the `-c` table and the shared diagnostics moved to `grep_counts.py` and `METACHARS`/`SORTS`/the validation to `grep_options.py`; no suppression was added. `tests/test_grep_modes.py` adds 45 cases across both providers. 996 tests pass, 0 failures; konpy 111 files, 0 violations; both contract suites unchanged at 66/1 and 5/0. Evidence: `evidence-slice-06/`, packet: `review-slice-06.md`, diff: `slice-06.patch`.
- **clauses left open, unweakened:** `--events-json` for normalized events with paired outcomes and coordinates (`EXTRA-006`, `PAR-cmds-typer-json_out`) — a new surface, not a defect fix, and D-09 says a projection needs its own flag and documented schema; merging overlapping `-C` windows (`PAR-grep-typer-context`); the shared `--json` flag help still reads "Raw JSONL records, never truncated", which is inaccurate for `-c`, `-l`, `list`, `stats` and `tools` alike and cannot be corrected for `grep` alone without changing every command's help; the shown/total/omitted notice for `-n`-bounded JSON streams, which is `SXR-CLI-20`'s and depends on this slice; and `--sort started` ordering by UTC instant rather than timestamp string, which is `SXR-CLI-08`'s.

## SXR-CLI-07 — grep: result cap separated from character caps  *(DELIVERED 2026-09-13, awaiting review)*

- **class:** intentional-behavior-change
- **rows:** CMD-grep-typer, PAR-grep-typer-limit, PAR-grep-typer-budget, PAR-grep-typer-include_all, EXTRA-046, EXTRA-048
- **before:** `-n 0` lifts both the row cap and the character budget while per-match 200-char flattening still applies, so there is no way to get complete match text; `--all` only keeps zero-count rows in `-c`, and prints nothing when every session has zero matches.
- **after:** `-n` caps results only; `--budget` alone stops output by characters; `--all` lifts row, budget and per-match caps together; new `--full` prints complete matched text under the current row cap; new `--include-zero` keeps zero-count rows in `-c`, including an all-zero table.
- **files:** `src/sxr/views_grep.py`, `src/sxr/flags.py`, `src/sxr/grep_options.py`; `tests/test_search_index.py`, `tests/test_output_contracts.py`
- **deps:** SXR-CLI-06, SXR-CLI-21
- **accept:** `-n 0` keeps the default budget and says so on stderr; `--all` prints every match in full; `--full -n 5` prints five complete matches; `-c --include-zero` on an all-zero scope prints the table and exits 1; count totals identical with and without display caps.
- **review:** migration note for the changed `-n 0` and `--all` meanings in help, README and primer; full-view budget bypass (SXR-AUD-008) still holds.
- **rows verified against source and run before editing.** Every `before` cell was true, which is worth saying after two slices where one was not. Measured in `evidence-slice-07/before/`: `--budget 400 -n 0` printed all 16 rows where `--budget 400` printed 1, so `-n 0` really did discard an explicit budget; `-n 0` alone still trimmed every row and produced zero complete texts; `--all` on a normal scan was byte-identical to no flag at all; `--all -c` on an all-zero scope printed nothing and exited 1; `--full` and `--include-zero` exited 2 as unknown options.
- **one clause `tasks.md` had dropped, recovered from the rows.** `PAR-grep-typer-budget`'s `after` asks for "a documented search-output budget **with omission metadata**" and its `acceptance` for "omitted results ... visible in text **and structured metadata**". The `after` cell above kept only the character-stopping half. The gap was real: `grep -n 2 --json` printed 2 of 14 records with nothing on stdout and nothing on stderr to say 12 were missing, while the same cap in text mode printed a footer. Closed by sending the footer to stderr under `--json`, which is the same `stderr=json_out` shape `errors` already uses -- D-09 keeps stdout to records, so "structured metadata" on stdout was not available, and an unreported omission was the worse of the two.
- **delivered:** three caps, three flags, each independent. `-n` caps results; `--budget` stops output by characters and is no longer discarded by `-n 0`; `--line-limit` flattens each row. `--full` lifts both character caps and leaves `-n` in charge, as `show --full` does under SXR-AUD-008. `--all` lifts all three, which makes it exactly `--full -n 0` -- asserted byte-for-byte on both providers rather than described, so the two spellings cannot drift. `--include-zero` takes over the zero-count-row job and makes an all-zero table printable while the scope still exits 1. `-c --full` and a bare `--include-zero` are refused with a reason, the way `-c --sort` and `-c -C` already are.
- **`--all` agrees with `prompts`, deliberately.** D-01 settled that `prompts --all` means completeness and overrides an explicit `-n`/`--budget`, with selection-widening moved to `--include-context`. `grep --all` now means completeness and overrides an explicit `-n`/`--budget`, with selection-widening moved to `--include-zero`. Same meaning, same precedence, same shape of sibling flag; two tests name D-01 so the parallel is checkable rather than a claim.
- **`--full` against `--all`, resolved rather than left ambiguous.** They do overlap, and the overlap is the point: `--all` is defined *as* `--full -n 0` instead of as a fourth independent switch. `--full` exists because "every match, whole" and "these five matches, whole" are both real questions and `-n` is the only difference between them. `rows_uncapped` and `complete_text` are the two properties the view actually reads, so neither flag can grow a private meaning.
- **migration, stated in three places and measured in a fourth.** `sxr grep --help` and the `--help` epilog carry the caps; `README.md` gains a four-column table and a two-item migration list; the `-c` footer now advertises `--include-zero` rather than the flag that no longer does that job, which is what a script author sees first. 28 captures from slices 5, 6, 8 and 21 changed, and all 28 are one of those three sentences -- no data row moved.
- **`PRIMER_BODY` is unchanged, and that is a judgment worth reviewing.** Checked line by line: the installed primer never mentioned `grep --all`, `grep -n 0` or zero-count rows, and its one relevant sentence ("`--around`, `--range`, `--type` or `--full` prints whole text") becomes more true now that `--full` exists on `grep` too. Nothing in it is false. Adding to it would either need a version bump nobody approved or leave a v0.14.0-stamped block whose content differs from this tree's v0.14.0 primer -- the drift `write_hazard` exists to catch. Left for the reviewer as **open decision 10**.
- **left open:** `CMD-grep-typer`'s `problem` cell also says "-C limits blocks rather than physical lines", which is a `-C` unit question this slice did not touch and no acceptance clause here covers. `PAR-grep-typer-limit` asks to "define the unit for each mode": done for match rows, `-l` sessions and `-c` table rows, not for `-C` windows.

## SXR-CLI-08 — one timestamp parser for every sort, filter and format

- **class:** defect
- **rows:** CMD-list-typer, EXTRA-012
- **before:** `util.day()` returns `ts[:19] + "Z"`, so `2026-09-10T09:00:00+02:00` displays as `2026-09-10T09:00:00Z`; list ordering and `grep -c --sort started` compare timestamp strings, so offset-bearing transcripts sort and display wrong (window filtering already uses instants).
- **after:** one parser converts recorded timestamps to UTC instants for sorting, filtering and display; raw `--json` keeps the source timestamp string while derived metadata carries the real UTC instant.
- **files:** `src/sxr/util.py`, `src/sxr/views_info.py`, `src/sxr/views_grep.py`, `src/sxr/discovery_scope.py`, `src/sxr/find_service.py`; `tests/test_lazy_discovery.py`, `tests/test_output_contracts.py`
- **deps:** none
- **accept:** two sessions recording the same instant in different offsets sort adjacently and display the same `started`; `--since`/`--before` results unchanged (SXR-AUD-002); `grep -c --sort started` orders by instant.
- **review:** no timestamp string slicing or string comparison left; the note that corrected chronology can renumber `@N` for offset-bearing corpora is in the release notes.
- **delivered 2026-09-12.** `util.instant()` is now the only caller of `fromisoformat` in `src/sxr` (one grep proves it), and `day`, `clock`, the new `date_of`, `order_key`, `is_live` and `handles._instant` all route through it. The three newest-first discovery sorts (`claude_discovery`, `providers/codex`, `find_service`), `grep -c --sort started` and both `[:10]` date columns now compare and print instants. All three accept clauses hold, measured in `evidence-slice-08/`: S1 and S2 sort adjacently and both show `2026-09-10T07:00:00Z`; every literal `--since`/`--before` bound keeps exactly the sessions it kept before, on both providers, checked mechanically by `check_scope_08.py` with failures 0; `--sort started` orders by instant. `README.md` carries the renumbering note.
- **corrections to this row, both verified against source.** Two of the cited files needed no change and one uncited file did. `discovery_scope.py` does no timestamp work at all, and `views_grep.py`'s timestamp handling moved to `grep_counts.py` in slice 6. The ordering sorts that actually decide `@N` are in `claude_discovery.py:82` and `providers/codex.py:153`, which neither row named; both rows instead cite `discovery.py:deduplicate`, which has never sorted, at the audited base `48b11c6c` either. That citation was wrong when written, not stale. The two named test modules needed no change; the coverage is in a new `tests/test_timestamps.py` (53 cases, both providers).
- **left open, unweakened.** `CMD-list-typer` also asks for a handle, the scope and an exact `--file` follow-up in `list --json`; that is additive metadata unrelated to timestamps and is untouched here. `find --json`'s `started` stays the verbatim source string rather than becoming the instant: unlike `list --json`, it never appended `Z` and so never made a false UTC claim, and changing it is a schema change to a command whose own rows are not in this slice. `stats` reports the first and last *records'* instants rather than the minimum and maximum, which is what it always did, now displayed correctly.

## SXR-CLI-09 — stats: numeric JSON fields and a whole-session limit unit

- **class:** intentional-behavior-change
- **rows:** CMD-stats-typer, PAR-stats-typer-arg, PAR-stats-typer-json_out, PAR-stats-typer-limit
- **before:** `-n 1` prints one field/value row in text but one whole session object in JSON (`views_info._print_stats`); JSON `tokens` and `size` are human strings (`"45k"`, `"210k"`) from `human_num`/`human_size`.
- **after:** `-n` counts complete session summaries in both formats; JSON emits integer `tokens` and `size_bytes` and UTC `started`/`ended`; text groups each session's fields under an explicit session identity header.
- **files:** `src/sxr/views_info.py`, `src/sxr/output.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-08
- **accept:** `stats @1:@2 -n 1` prints exactly one session in text and in JSON; `jq '.tokens|type'` returns `number`; a shown session keeps every field.
- **review:** the JSON schema change is documented as a versioned migration in README and help before merge.

## SXR-CLI-10 — tools: bounded Skill detail and identified aggregates

- **class:** defect
- **rows:** CMD-tools-typer, PAR-tools-typer-json_out
- **before:** the `# Skill inputs:` footer in `views_info.tools_view` prints every distinct skill regardless of `-n`, so detail grows outside the requested cap; the JSON aggregate carries no source session identity.
- **after:** the Skill-input footer obeys the same row allowance and reports omissions; the JSON aggregate gains `session`, `provider` and `file` while keeping every existing key (SXR-AUD-007).
- **files:** `src/sxr/views_info.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-02
- **accept:** `-n 1` with five distinct skill inputs prints one skill plus an omission notice; JSON emits one identified aggregate per selected session; `-n 0` output unchanged.
- **review:** no key dropped from the JSON aggregate — capping keys inside it stays blocked on the `PAR-tools-typer-limit` decision.

## SXR-CLI-11 — one physical-file scope for secrets audit, clean and path

- **class:** intentional-behavior-change
- **rows:** CMD-secrets-typer, CMD-secrets-clean-typer, PAR-secrets-clean-typer-arg, CMD-path-typer, EXTRA-014
- **before:** `views_secrets.secrets_view` opens `ref.path` only; `secrets/clean.py` expands through `secrets/files.physical_paths` (duplicate copies plus recursive Claude children); `cli.py:193` (`path`) uses `provider.session_paths` — three different file sets for one selection.
- **after:** all three derive their worklist from one selection function; `--include-agents` controls child inclusion consistently; `--file` stays exact; `path --json` gains owning session and provider fields; `--apply` never widens beyond the previewed set.
- **files:** `src/sxr/secrets/files.py`, `src/sxr/views_secrets.py`, `src/sxr/secrets/clean.py`, `src/sxr/cli.py`; `tests/test_secrets.py`, `tests/test_clean_files.py`, `tests/test_file_selection.py`
- **deps:** none
- **accept:** for a session with a duplicate copy and a child transcript, `secrets`, `secrets clean` (dry run) and `path` report the same file list; `--file X` yields exactly X in all three; `--apply` rewrites only previewed files; duplicate paths counted once.
- **review:** before/after file-set diff on a synthetic corpus; record-level auditing (SXR-AUD-001) intact; no write scope broadened as a side effect of the UX change.

## SXR-CLI-12 — secrets follow-ups preserve scope and stay masked

- **class:** defect
- **rows:** PAR-secrets-clean-typer-apply, PAR-secrets-typer-candidates, EXTRA-015, EXTRA-016
- **before:** `clean.py:209` prints `sxr secrets clean --apply` regardless of provider, session, `--file`, `--path` or date flags; `views_secrets.py:88` suggests `sxr show <id> --around <seq>`, which can print the credential the audit just masked; `--candidates` before `clean` is accepted and ignored.
- **after:** the dry-run footer prints a shell-quoted command reproducing the resolved selection (preferring exact `--file` for a single source, an explicit file list otherwise); the audit footer offers only masked follow-ups and no raw `show` hint; `sxr secrets --candidates clean` exits 2 stating that clean never rewrites entropy candidates.
- **files:** `src/sxr/secrets/clean.py`, `src/sxr/views_secrets.py`, `src/sxr/secrets_commands.py`, `src/sxr/secrets_group.py`, `src/sxr/navigation.py`; `tests/test_secrets_cli.py`, `tests/test_secret_audit_records.py`
- **deps:** SXR-CLI-11
- **accept:** a preview run with `--codex --path DIR @2` prints a follow-up that, run verbatim, touches exactly the previewed files, including paths containing spaces; audit output contains no `sxr show` suggestion; `secrets --candidates clean` exits 2; no secret value in any stream.
- **review:** quoting of the generated command; masked-output guarantee unchanged in text and JSON.

## SXR-CLI-13 — document `secrets audit` in help

- **class:** mechanical
- **rows:** CMD-secrets-audit-typer, PAR-secrets-audit-typer-arg
- **before:** `secrets audit` exists but is hidden, so `sxr secrets --help` lists only `clean` and the reserved action names that a session name can collide with are invisible.
- **after:** `audit` is listed with its own flags shown on its surface; bare `secrets` and `secrets SESSION` shorthands behave exactly as today.
- **files:** `src/sxr/secrets_group.py`; `tests/test_secrets_cli.py`
- **deps:** none
- **accept:** `sxr secrets --help` lists `audit` and `clean`; `sxr secrets audit --help` shows `--candidates`; `sxr secrets <name>` still audits that session.
- **review:** help capture diff only; no selection or output change.

## SXR-CLI-14 — accept `--since`/`--before` after every session command

- **class:** optional-addition
- **rows:** PAR-root-typer-since, PAR-root-typer-before, EXTRA-071, EXTRA-072, EXTRA-073, EXTRA-074, EXTRA-075, EXTRA-076, EXTRA-077, EXTRA-078, EXTRA-079, EXTRA-080, EXTRA-081, EXTRA-082
- **before:** the window flags are declared on root, list, grep, cmds, index, find and the secrets group only. Root values do reach every command (`flags.sessions` reads `ctx.obj`), but `sxr show --since today` exits 2 because `show`, `prompts`, `errors`, `tools`, `stats` and `path` declare no such option.
- **after:** those six commands accept `--since`/`--before` after the command with identical inclusive UTC semantics and identical handle resolution; both placements produce the same scope.
- **files:** `src/sxr/cli.py`, `src/sxr/show_command.py`, `src/sxr/flags.py`; `tests/test_lazy_discovery.py`, `tests/test_file_selection.py`
- **deps:** SXR-CLI-08, SXR-CLI-02
- **accept:** `sxr show --since today` and `sxr --since today show` select the same session; `prompts --before <date>` renumbers handles the same way as the root form; an invalid date exits 2 in both positions; which records are selected inside a session is unchanged.
- **review:** matrix of six commands × two placements; no new filtering of events, only of sessions.

## SXR-CLI-15 — skills honors inherited flags and projects paths consistently

- **class:** defect *(covers both dispatch paths)*
- **rows:** CMD-skills-argparse, PAR-skills-argparse-json, PAR-skills-argparse-limit, PAR-skills-argparse-paths, PAR-skills-argparse-aliases, PAR-skills-argparse-index, PAR-skills-argparse-root, PAR-skills-argparse-clear, EXTRA-027
- **before:** `skills_command.lookup` forwards `ctx.args` to `skills_cli.main`, so `sxr --json -n 5 skills x` loses both flags; `--paths --json` prints the full envelope instead of the path list; `-n` caps groups before alias expansion, so `--paths --aliases -n 2` can print more than two paths; `--clear` accepts output/filter flags it ignores.
- **after:** applicable root flags are forwarded to the argparse parser and honored; `--paths --json` emits the same path list as text; in path mode the limit counts distinct emitted paths after copy/alias expansion; `--index`, `--clear` and `--defaults` reject flags they cannot use and print the resolved or cleared roots.
- **files:** `src/sxr/skills_command.py`, `src/sxr/skills_cli.py`, `src/sxr/skills_catalog.py`, `src/sxr/skills_content.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-18
- **accept:** `sxr --json skills foo` and `sxr skills foo --json` produce identical output; `skills --paths --aliases -n 2 --json` yields exactly two paths equal to text mode; `skills --clear --json` either honors or rejects the flag, never ignores it.
- **review:** both entry paths exercised; a scoped `--root` lookup never rewrites remembered roots.

## SXR-CLI-16 — serve: one parser contract, validated launcher flags

- **class:** defect *(covers both dispatch paths)*
- **rows:** CMD-serve-typer, CMD-serve-argparse, PAR-serve-typer-action, PAR-serve-argparse-action, PAR-serve-argparse-foreground, PAR-serve-argparse-idle, EXTRA-022, EXTRA-023
- **before:** `sxr serve status` reaches argparse (hidden `--foreground PATH`, `--idle SECONDS`), while `sxr --json serve status` reaches the Typer wrapper, which declares an unconstrained action string and no launcher flags; `--idle nan`/`inf` pass the `<= 0` check; `--foreground` overrides the action silently.
- **after:** one shared action choice (`status`|`stop`) validated identically on both paths; `--idle` must be finite and positive and is rejected outside foreground mode; `--foreground` is an internal launch mode that rejects a positional action; status stays read-only and an unavailable worker still exits 1.
- **files:** `src/sxr/find_worker.py`, `src/sxr/cli.py`, `src/sxr/__init__.py`; worker/serve contract tests
- **deps:** SXR-CLI-18
- **accept:** `serve bogus` exits 2 with the same message on both paths; `serve --idle nan --foreground P` and `serve status --idle 5` exit 2; `serve status` starts no worker; the bundled launcher still starts a foreground worker.
- **review:** bundle relocation and entry-point verification rerun; no real worker started by tests.

## SXR-CLI-17 — find: one command contract across both parsers

- **class:** defect *(covers both dispatch paths)*
- **rows:** CMD-find-typer, CMD-find-argparse, PAR-find-typer-index, PAR-find-argparse-index, PAR-find-typer-exclude_sessions, PAR-find-argparse-exclude_sessions, EXTRA-010, EXTRA-025
- **before:** `sxr find x` uses argparse and accepts unique long-option prefixes (`--include-c`), while `sxr --json find x` uses Typer and rejects them; `find --index <query>` turns a no-hit search into exit 0; an `--exclude-session` value that matches nothing is silent.
- **after:** both entry paths derive from one option declaration with the same help, validation and exit codes; `--index` without a query is preparation-only (exit 0), and with a query keeps ordinary search exits (1 on no hit, 2 on incomplete search); unmatched explicit exclusions are reported on stderr without widening the search.
- **files:** `src/sxr/find_cli.py`, `src/sxr/find_command.py`, `src/sxr/find_service.py`, `src/sxr/__init__.py`; `tests/test_lazy_discovery.py`, `tests/test_audit_retrieval.py`
- **deps:** SXR-CLI-18
- **accept:** help for both paths matches except the program name; `find --index "nomatch"` exits 1; `find --index` alone exits 0; `find --include-c x` exits 2 on both paths; ranking, evidence and the five-result default unchanged.
- **review:** side-by-side help captures plus an exit-code matrix; retrieval quality unchanged on the existing audit retrieval corpus.

## SXR-CLI-18 — reject options a command cannot use, in every parser

- **class:** intentional-behavior-change *(covers both dispatch paths)*
- **rows:** CMD-root-typer, EXTRA-001, EXTRA-018, PAR-root-typer-use_codex, PAR-root-typer-path, PAR-root-typer-json_out, PAR-root-typer-limit, PAR-root-typer-recursive, PAR-root-typer-worktrees, PAR-find-typer-all_projects, PAR-find-argparse-all_projects
- **before:** root flags land in `ctx.obj` and are read only by commands that care, so `sxr --json init`, `sxr -n 5 index`, `sxr --json skills x` and `sxr --recursive --all-projects find x` run with the option silently ignored; argparse paths additionally accept abbreviated long options.
- **after:** each command declares which shared options it honors; a root or command option the selected command cannot honor exits 2 naming both the option and the command; abbreviated long options are rejected in every parser with a close-match suggestion and no guessed execution; supported combinations behave exactly as today.
- **files:** `src/sxr/scope_options.py`, `src/sxr/flags.py`, `src/sxr/cli.py`, `src/sxr/find_cli.py`, `src/sxr/skills_cli.py`, `src/sxr/find_worker.py`; `tests/test_file_selection.py`, `tests/test_output_contracts.py`
- **deps:** none — 15, 16, 17, 20 depend on it
- **accept:** `sxr --json init` exits 2; `sxr -n 5 index` is honored or exits 2 per the declared list, never ignored; `find --include-c x` exits 2; every currently valid invocation in the test suite keeps its exit code; an empty listing still exits 0.
- **review:** the applicability table itself, plus a full-suite run to surface scripts that depended on a previously ignored flag.

## SXR-CLI-19 — init --check compares the installed block content

- **class:** intentional-behavior-change
- **rows:** CMD-init-typer, PAR-init-typer-check, PAR-init-typer-write, PAR-init-typer-use_global
- **before:** `onboard.check_primer` compares only the stamped version (`onboard.py:187`), so an edited current-version block exits 0; the resolved target file is not reported.
- **after:** `--check` compares the installed block body against the generated primer and exits 1 on any difference, naming the resolved target; `--write` stays idempotent and byte-preserving outside the markers and reports its destination; `--global`'s fallback chain is documented in help.
- **files:** `src/sxr/onboard.py`; `tests/test_primer_errors.py`
- **deps:** none
- **accept:** one edited character inside a current-version block makes `--check` exit 1; an untouched block exits 0; `--write` twice is byte-identical; text outside the markers unchanged; an invalid destination still exits 2.
- **review:** byte-level diff of a file with surrounding prose; the 0/1/2 exit table in help.

## SXR-CLI-20 — index --clear reports its exact extent

- **class:** defect
- **rows:** CMD-index-typer, PAR-index-typer-clear_, EXTRA-026
- **before:** `search_index.index_cmd` handles `--clear` before any scope validation, so `sxr index --clear --codex --path X` silently ignores every scope flag and prints only the cache path.
- **after:** `--clear` rejects provider, scope and limit flags and reports what was removed (the shared search database plus journal/WAL) and what was kept (skill maps, fingerprint salt, transcripts).
- **files:** `src/sxr/search_index.py`, `src/sxr/index_store.py`; `tests/test_search_index.py`
- **deps:** SXR-CLI-18
- **accept:** `index --clear --codex` exits 2; `index --clear` names removed and retained artifacts; a cleared cache rebuilds on the next `index`; the skill map survives a session-cache clear.
- **review:** the printed extent matches what `index_store.clear()` actually deletes.

## SXR-CLI-21 — validate and document the compact-display flags  *(DELIVERED 2026-09-13, awaiting review)*
- **delivered:** `util._env_int` reports an unusable `SXR_BUDGET`/`SXR_LINE_LIMIT` once per variable per process on stderr and falls back to the default; `util.middle_trim` derives its head and tail from the one per-line cap instead of fixed widths, which at the 200 default is byte-identical to its old 200-and-120 split; `views_grep._emit` resolves the cap once and passes it to match rows as well as `-C` windows; `views_read.errors` resolves it once for `--compact`; `GrepBudgetF` gains `min=0`. `tests/test_compact_caps.py` adds 30 cases across both providers, `tests/conftest.py` clears the per-process notice per test. 1079 pass (1049 + 30 new); ruff clean, format 211; konpy 113 files, 0 violations; both contract suites unchanged (66 with `PROMPTS-filter` the only failure, 5/5). Evidence: `evidence-slice-21/`, baseline: `baseline-21/`, diff: `slice-21.patch`, packet: `review-slice-21.md`.
- **closes for slices 3 and 4:** both deferred "the same explicit cap policy for all event kinds" to this task and neither defined one — SXR-CLI-03 left tool-result bodies on `middle_trim`'s fixed widths, SXR-CLI-04 said its `--compact` branch still used them. One derived cap now covers both, so their clauses close here rather than being replaced by a third policy.
- **left open:** EXTRA-009's `find_worker` idle check and `skills_cli`'s numeric arguments. Both are separate commands with their own dispatch and neither appears in this task's `files` list; folding them in would have widened a shared-plumbing slice into two more entry points. `PAR-show-typer-tail`'s JSON record-counting clause stays where SXR-CLI-03 left it, needing its own decision.

## SXR-CLI-21 — validate and document the compact-display flags

- **class:** defect *(shared flags: both dispatch paths)*
- **rows:** PAR-show-typer-budget, PAR-show-typer-line_cap, EXTRA-009, EXTRA-028, EXTRA-029
- **before:** `util.scan_budget`/`line_limit` accept any integer and fall back silently on garbage env values; negative `--budget`/`--line-limit` behave as "unlimited"; grep match rows hardcode `one_line`'s 200 default while `-C` windows read `SXR_LINE_LIMIT`.
- **after (corrected 2026-09-13; the original wording is below and conflicted with D-05):** an invalid `SXR_BUDGET`/`SXR_LINE_LIMIT` prints one stderr notice instead of being silently ignored, and falls back to the default; one compact-view cap applies to every trimmed row of a view, including tool-result bodies, which stop using `middle_trim`'s fixed widths; `grep --budget` rejects negatives like `show --budget` already does. `show` keeps rejecting negative `--budget`/`--line-limit` (**D-05**, already delivered by SXR-CLI-03, verified not re-done) and `prompts` keeps negative meaning "never truncate" (**D-02**). The asymmetry survives.
- **the original wording, and why it was wrong:** *"`--budget` and `--line-limit` reject negatives (exit 2), 0 means no trimming, …"* — read across every command that has those flag names, which is the harmonization D-05 refused. **The CSV rows do not propose that.** `PAR-show-typer-budget` and `PAR-show-typer-line_cap` are both scoped `command: sxr show`, and the two env rows ask only to "validate numeric values" and, for `prompts`, to "remove implicit trimming from plain prompts" — which SXR-CLI-01 did. So this is a third kind of row defect beyond stale and wrong-when-written: a **task-spec paraphrase that dropped a row's command scope** and thereby manufactured a conflict the source rows never had. No reviewer decision is needed; there is nothing to weigh against D-05.
- **files:** `src/sxr/util.py`, `src/sxr/flags.py`, `src/sxr/views_read.py`, `src/sxr/views_grep.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-01 (prompts must already be budget-free)
- **accept:** `show --budget -1` and `show --line-limit -1` exit 2 (already true; re-measured, not re-implemented); `--budget 0` prints whole text; `SXR_BUDGET=abc` prints one notice and uses the default; grep match rows and `-C` windows use the same cap; a trimmed tool-result body follows the selected cap; `prompts --budget -1` still never truncates.
- **review:** the flag/env/default precedence table; complete views (`--full`, zooms, `--json`) still bypass the budget; the notice reaches stderr only, fires at most once per variable per process, and does not fire for a valid value.

## SXR-CLI-22 — help states units, defaults and schemas; `-h` everywhere

- **class:** mechanical *(covers both dispatch paths)*
- **rows:** PAR-root-typer-help, PAR-root-typer-use_claude, PAR-root-typer-include_agents, PAR-root-typer-archives, PAR-list-typer-json_out, PAR-show-typer-limit
- **before:** Typer surfaces accept `--help` only while argparse paths also take `-h`; the shared `--claude` help says "(default)" even for `find`, which defaults to both providers; the shared `--json` help says "Raw JSONL records, never truncated" for commands that emit derived objects; `-n` help gives no per-format unit; child/archive defaults differ per command but read identically.
- **after:** `-h` and `--help` work on every surface; each command's help states its provider default, its `--json` record shape, its `-n` unit per format, and its child/archive defaults; root help stays short with the long guide in the epilog.
- **files:** `src/sxr/flags.py`, `src/sxr/cli.py`, `src/sxr/onboard.py`, `src/sxr/find_cli.py`, `src/sxr/skills_cli.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-03, 04, 06, 07, 09 (help must describe final behavior)
- **accept:** `sxr <cmd> -h` exits 0 for every command; `find --help` does not call Claude the default; every JSON-capable command's help names its record type and limit unit.
- **review:** the 21 captured help texts in `audit/2026-09-10/command-review/help/` regenerated and diffed.

## SXR-CLI-23 — handles and generated follow-ups keep the exact source

- **class:** optional-addition
- **rows:** PAR-root-typer-file, EXTRA-005
- **before:** `list --json` carries no `@N` handle and no follow-up command; find result ranks look like handles; generated follow-ups use ids that renumber when the scope changes.
- **after:** `list --json` carries `handle` plus an exact `--file` follow-up command; find output labels ranks as ranks; every generated follow-up (`show --around`, zoom hints, clean apply) names the exact source file.
- **files:** `src/sxr/views_info.py`, `src/sxr/navigation.py`, `src/sxr/find_service.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-08, SXR-CLI-12
- **accept:** a follow-up copied from `list --json` reads the same file after new sessions appear; find never presents a rank as `@N`; existing `@N` semantics unchanged.
- **review:** JSON additions are additive only; no change to handle numbering rules.

## SXR-CLI-24 — results on stdout, omissions and notices on stderr  *(DELIVERED 2026-09-14, awaiting review)*

- **rows verified against source before editing, and run:** `PAR-list-typer-limit`,
  `PAR-root-typer-coverage`, `EXTRA-011`. Read from the CSV, not from the paraphrase
  below; the paraphrase was checked against all three and carries their qualifiers.
- **what the rows asked for that was already true:** `--json` stdout is already pure in
  all 18 machine-readable cases measured, so `EXTRA-011`'s "no text notice breaks JSON
  stdout" needed nothing. `_coverage` already labels provider roots `searched` or
  `unavailable`, and already separates discovery counts from searched source counts,
  which is most of `PAR-root-typer-coverage`. `show`, `stats`, `path`, `errors` and
  (since SXR-CLI-07) `grep` already report omissions on stderr under `--json`.
- **the three defects that were left, each measured before being fixed:**
  1. `list -n 1 --json` returned 1 of 4 sessions and said nothing on either stream.
  2. `cmds -n 1 --json` returned 1 of 3 records and said nothing on either stream.
     `print_records` defers its notice when handed a scope-wide budget, so that one
     omission is reported for the whole scope rather than once per session, and
     `cmds_view` never made that deferred call.
  3. A `--path` that does not exist reported "0 sessions" in the same words as a real
     directory with no sessions, so a typo was indistinguishable from an empty scope.
  Plus one found while fixing 2: the `# N of M sessions searched; all of them:
  --all-sessions` disclosure was printed in text mode only, so a `--json` caller was
  not told its scope had been narrowed.
- **what this slice deliberately did not do:** move text-mode headers and footers off
  stdout. `EXTRA-011`'s before-cell names them, but its compatibility cell says "Review
  before implementing", and every script that reads `# +N more` or the `# read:` line
  from `sxr list` would break at once. Left as an open decision with the evidence.
- **also not done:** `total/shown/omitted` *fields* inside structured envelopes, which
  `EXTRA-011`'s after-cell permits ("where structured envelopes exist"). Schema growth
  is exactly what the three `decision-needed` rows hold, so this slice reports on
  stderr and adds no field to any object.
- **delivered:** stdout byte-identical in all 116 captures on both providers, exit codes
  identical in all 116, and 16 changed captures all of which add a stderr line.

## SXR-CLI-24 — results on stdout, omissions and notices on stderr

- **class:** defect
- **rows:** PAR-list-typer-limit, PAR-root-typer-coverage, EXTRA-011
- **before:** text headers, footers and trim notices print on stdout while root help claims notices go to stderr; `list --json`, `grep --json` and `cmds --json` bounded by `-n` print no omission notice at all; `--coverage` does not distinguish discovered roots from searched sources.
- **after:** result data on stdout and all progress/recovery/omission notices on stderr (headers documented as data); every `-n`-bounded JSON stream reports shown/total/omitted on stderr; `--coverage` labels unavailable roots and separates discovered from searched counts.
- **files:** `src/sxr/output.py`, `src/sxr/views_info.py`, `src/sxr/views_grep.py`, `src/sxr/discovery_scope.py`; `tests/test_output_contracts.py`
- **deps:** SXR-CLI-06
- **accept:** `list --json -n 1` with three sessions prints one object on stdout and a notice on stderr; `2>/dev/null` leaves valid JSON only; the stderr claim in help matches observed streams.
- **review:** stdout/stderr split per command; existing SXR-AUD-005/006/007 notices preserved.

---

## SXR-DOCS-02 — one primer refresh for every flag-changing slice

- **class:** record keeping, no behavior change
- **rows:** none; queued by D-14 rather than derived from the CSV
- **why it exists:** SXR-CLI-06, 07 and 21 each changed a documented flag meaning, and
  more of the queue will. `PRIMER_BODY` is version-stamped, and `write_hazard` compares
  installed content independently of that stamp, so editing the primer once per slice
  would either move the version once per slice or leave stamped blocks in other
  repositories whose content differs from what that version generates.
- **after:** one refresh of `PRIMER_BODY` covering every flag-changing slice delivered by
  then, with a single version bump, once those slices are done. D-14 defers the content,
  it does not cancel it.
- **deps:** every flag-changing slice that should be covered. Today that is SXR-CLI-06,
  SXR-CLI-07 and SXR-CLI-21; check the ledger for later ones before running it.
- **accept:** `init --check` reports the installed block as outdated for the old version
  and current after the refresh; the primer's token budget is respected; nothing in the
  refreshed text contradicts `README.md` or the `--help` epilog.
- **carried forward, per slice, so the refresh has a source rather than a memory:**
  SXR-CLI-07's ready wording for the grep bullet is *"--full/--all print matches whole;
  -c --include-zero keeps zero-count rows."* SXR-CLI-06 and SXR-CLI-21 wrote no primer
  text, and neither made a primer statement false; verify that again at refresh time.

---

## Proposed sequence

01 → 02 → 03 → 04 → 21 → 06 → 07 → 05 → 08 → 09 → 10 → 11 → 12 → 13 → 18 → 15 → 16 → 17 → 19 → 20 → 14 → 24 → 23 → 22.

**Resequenced 2026-09-12, reviewer-approved: 08 comes before 07.** As actually
run the order has been 01 → 02 → 03 → 04 → 05 → 06 → **08** → 07 → …, with 21
still ahead of 07. Two reasons. SXR-CLI-06 changed the documented meaning of
`--sort`, `-l --json` and the `--json` record unit, and SXR-CLI-07 changes the
documented meanings of `-n 0` and `--all`; two consecutive slices redefining
documented flags is a review hazard, because a reader cannot tell which
migration note explains a given behavior change. And SXR-CLI-07 keeps
`--sort started`, which SXR-CLI-08 is what makes correct: sorting timestamp
strings is wrong for offset-bearing transcripts whatever the row caps do.

Rationale for the shape: the `views_read` cluster (01–04, 21) lands first because three tasks edit the same renderer; the search cluster (06, 07, 05) next; correctness fixes with no shared blast radius (08–13) after that; parser strictness (18) before everything that depends on it (15, 16, 17, 20); additive surfaces (14, 23) and the documentation sweep (22) last, so help is written once against final behavior.

## Next slice after SXR-CLI-01

**SXR-CLI-02 — honor multi-session ranges in show, prompts, tools.** It depends on SXR-CLI-01: both slices rewrite `views_read.prompts` and its call site in `cli.py`, and 02's per-session identity headers only make sense once 01 has settled what a prompt record is and how completely it prints. Doing 02 first would force the same code to be written twice and would mix "which sessions" with "which records" in one review. It is also the smallest next step that closes a silent data-loss bug (a valid `@A:@B` range currently discards sessions), and it unblocks 03, 10 and 14.
