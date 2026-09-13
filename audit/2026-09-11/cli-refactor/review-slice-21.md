# Review packet — SXR-CLI-21, validate and document the compact-display flags

## 1. What changed, and why

Three defects, all in how much text a scan prints.

**One view had two caps.** `grep -C` printed its match row through
`one_line(event.text)` with no cap argument, so it used `one_line`'s built-in 200
whatever the caller asked for, while the context rows below it read
`SXR_LINE_LIMIT`. Measured: the longest match row was 239 characters at
`SXR_LINE_LIMIT=60`, at `400`, and at the default alike. `views_grep._emit` now
resolves the cap once, above the branch, and passes it to both.

**A tool-result body was exempt.** `middle_trim` kept a fixed 200-and-120 split
regardless of the cap, so `errors --compact` printed a 383-character row at cap 60
and at cap 400, and `show --tool-results --line-limit 60` printed 122-character
text rows next to a 399-character result row. It now derives head and tail from
the one cap — `head = cap`, `tail = cap * 120 // 200` — which **at the 200 default
is exactly the 200 and 120 it always used**, so nothing moves unless a cap was
asked for. This is the clause SXR-CLI-03 and SXR-CLI-04 each touched and deferred
here; see §5.

**An unusable environment value changed behavior in silence.** `_env_int` caught
`ValueError` and returned the default, so `SXR_BUDGET=abc` — or an empty string, a
float, a negative — capped or uncapped every command in a shell and said nothing.
Worse, a negative one was *obeyed*: `SXR_LINE_LIMIT=-5` reached `show`'s footer,
which announced "trimmed to -5-char lines" and then trimmed nothing. Now one
stderr notice names the value and the default, once per variable per process, and
only when the command would have applied it.

`grep --budget` also gains `min=0`, so a negative char budget exits 2 as it does on
`show`. That extends D-05 to the other command with a char budget; it does not
touch `prompts`.

Files: `util.py` (+56/−8), `views_grep.py`, `views_read.py`, `flags.py`,
`tests/conftest.py`, `tests/test_compact_caps.py` (new, 30 cases), `README.md`,
`contracts.md`. Diff: `slice-21.patch`.

## 2. The spec conflict you flagged — no decision needed

`tasks.md:264` said `--budget` and `--line-limit` should "reject negatives (exit
2)", which read across every command is the harmonization D-05 refused. **I checked
the source rows before rewriting anything, and they do not propose it.**
`PAR-show-typer-budget` and `PAR-show-typer-line_cap` are both scoped `command:
sxr show`, and their `after` cells say "reject negatives" of *those* flags. The two
env rows ask only to "validate numeric values" and, for `prompts`, to "remove
implicit trimming from plain prompts" — which SXR-CLI-01 did.

So the conflict was manufactured by the task spec's own paraphrase, which dropped
the row's command scope. That is a **third kind of row defect** beyond the stale
and wrong-when-written ones already found: a *derived* document that lost a
qualifier the source row carried. There is nothing better-for-users to weigh
against D-05, so I have not left you a decision — I rewrote the spec, kept the
original wording beside it with this explanation, and re-measured rather than
re-implemented the `show` half:

| invocation | exit | source of the behavior |
| --- | --- | --- |
| `show --budget -1`, `show --line-limit -1` | **2** | D-05, delivered by SXR-CLI-03; `min=0` on `BudgetF`/`LineLimitF` |
| `prompts --budget -1`, `prompts --line-limit -1` | **0**, whole text | D-02; `PromptBudgetF`/`PromptLineLimitF` have no minimum |
| `grep --budget -1` | **2** — changed here | extends D-05's reasoning, not D-02's |

`test_show_keeps_refusing_and_prompts_keeps_never_truncating` pins both halves in
one test, so a future edit cannot erase one of them without failing.

## 3. Verified before editing: every CSV row run, not just read

| row | status against current source | closed here |
| --- | --- | --- |
| `PAR-show-typer-budget` | **stale.** Its "reject negatives" is already true — `show --budget -1` exits 2, measured. Its remaining ask, describing the flag as a compact-display threshold and stating when full/zoom/JSON bypass it, was documentation only. | documentation; the rejection was already done |
| `PAR-show-typer-line_cap` | **half stale, half open.** Negatives already exit 2. "Apply the same explicit cap policy to all displayed event kinds" was open: measured, a tool result kept 383 characters at cap 60 and at cap 400. | yes, the open half |
| `EXTRA-009` | **partly stale.** `--around 0` already exits 2 (min=1), row limits and `--tail` already reject negatives. `grep --budget` did not. | the `grep --budget` part |
| `EXTRA-028` | **accurate.** "Non-integer values fall back silently" and "negative values disable" both reproduced. Its `prompts` clause was closed by SXR-CLI-01. | yes |
| `EXTRA-029` | **accurate, and the most precise row in the set.** "Grep normal rows hardcode `util.one_line`'s 200 default, while context reads this environment setting" is exactly what the captures show. | yes |

No row was wrong-when-written this time. Three were stale in the direction of
already-fixed, which is the healthy direction, and I re-measured each rather than
trusting the status column: `evidence-slice-21/before/` holds the run for every one.

## 4. Compatibility

118 invocations per side, both providers. **85 byte-identical, 33 changed**, each
named and reasoned in `evidence-slice-21/README.md`. The load-bearing numbers:

* **0 of 16** `bypass` cases changed. `--full`, `--around`, `--range`, `--tail`,
  `--json`, plain `prompts` and plain `errors` are untouched under a 500-char
  budget, so the "complete views ignore the budget" contract holds.
* **Default output does not move.** `grep` rows, `cmds` and trimmed `show` at the
  default cap are byte-identical, because the derived split equals the old fixed
  one at 200.
* **16 of the 18 `env` changes add a stderr line and change stdout not at all.**
  The other 2 are the `SXR_LINE_LIMIT=-5` footer absurdity.
* **Zero** notices appear on stdout across all 118 after-captures, and the ten
  `--json` cases report every stdout line parsing, the same as before. `show
  --json` and `list` stay silent about a budget they never consult.
* Preserved and re-measured, not assumed: raw records per D-09, the `grep_session`
  projection per D-12, `@N` semantics per D-13, physical line identity, per
  transcript dedup, exit codes, provider defaults, `--file` selection.

Earlier slices re-measured with their own harnesses, and each difference
attributed by re-running against `baseline-21`:

| slice | files | differ from accepted `after/` | caused by this slice |
| --- | --- | --- | --- |
| 02 | 28 | 19 | **0** — identical 19 differ from `baseline-21`, byte for byte |
| 03 | 48 | 0 | 0 |
| 04 | 38 | 0 | 0 |
| 05 | 44 | 2 | **0** — slice 6's `cmds --help` wording |
| 06 | 92 | 2 | **2** — `grep --help` now shows `--budget <int range>  [x>=0]` |
| 08 | 72 | 0 | 0 |

Gates: **1079 pass** (1049 + 30), ruff check clean and `ruff format --check` reporting 211 files already formatted (a formatter tally, not a source-file count),
konpy 113 files with 0 violations and no suppressions, `uv run` only. Both contract
suites re-run with explicit `--output`: **66 passed with `PROMPTS-filter` the only
failure**, and prompts **5/5** — no status change. `verify_cli.py` lives at
`audit/2026-09-10/verify_cli.py`, not under `command-review/`.

## 5. What slices 3 and 4 actually deferred, and three cautions

**The deferral, quoted.** SXR-CLI-03: *"PAR-show-typer-line_cap's 'same explicit
cap policy for all event kinds' (tool-result bodies still use `util.middle_trim`'s
fixed widths; that clause stays with SXR-CLI-21)"*. SXR-CLI-04: *"SXR-CLI-21's
`--line-limit` clause is touched, not closed: the default path no longer trims at
all, but `--compact` still uses `middle_trim`'s fixed widths and `errors` has no
`--line-limit`"*. Both name the same object — `middle_trim`'s fixed widths — and
neither defines a policy. So there was no third policy to invent: deriving the
widths from the one cap closes both, and `errors --compact` gets its cap from
`SXR_LINE_LIMIT` since the command has no flag.

**The env notice's three failure modes, each checked.** It reaches stderr only (0
stdout occurrences in 118 captures). It fires at most once per variable per run —
the dedupe is process state, which is right for a CLI where each invocation is a
process, and `tests/conftest.py` clears it per test since a test session is one
process. And a *valid* value prints nothing, so a correctly configured shell is
silent. Neither contract suite changed status.

**A harness bug I introduced and caught.** My first capture run under-reported the
notices, because it ran all 118 cases in one process and the dedupe leaked across
them — the first case to see a bad `SXR_BUDGET` was the only one to report it.
Fixed by resetting per case, looked up with `getattr` so the same file still runs
against the baseline tree, and both sides recaptured. Separately, the two oldest
harnesses take the output directory as a **positional** argument: passing
`--output` makes them write into a directory named `--output`, and `--help` into
one named `--help`. Both stray directories were created here and removed; the
slice-02 and slice-03 recaptures were re-run with the positional form.

**Scope.** `util.py` and `flags.py` are read by every command, so I kept the
`util.py` changes to two functions and left `line_limit`/`scan_budget`'s signatures
and precedence alone. `middle_trim`'s signature changed from `(text, head, tail)`
to `(text, cap)`; it had exactly two callers, both in `views_read.py`, and no test
referenced it before this slice.

**Left open, deliberately.** EXTRA-009's `find_worker` idle check and `skills_cli`'s
numeric arguments: separate commands with their own dispatch, neither in this
task's `files` list, and folding them in would have widened a shared-plumbing slice
into two more entry points. `PAR-show-typer-tail`'s JSON record-counting clause
stays where SXR-CLI-03 left it, needing its own decision. One behavior change to
note explicitly: a script setting a *negative* `SXR_BUDGET`/`SXR_LINE_LIMIT` to
mean "unlimited" now gets the default and a notice. That reading was never
documented — `0` is — and `README.md` carries the migration line.

**Next.** `SXR-CLI-07`'s declared dependencies (`SXR-CLI-06`, `SXR-CLI-21`) are now
both delivered, so it is unblocked and is the natural next slice.
