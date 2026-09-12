# Review packet — SXR-CLI-02, honor multi-session ranges in show, prompts, tools

Delivered 2026-09-11. **Accepted 2026-09-11 by the originating reviewer**, who
independently re-ran the verification below before accepting. Nothing was
committed; the change sits in the working tree alongside the pre-existing
remediation work and slice 1.

**Decision resolved on acceptance — D-04.** The banner question in section 4 was
answered: keep the uniform `# session @N  <short id>  <file>` banner across
`show`, `prompts` and `tools`, including the duplication with `show`'s own
`file:` header line, because consistency across the three commands wins.
SXR-CLI-03 may revisit the duplication only as a consequence of reworking
`show`'s header, and must not diverge the three banner formats to remove it.
No code changed after acceptance. Also recorded in [ledger.md](ledger.md).

## 1. What was asked, and the invocation that proves it

**Task:** SXR-CLI-02, class `defect`.
**CSV rows:** `PAR-show-typer-arg`, `PAR-prompts-typer-arg`, `PAR-tools-typer-arg`,
`EXTRA-004`.

`handles.resolve` has always returned every session an inclusive `@A:@B` range
names, normalizing reversed endpoints. `show`, `prompts` and `tools` then took
`[0]`, so a valid range read one session and said nothing about the rest.

Before, on a synthetic two-session Claude corpus:

```
$ sxr show @1:@2 --path /w
session:  bbbb1111-2222-3333-4444-555566667777
...
#0005  09:10:11  user   text    "bravo second human prompt"
```

Exit 0, and byte-identical to `sxr show @1`. Session `aaaa1111` was discarded
silently. After:

```
$ sxr show @1:@2 --path /w
# session @1  bbbb1111  /…/bbbb1111-2222-3333-4444-555566667777.jsonl
session:  bbbb1111-2222-3333-4444-555566667777
...
#0005  09:10:11  user   text    "bravo second human prompt"

# session @2  aaaa1111  /…/aaaa1111-2222-3333-4444-555566667777.jsonl
session:  aaaa1111-2222-3333-4444-555566667777
...
#0005  16:58:24  user   text    "alpha second human prompt"
```

The same holds for `prompts @1:@2` and `tools @1:@2`, and for Codex. Full
captures: `evidence-02/before/` and `evidence-02/after/`, indexed by
`evidence-02/before-after-index.txt`.

**CSV rows verified against source before implementing.** No row's reading had
changed: every `before` cell still described the code at this slice's baseline,
and the defect was confirmed by capture rather than by reading. `disposition.json`
and `disposition.md` were updated to record *which clause* of each multi-clause
row this slice closes — `PAR-show-typer-arg` also carries filter-precedence and
`--tools` clauses that stay with SXR-CLI-03, and `PAR-tools-typer-arg` also
carries the `--json` `-n` unit (the `PAR-tools-typer-limit` decision) and the
still-uncapped `# Skill inputs` line. `disposition.json` now has a
`verified_against_source` entry for this slice. The CSV itself is untouched: its
sha256 still matches the value recorded in `disposition.json`.

## 2. The bounded diff

`slice-02.patch` — 743 lines, 402 added, 50 removed, 11 files (9 modified, 2 new).

It is a diff of this slice's recorded starting tree against the current tree, so
slice 1 is part of the *starting* state and does not appear. Reproduce it:

```bash
mkdir -p /tmp/sxr-b02 && tar -xzf audit/2026-09-11/cli-refactor/baseline-02/worktree-snapshot.tar.gz -C /tmp/sxr-b02
mkdir -p /tmp/sxr-after02
{ git ls-files src tests docs packaging README.md CLAUDE.md konpy.json pyproject.toml justfile
  git ls-files -o --exclude-standard src tests docs packaging; } | sort -u > /tmp/after-files.txt
rsync -a --files-from=/tmp/after-files.txt ./ /tmp/sxr-after02/
diff -ruN -x .ruff_cache -x __pycache__ /tmp/sxr-b02 /tmp/sxr-after02
```

Exclude `.ruff_cache`: running ruff inside an extracted snapshot creates one
there, because the snapshot contains a `pyproject.toml`.

`slice-02-after-sha256.txt` records a hash per file after this slice.
Slice 1's `baseline/`, `slice-01.patch` and `slice-01-after-sha256.txt` are
unmodified.

## 3. Source identity, changed files, and verification

### Design decision: how a range identifies its sessions

One rule for all three commands: when a selection holds **more than one**
session, each session's output is preceded by

```
# session @N  <short id>  <file path>
```

on stdout for text views, on **stderr** for `--json` views. `--json` stdout is a
raw-JSONL contract (`EXTRA-006`), so identity cannot become a stdout line or a
new record field there without breaking it; stderr is where this CLI already puts
diagnostics (`RowBudget.notice(stderr=json_out)`). A selection of exactly one
session takes the pre-range code path unchanged and prints no banner at all.

Second rule: `-n` is **one row allowance for the whole invocation**, not per
session. That matches what `errors`, `cmds`, `stats` and `path` already do and
what `SXR-AUD-006` established. Selection filters stay per session — `--around`,
`--range`, `--type`, `--tail`, `--errors` describe a transcript, so each session
is filtered on its own; only the output allowance is shared.

A consequence worth seeing before you approve it: when the allowance runs out
mid-range, later sessions still print their banner (and, for `show`/`tools`,
their header) with no rows under it. That is deliberate — you can tell the
session was read and exhausted rather than skipped — and it is how `stats`
already behaves. `evidence-02/after/claude-tools-range-limit.txt` shows it.

### Changed files

| File | Change |
|---|---|
| `src/sxr/session_scope.py` (new, 55 lines) | `banner()` and `render()`: the one place that decides per-session identity and the shared allowance. Its docstring is the contract. |
| `src/sxr/show_command.py` | `resolve(...)[0]` → the full list, rendered through `render_scope`. |
| `src/sxr/cli.py` | `prompts` and `tools` likewise; both now call a `*_scope` entry point, so the command bodies got shorter, not longer. |
| `src/sxr/views_read.py` | `show()` accepts a shared `RowBudget`; `print_events` gained an inherited-budget path and its row body moved into `_print_event` (no output change on the owned path). |
| `src/sxr/views_prompts.py` | `prompts()` accepts a shared budget; new `prompts_scope`. `Display.trim` became `Display.compact` plus a `trims()` step, so the trim decision is made from the rows actually printed rather than from a pre-slice guess. |
| `src/sxr/views_info.py` | new `tools_scope`; `tools_view` accepts a shared budget. |
| `src/sxr/output.py` | `print_records` accepts an inherited budget and reports omissions once for the scope. Dedup stays per transcript. |
| `src/sxr/flags.py` | every discovered ref carries `extra["handle"]` (`@N`), the scope position the banner names. |
| `src/sxr/onboard.py` | `--help` epilog now states the range contract. |
| `README.md` | the session-addressing section documents ranges, banners and the shared `-n`. |
| `tests/test_session_range.py` (new, 280 lines, 69 cases) | see below. |

`PRIMER_BODY` was deliberately **not** touched. It already said "@A:@B range"
without qualification; that sentence was arguably wrong before this slice and is
correct now, so no primer edit and no version bump is needed.

### Tests

`tests/test_session_range.py` runs every case against both providers via a
parametrized fixture that writes two synthetic Claude sessions or two synthetic
Codex rollouts into `tmp_path` with `CLAUDE_CONFIG_DIR`/`CODEX_HOME` and
`SXR_CACHE_DIR` redirected there. Covered: every session rendered; content from
both sessions present; **single-session output byte-identical** for both `@1` and
`@1:@1`; inverted `@2:@1` byte-identical to `@1:@2`; `@1:@9` exits 2; `-n` as one
allowance (and the unlimited run equal to the sum of the per-session runs);
`--json` stdout parseable with identity on stderr; `--json` record count equal to
the sum of per-session counts (dedup neither drops nor repeats); `--json -n 1`
spanning the range; `--all` lifting the shared limit; `--include-context` widening
every session; `--budget`/`--line-limit` requesting compact text per session;
exit 1 only when no session produced output; `tools --json` keeping one complete
aggregate per session under `-n 1` (SXR-AUD-007); cold/warm/`SXR_NO_CACHE` reads
of a range agreeing; a prompt-less session not sinking the range; and providers
being unmixable in one scope.

Two real bugs were caught by these tests during development, both fixed:
`--all` did not lift the *shared* allowance (`prompts_scope` was passing the raw
`-n` instead of the resolved one), and the trim decision was computed from a
per-session slice that no longer matched the rows actually printed.

### Verification

Every command was run through the project checkout (`uv run`); the installed
`/opt/homebrew/bin/sxr` was never invoked or modified.

| Command | Baseline | After |
|---|---|---|
| `uv run pytest -q` | 676 passed, 0 failed | **745 passed, 0 failed** |
| `uv run ruff check .` | exit 0 | exit 0 |
| `uv run ruff format --check .` | exit 0 (147 files) | exit 0 (153 files) |
| `uv run konpy validate` | exit 0 | exit 0 |
| `uv run konpy check` | exit 0, 98 files | exit 0, 100 files, 0 violations |
| `uv run python audit/2026-09-10/verify_cli.py` | exit 1 — 66 passed, 1 failed | exit 1 — 66 passed, 1 failed |
| `uv run python cli-refactor/verify_prompts.py` | exit 0 — 5 of 5 | exit 0 — 5 of 5 |
| `uv run python cli-refactor/capture_ranges.py` | 28 captures (`before/`) | 28 captures (`after/`) |

**Baseline versus new failures.** There are no new failures. The single failing
historical contract is `PROMPTS-filter`, which failed at this slice's baseline
too: it asserts the pre-slice-01 meaning of `--all`. **Its status did not change
in this slice**, and no other historical contract changed status. Slice 1 stays
green: `verify_prompts.py` 5 of 5, and the whole 745-test suite includes
`test_prompt_defaults.py` and `test_prompt_limits.py` unmodified.

**Affected command matrix.** `uv run pytest tests/test_session_range.py
tests/test_show_boundaries.py tests/test_output_contracts.py tests/test_views.py
tests/test_record_shape.py tests/test_prompts.py tests/test_prompt_limits.py
tests/test_prompt_defaults.py tests/test_read_cache.py tests/test_handles.py
tests/test_cli.py tests/test_navigation.py` — 295 tests, 0 failures, 0 errors
(`evidence-02/matrix-pytest.log`, `matrix-pytest.xml`).

**Not run.** No bundle build or relocation check: no entry point, dependency or
packaging file was touched, and `packaging/verify.py` already carries unrelated
uncommitted edits. Nothing was published, installed or released; no real
transcript was read or rewritten. Linux and x86_64 are unavailable here. The
other command surfaces were exercised only through the test suite and the
67-check contract suite, not by hand.

## 4. Compatibility, limitations, decisions

**Compatible.** A single-session invocation is byte-identical, proven by capture
rather than assertion: `claude-show-single`, `claude-prompts-single`,
`claude-tools-single`, `claude-prompts-range-self` (`@2:@2`), `claude-list` and
`codex-list` are all UNCHANGED in `before-after-index.txt`. Exit codes are
unchanged: 0 with content, 1 when no selected session produced output, 2 for a
range that overruns the scope (`@1:@5` still prints `@5 out of range; 2 sessions
in scope`). Raw JSON record shape, per-transcript dedup and physical line
identity are unchanged. No argparse entry point is affected — `find`, `skills`
and `serve` are the argparse paths and none accepts a session range.

**Behavior change, intentional.** `show/prompts/tools @A:@B` now prints more than
it used to, because it used to print one session's worth. Scripts that relied on
a range being silently truncated will see extra output; the CSV's compatibility
cell anticipated this ("A range will produce more output as requested").

**Limitations.**

1. `show`'s banner duplicates the `file:` line of its own header, two lines
   apart. Collapsing it means changing `show`'s single-session header, which is
   SXR-CLI-03's territory, so I kept the uniform banner instead. Say the word and
   SXR-CLI-03 can drop the duplication.
2. `tools --json` still has no session field, so for a range its identity lives
   only on stderr. Adding `session`/`file` (matching `stats --json`, which
   already carries them) would change single-session JSON output, which you
   asked me to preserve. Flagged, not done.
3. A range cannot span providers: a scope is one provider, and `--claude
   --codex` is a usage error. Tested, not worked around.
4. The `# Skill inputs` line in `tools` is still uncapped by `-n` — a separate
   clause of `PAR-tools-typer-arg`, left open.

**Decision I need from you.** Only one, and it is not blocking: is the uniform
`# session @N  <id>  <file>` banner what you want for `show`, accepting the
one-line duplication with its header, or should SXR-CLI-03 fold the handle into
the header instead? Everything else in this slice follows precedents already in
the codebase.

**Concurrency you should know about.** Two agents were assigned this slice and
both wrote into this directory. The other run measured the baseline, built the
capture harness, recorded `before/`, noticed my edits and stopped without
implementing — its own README said so. Nothing was discarded: no source or test
file was written by both, its `before/` was independently re-derived from the
verified baseline snapshot and matched byte-for-byte, and its two harness scripts
were only `ruff format`ted (verified to leave both parse trees identical) so the
repository's format check would pass again. `evidence-02/README.md` has the
detail.

## 5. Ledger and next slice

`ledger.md`: SXR-CLI-01 **accepted 2026-09-11** with its three decisions recorded
as resolved; SXR-CLI-02 **delivered 2026-09-11**. The reject-negatives question
inherited from decision D-02 is now an explicit open question on SXR-CLI-03.

**Next proposed slice: SXR-CLI-03 — one documented selection pipeline for show.**
It is the natural successor: it already depends on SXR-CLI-02, it owns the two
loose ends this slice created or inherited (the banner/header duplication, the
negative `--budget`/`--line-limit` question), and it is the last structural
change to `show` before the remaining tasks become per-command work. It will
change `show` output shape, so it wants its own baseline snapshot the same way
this slice did.
