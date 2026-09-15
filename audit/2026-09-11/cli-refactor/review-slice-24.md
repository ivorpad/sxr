# Review packet — SXR-CLI-24, results on stdout, omissions and notices on stderr

Delivered 2026-09-14, uncommitted. Baseline `55ad925`.

## 0. Why this slice, and not the next number

The queue's next number was `SXR-CLI-09`, and it is the one task I ruled out on the
brief you gave: it changes what `-n` counts for `stats` and changes that command's JSON
schema, so it would redefine a flag's meaning immediately after SXR-CLI-07 did. The
dependency check then removed three more candidates, and two of the removals are
findings in their own right:

- **`SXR-CLI-19` is already closed, and nobody noticed.** Its headline clause is that
  `init --check` compares only the version stamp, so an edited current-version block
  passes. Ran it: an edited block exits 1 with "stamped this version but its body
  differs". `check_primer` has compared the body since `f806ede`, the upstream merge.
  The rest of the task is closed too — inherited `--json` already exits 2, an invalid
  destination exits 2, `--write` is byte-identical on a second run and preserves
  surrounding prose, and the resolved target is named. What is left is one sentence of
  help text: `--global`'s exact fallback chain is in the function's docstring but not in
  `init --help`. `CODEX_HOME` is *not* consulted, but the row itself defers that
  ("Keep selection unchanged until a separate profile-target decision"). **Recommend
  striking SXR-CLI-19 and moving its one remaining clause into SXR-CLI-22.**
- **`SXR-CLI-10`'s core is blocked on a decision you already hold.**
  `PAR-tools-typer-limit` is one of the three `decision-needed` rows: whether `-n` may
  cap keys inside the `tools --json` aggregate, against `SXR-AUD-007`. Its other clause
  (identity fields in the aggregate) is schema growth, which the same three rows hold.
  It is not implementable without your answer, so it should not be picked up as if it
  were.
- **`SXR-CLI-18` is the biggest unblocker left** (15, 16, 17 and 20 depend on it, and it
  has no dependencies), but it changes exit codes for currently-valid invocations across
  every parser and six source files, and its review clause asks for an applicability
  table as a design artifact. That deserves a slice with your full attention rather than
  one following two behavior-changing slices. **Recommend it next.**

`SXR-CLI-24` was left: **deps `SXR-CLI-06`** (accepted), class **defect**, rows
`PAR-list-typer-limit`, `PAR-root-typer-coverage`, `EXTRA-011`. It changes no flag's
meaning — it makes behavior match what `README.md` and the primer already claim.

## 1. What changed

Three source changes, 31 lines added and 10 replaced, no new flags, no schema change.

**`views_info.list_view`** — the `--json` branch now counts through a `RowBudget` and
reports the omission on stderr. `list -n 1 --json` returned one session of four and said
nothing on either stream; the text view has printed `+3 more` for as long as it existed.

**`views_info.cmds_view`** — under `--json`, the deferred omission notice is finally
made, and the unsearched-scope disclosure now prints in both modes. `print_records`
deliberately skips its own notice when handed a scope-wide budget, so one omission is
reported for the whole scope instead of once per session; `cmds_view` was the caller that
never made the deferred call. Separately, `# N of M sessions searched; all of them:
--all-sessions` sat inside `if not json_out:`, so a JSON caller was handed a narrowed
scope with no way to learn it had been narrowed.

**`discovery_scope._coverage`** — a `--path` that does not exist on this machine is
labelled on the coverage line, but only when the scope came back empty. A typo read
identically to a real directory nobody has worked in. It stays silent when sessions were
found, because a recorded cwd that no longer exists locally still legitimately matches
the sessions recorded there.

`tests/test_streams.py` adds 12 tests. `README.md` and `contracts.md` record the
contract; `capture_streams.py` and `fixture_streams.py` are the harness.

## 2. How it was verified

- **Rows read from the CSV, not from `tasks.md`, and run before editing.** All three
  paraphrases were checked against their sources and carry the qualifiers this time,
  including `EXTRA-011`'s split between fields in envelopes and notices on raw streams —
  the qualifier that would have licensed adding fields to raw records against D-09.
- **Three of the rows' clauses were already satisfied**, and are reported as such rather
  than reimplemented: `--json` stdout is already pure in all 18 machine-readable cases,
  `_coverage` already labels provider roots and already separates discovery counts from
  searched source counts, and five views already reported omissions on stderr.
- **116 captures per side, both providers.** stdout byte-identical in 116 of 116, exit
  codes identical in 116 of 116; all 16 changed captures differ only by an added stderr
  line. Both providers changed in exactly the same eight places.
- **The 12 new tests were run against the restored baseline**: 5 fail, 7 pass. One
  failure per defect; the 7 that pass on both trees are the preservation tests, which is
  the only way a preservation test means anything.
- **Nine earlier harnesses re-measured**, and the 11 differences attributed by running
  each harness against the baseline twice rather than assuming: 44 of 44, 38 of 38 and
  92 of 92 stable, so none of the 11 is nondeterminism. Nine are the new `cmds --json`
  notices; two are the coverage label firing on `/elsewhere`, a synthetic path in slice
  4's fixture that genuinely is not on this machine. stdout and exit codes identical in
  11 of 11.
- **Gates in a clean environment** (no `CLAUDE_CONFIG_DIR`, `CODEX_HOME` or `SXR_*`
  set): 1123 passed, ruff clean, 221 files formatted, konpy 115 files with 0 violations
  and no suppressions, `verify_cli.py` 66 passed with `PROMPTS-filter` the only failure
  (unchanged), `verify_prompts.py` 5 of 5.
- **Preserved and checked, not assumed:** raw records per D-09 (a `cmds --json` record
  is still the provider's line, with no `shown`/`omitted` added), the `grep_session`
  projection per D-12 with no match count, physical line identity (a line with two tool
  calls is one record under a cap), dedup, provider defaults, `--file` selection, exit
  codes including the empty-result 1 and negative-limit 2, and the primer as-is per D-14
  — this slice needs no primer edit, because it makes an existing primer claim true
  rather than changing what the primer would have to say.

## 3. Migration

**There is nothing a stdout-reading script must change.** That is the measurement above,
not an intention. What changes for callers:

| invocation | before | after |
| --- | --- | --- |
| `list -n K --json` | K of N sessions, silence | same stdout, `# +N-K more sessions …` on stderr |
| `cmds -n K --json` | K of N records, silence | same stdout, `# +N-K more records …` on stderr |
| `cmds --grep X --json` | narrowed scope, silence | same stdout, `# K of M sessions searched; all of them: --all-sessions` on stderr |
| `--coverage` with a missing `--path` | `(exact cwd)` | `(exact cwd; path not present on this machine)`, empty scopes only |

A script that pipes stderr into stdout and parses the union will see new lines. That is
the same exposure every previous omission notice created, and it is the reason the
notices are on stderr rather than in the data.

## 4. Compatibility and what was deliberately left alone

**Human-mode headers and footers stay on stdout.** `EXTRA-011`'s before-cell names them
as the problem, but its compatibility cell says "Review before implementing", and
moving them would break every script reading `# +N more` or the `# read:` guidance line
from `sxr list`. Raised as an open decision below rather than taken.

**No omission metadata inside any object.** `EXTRA-011` permits `total/shown/omitted`
fields "where structured envelopes exist" — `tools --json` and `stats --json` are such
envelopes. Schema growth is precisely what your three `decision-needed` rows hold, so
this slice reports on stderr and adds no field anywhere.

**One text-mode wording is now inconsistent, deliberately.** `list -n 1` says `# +3
more (raise -n, -n 0 for all)` on stdout while `list -n 1 --json` says `# +3 more
sessions (shown 1 of 4; raise -n, -n 0 for all)` on stderr, because the JSON path reuses
the shared `RowBudget.notice` wording that every other view uses and the text footer is
its own older string. Unifying them would change text stdout, which this slice promises
not to do. Worth a line in a later slice.

**`views_info.py` is 294 lines against konpy's 300.** It passes with no suppression, but
it is the tightest module in the tree and the next slice to touch it must split it first.

## 5. Open questions and disclosures

1. **Should human-mode footers move to stderr?** The row asks for it and says to review
   first. My recommendation is no, or not as a whole: `# +N more` is arguably a notice,
   but the `# read:`/`# find:` guidance lines and the `# session @N` banner are what
   make text output teachable, and `sxr list > notes.md` losing them is a real loss. If
   you want a split, the honest cut is omission notices to stderr and guidance staying,
   which needs its own migration note.
2. **`SXR-CLI-19` should be struck and its remainder folded into `SXR-CLI-22`**, on the
   evidence in section 0. I have not edited the queue to do this — it is your call.
3. **`contracts.md` carried a stale claim and I corrected it, visibly.** It said
   `init --check` "compares the stamp only, never the body". `f806ede` made that false.
   It mattered because both `SXR-DOCS-02` (queued by D-14) and `SXR-CLI-19` rest on what
   `--check` can detect, and a document later slices trust was telling them the wrong
   thing. This is the same failure as the dropped qualifiers, one step further along: not
   a paraphrase losing a qualifier, but a derived claim outliving the code it described.
   Worth asking whether the *other* contract bullets have the same problem; a mechanical
   check is harder here than for CSV rows, because these claims cite behavior rather than
   text, but the ones that name a file and line could be checked cheaply.
4. **A clock disagreement, stated rather than settled.** Your message dates D-14
   "2026-09-13 — that is today"; this machine read 2026-09-14 throughout, and `55ad925`
   is authored on the 14th. I recorded your decisions with your dates and my artifacts
   with theirs, and did not reconcile them. Last time I reconciled a date of yours
   against my own evidence, your date was the correct one.
5. **Left uncommitted**, as with every slice before review. The tree is clean apart from
   this slice, `HEAD` is `55ad925`, `origin/main` is still `8f93114`, no stashes, nothing
   pushed, no existing commit amended.
