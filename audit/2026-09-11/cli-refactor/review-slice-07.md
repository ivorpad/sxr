# SXR-CLI-07 — grep: result cap separated from character caps

Delivered 2026-09-13, on top of `63a16c6`. Left uncommitted; see part 5.

## 1. What changed and why

`grep` had three ways to stop printing and two flags to control them, so one flag
had to do two jobs. `-n` capped results *and* lifted the character budget, which
meant `grep -n 0 --budget 400` printed everything and silently ignored the budget
the caller had just typed. Per-match flattening to 200 characters applied no matter
what anyone asked, so there was no spelling at all for "every match, whole". And
`--all` — a flag whose name promises completeness — did nothing to a normal scan and
only kept zero-count rows in `-c`, where it printed nothing at all if every session
had zero.

Now each cap answers to one flag. `-n` caps results. `--budget` stops output by
characters. `--line-limit` flattens each row. `--full` lifts the two character caps
and leaves `-n` in charge of how many, exactly as `show --full` behaves under
SXR-AUD-008. `--all` lifts all three. `--include-zero` takes over the zero-count-row
job and makes an all-zero table printable, while a zero-match scope still exits 1.

**`--full` and `--all` do overlap, and the overlap is the resolution rather than a
loose end.** `--all` is defined *as* `--full -n 0` — one sentence in `--help`, one
line in the README, and a test that asserts the two produce byte-identical stdout on
both providers so they cannot drift. `--full` earns its own name because "every
match, whole" and "these five matches, whole" are both real questions and `-n` is
the only difference between them. The view reads two derived properties,
`rows_uncapped` and `complete_text`, rather than the flags themselves, so neither
flag can quietly grow a private meaning.

**`grep --all` and `prompts --all` mean the same thing, deliberately.** D-01 settled
that `prompts --all` means completeness and overrides an explicit `-n`/`--budget`,
with selection-widening moved to a separately named `--include-context`. `grep --all`
now means completeness, overrides an explicit `-n`/`--budget`, and its
selection-widening moved to a separately named `--include-zero`. Same meaning, same
precedence, same shape of sibling flag. Two tests name D-01 in their docstrings so
the parallel is checkable rather than asserted, and `contracts.md` records that a
later slice must not give one command's `--all` a meaning the other lacks.

## 2. Verification

Rows checked against source **and run** before editing, in
`evidence-slice-07/before/`. All six `before` cells were accurate, which is worth
stating after two slices where one was not: `--budget 400 -n 0` printed 16 data rows
where `--budget 400` printed 1; `-n 0` alone produced zero complete texts; `--all`
on a normal scan was byte-identical to no flag; `--all -c` on an all-zero scope
printed nothing and exited 1; `--full` and `--include-zero` exited 2 as unknown
options.

Applying the qualifier lesson to the rows rather than the paraphrase found a clause
`tasks.md` had dropped. `PAR-grep-typer-budget` asks for a budget "**with omission
metadata**" and for omitted results "visible in text **and structured metadata**";
the paraphrase kept only the character-stopping half. The gap was real: `grep -n 2
--json` printed 2 of 16 records with nothing on stdout and nothing on stderr, while
the same cap in text mode printed a footer. Closed by sending the footer to stderr
under `--json`, the same `stderr=json_out` shape `errors` already uses. Structured
metadata *on stdout* was not available to me — D-09 keeps stdout to raw records —
and an unreported omission is the worse of the two problems.

96 captures per side, 48 per provider. **38 of 96 byte-identical**, and the changes
concentrate exactly where the slice is aimed: 0 of 14 in the `--full` group (all
were "No such option" before), 16 of 24 in the `keep` group that must not move. All
eight `keep` changes are the `-c` footer's flag name or `--help` growing a
paragraph; `json-dedup`, `ids-json` (D-12's `grep_session`), `count-json`,
`context-3`, `ids-plain` and all three zero-match cases with their exit codes are
byte-identical.

Earlier slices re-measured with the corrected harnesses, and differences
**attributed by measurement**: `recaptures/pre07/` re-runs each harness against the
restored `baseline-07` tarball via `--source`, so anything differing there predates
this slice. Slices 3 and 4 are 48 of 48 and 38 of 38 identical. 28 differences are
attributable to slice 7 — 18 in slice 6's captures, 8 in slice 8's, 2 in slice 21's
— and every one is the `-c` footer's flag name, the capped footer's new hint, or the
omission notice appearing on stderr under `--json`. No data row, count, id,
timestamp or exit code moved.

Live corpus, not only fixtures: `sxr grep "budget" -n 3 --json` gives 3 stdout lines
that all parse with `# 39 matches, showing first 3` on stderr, and `sxr grep
zzzznotfoundzzzz -c --include-zero` prints 36 zero rows and exits 1.

Gates: 1111 passed, ruff check and format clean over 217 files, konpy 114 files with
0 violations and no suppressions, `verify_cli.py` 66 passed with `PROMPTS-filter`
the only failure, `verify_prompts.py` 5 of 5. Both contract suites unchanged, both
run with an explicit `--output`.

## 3. Migration

Three changed spellings, each documented where the person who used it will look.

| spelling | before | after | where the migration is stated |
| --- | --- | --- | --- |
| `-n 0` | lifted the row cap **and** the character budget | lifts the row cap only; says so on stderr when the budget then stops output | `--help`, README migration list, and the runtime notice itself |
| `--all` | kept zero-count rows in `-c`; no effect on a normal scan | lifts all three caps; `= --full -n 0` | `--help`, README table and migration list, `-c` footer |
| `--all` for zero rows | the only way to keep them | `--include-zero` | the `-c` footer a script author sees first, plus README |

The runtime notice matters more than the prose: someone whose script says `grep -n 0
--budget 400` gets told, on stderr, that `-n 0` lifts the result cap only now and
that `--all` or `--budget 0` is what they meant. The `-c` footer stopped advertising
a flag that no longer does the job it advertises.

`PRIMER_BODY` is unchanged, and I want that looked at rather than assumed. Checked
line by line, the installed primer never mentioned `grep --all`, `grep -n 0` or
zero-count rows, so nothing in it is false, and its one adjacent sentence about
`--full` printing whole text became *more* accurate. Adding to it costs either a
version bump nobody approved or a v0.14.0-stamped block whose content differs from
what this tree's v0.14.0 generates — the drift `write_hazard` exists to catch.
Raised as open decision 10, **resolved by the reviewer as D-14 (2026-09-13): leave
the primer as it is.** Primer content for the flag-changing slices is deferred to a
single refresh once they are done, so the version moves once rather than per slice;
that refresh is queued as `SXR-DOCS-02` and carries this slice's ready wording.

## 4. The qualifier audit you asked about

Feasible and cheap: one script, `audit_qualifiers.py`, inside this slice rather than
a slice of its own. Three mechanical checks over all 24 tasks and 408 rows, using
the CSV's own `command` field rather than any judgment about prose.

**0 findings for the slice-21 shape itself** — no task's prose speaks normatively for
a command none of its rows are scoped to. Check 2 generalizes it (an unscoped rule
about a flag several commands own, in a one-command task) and is validated by
`--selftest` against slice 21's preserved original wording, which it catches. It
found 10, of which 9 are `before`/`after` cells under a heading that names the
command, and **1 was real and is fixed**: `tasks.md` recorded D-01 and D-02 with no
command named, though both are scoped to `prompts` and `--budget` belongs to `show`
and `grep` too — the identical shape, on the identical subject, as the sentence that
manufactured the D-05 conflict. A later slice reading it as a global rule would have
re-broken exactly what D-05 protects. The 131 clause findings are all in undelivered
tasks whose prose is a one-line summary by design; **zero in any delivered task**.
Full table in `ledger.md`.

## 5. Open questions and disclosures

**Open decision 10 — resolved as D-14.** The primer stays as it is, and the deferred
refresh is queued as `SXR-DOCS-02` so it stays a visible task rather than an implicit
obligation. Reasoning in `ledger.md`.

**Left uncommitted.** Every earlier slice was reviewed uncommitted and committed on
acceptance, and this one changes two documented flag meanings — the case where I
would least like the record to show a commit before you have looked at the
migration. `slice-07.patch` is written and verified to apply cleanly to the restored
baseline.

**Left open in the rows.** `CMD-grep-typer`'s `problem` cell also says "-C limits
blocks rather than physical lines", and `PAR-grep-typer-limit` asks to define the
unit for each mode. Done for match rows, `-l` sessions and `-c` table rows; not for
`-C` windows, which no acceptance clause here covers.

**Two tests changed rather than added.** `test_limit_caps_match_rows_and_reports_the_total`
asserted the old footer wording and `test_count_all_restores_zero_rows` constructed
`GrepOpts(include_all=True)`. Both were asserting the contract this slice
deliberately changes; the second is renamed to `test_count_include_zero_...` and
both keep their original assertions otherwise.

**A leaked environment variable, disclosed because it could have affected a gate.**
`CLAUDE_CONFIG_DIR=/tmp/sxr-demo02/claude` and `SXR_CACHE_DIR` were sitting in my
working shell from an earlier demonstration, which I noticed when a live-corpus check
reported 0 sessions. Every gate reported above was re-run after clearing them and
these are the post-clearing numbers. The captures were never exposed to it — each
harness sets its own provider root and pops `SXR_*` per case — but the first full
suite run of this slice was, so I re-ran it rather than report a number taken in a
dirty environment.

**Date corrections carried in this slice's documents.** The `2026-09-12` entries that
belonged to the 13th were fixed in `63a16c6`, and this slice's own entries are dated
2026-09-13 against the artifacts. One of the four was wrong: I changed a date the
reviewer had dictated for D-13, on mtime evidence that cannot speak to when a
decision was made. The message was sent on the 12th and only its execution slipped;
the reviewer has reverted it and recorded the principle in `ledger.md`.
