# Review packet — SXR-CLI-04: errors, source identity and complete text by default

## 1. What was asked, and one before/after invocation

**Task:** SXR-CLI-04, class `intentional-behavior-change`.
**CSV rows:** `CMD-errors-typer`, `PAR-errors-typer-arg`, `PAR-errors-typer-limit`,
`EXTRA-041` — all four already carried `task:SXR-CLI-04` in `disposition.json`, so
no disposition class changed.

`CMD-errors-typer` asks for three things: *"Include source session/file
coordinates on each result. Print complete error text by default and offer
--compact for summaries. Keep recorded error properties as the selection rule."*
Its acceptance clause is the concrete test: *"Two errors at the same sequence in
different sessions stay distinguishable. Long error endings and middles survive
default output. Limits remain global."*

Two synthetic sessions, each recording a failure at physical record 6:

```
$ sxr errors @1:@2 --compact          # before
#0006  12:06:06  Read  "ENOENT: /x beta"
#0009  12:09:09  Bash  "Traceback (most recent call last): ...[+1036 chars, middle]... exit status 65."
#0006  12:06:06  Read  "ENOENT: /x alpha"
#0009  12:09:09  Bash  "Traceback (most recent call last): ...[+1036 chars, middle]... exit status 65."
# 4 error records (Read 2, Bash 2)

$ sxr errors @1:@2 --compact          # after
#0006  bbbbbbb2  12:06:06  Read  "ENOENT: /x beta"
#0009  bbbbbbb2  12:09:09  Bash  "Traceback (most recent call last): ...[+1036 chars, middle]... exit status 65."
#0006  aaaaaaa1  12:06:06  Read  "ENOENT: /x alpha"
#0009  aaaaaaa1  12:09:09  Bash  "Traceback (most recent call last): ...[+1036 chars, middle]... exit status 65."
# 4 error records (Read 2, Bash 2)
# zoom: sxr show bbbbbbb2 --around 6
```

Before, the two `#0006` rows were byte-identical apart from the error text, and
the range printed no zoom hint at all. After, each row names the session it came
from, in the token `sxr show` accepts, so any single row is zoomable on its own.

Without `--compact`, the same command prints the error text whole: a one-line
error stays inline and quoted, a multi-line one becomes an indented block under
its row, so the row itself stays greppable:

```
$ sxr errors @1                       # after, default
#0006  bbbbbbb2  12:06:06  Read  "ENOENT: /x beta"
#0009  bbbbbbb2  12:09:09  Bash
    Traceback (most recent call last):
      File "/w/app/main.py", line 118, in handler
    ...
    The failure is at the END of this message, which middle trimming keeps but
    everything before it does not survive: exit status 65.
```

**Clauses closed.** Source identity per result (all three implemented rows),
complete error text by default (`CMD-errors-typer`), `--compact` (`EXTRA-041`,
and the second half of `CMD-errors-typer`'s `after` cell). `PAR-errors-typer-limit`'s
compatibility clause — *"Preserve nonnegative count syntax and -n alias"* — is
met by not touching `-n` at all; its logical unit is unchanged, so there is no
migration note to write.

**Clauses deliberately not closed.** `EXTRA-041`'s row calls itself a *proposed
option*; it is now implemented, and its acceptance ("verify the proposed contract
with targeted synthetic cases") is met by `tests/test_errors_view.py`. Nothing in
these four rows is left open.

## 2. The bounded diff

`slice-04.patch` — 541 lines, 360 added, 23 removed, 5 files. Generated with
`command diff -ruN -x __pycache__` between `/tmp/sxr-b04` (this slice's
hash-verified baseline snapshot, unpacked from `baseline-04/`) and the same file
list taken from the working tree. Written twice and `cmp`-ed, so it is
byte-reproducible.

sha256 `121ebee86271405268768035f72e6f183a9e4c656ae6f992449cdd15cf33bdd7`.
The full after-tree hash list is `slice-04-after-sha256.txt`, 128 files.

`__pycache__` is excluded because the before-capture imports `sxr` from the
unpacked baseline directory and leaves compiled files there. The archived
`baseline-04/worktree-snapshot.tar.gz` and its `sha256.txt` were written before
that run and contain no compiled file, so the recorded baseline is unaffected.

Separately, `maintenance-2026-09-11.patch` records the three reviewer-approved
changes made *before* this slice's baseline: the D-06 hazard fix in
`audit/2026-09-10/verify_cli.py` and `verify_prompts.py`, and the annotation of
`docs/session-search-hints-research.md`. Its hunks are reconstructed rather than
machine-generated, and the file says so and why.

## 3. Source identity, files, and what was verified

**Baseline:** HEAD `48b11c6cf08200de363e108924e42fdbc52d83e8`, snapshot
`baseline-04/` (127 files, `sha256.txt`), 825 tests passing.

### Changed files

| File | Lines | What changed |
|---|---|---|
| `src/sxr/views_read.py` | 189 → 229 | `errors` split into `error_records` (selection), `error_line` (one row) and `errors` (drive and tally) |
| `src/sxr/cli.py` | 279 → 286 | `--compact` on the `errors` command, plus its docstring |
| `src/sxr/onboard.py` | 291 → 298 | an `errors:` block in `EPILOG` and two example lines |
| `README.md` | +13 | one `errors` paragraph and two example lines |
| `tests/test_errors_view.py` | new, 346 | 19 cases × 2 providers = 38 tests |

`PRIMER_BODY` is untouched, verified by diffing the value against the baseline
checkout's: identical, sha256 `5d945756…`, 3747 chars. The primer's one `errors`
line (`recorded failures  sxr errors @N`) is still accurate, so the version-stamped
block that ships inside other repositories' `AGENTS.md` needs no reissue.

### Verification

| Command | Baseline | After |
|---|---|---|
| `uv run pytest -q` | 825 passed, 0 failed | **863 passed, 0 failed** |
| `uv run ruff check .` | clean | clean |
| `uv run ruff format --check .` | 159 files | 164 files |
| `uv run konpy validate` | exit 0 | exit 0 |
| `uv run konpy check` | 102 files, 0 violations | **103 files, 0 violations** |
| `verify_cli.py` (67 historical) | 66 passed, 1 failed | 66 passed, 1 failed |
| `verify_prompts.py` (5 migrated) | 5 passed, 0 failed | 5 passed, 0 failed |

**No historical contract changed status.** Both suites carry the same check ids
before and after, and a per-id comparison reports no status change. `PROMPTS-filter`
is the single failure in both runs, failing by the design D-02 recorded.

**New failures: none.** **Baseline failures: none**, apart from `PROMPTS-filter`,
which is a contract-suite case rather than a test.

No suppression was added anywhere; `konpy check` covers the new test module and
the grown source modules with zero violations. `onboard.py` is now 298 lines
against the 300-line limit — two lines of headroom, worth knowing before the next
slice touches it.

### Compatibility by capture

38 invocations captured from the baseline snapshot and from the working tree by
the same script in the same order (`evidence-04/before/`, `evidence-04/after/`,
annotated in `before-after-index.txt`):

* **12 byte-identical**, and they are the ones that matter: **every `--json` case
  on both providers**, plus the empty-scope exit 2 and the negative-limit exit 2
  paths. Raw provider records, their count under `-n`, and the stderr omission
  notice are all unmodified.
* **26 changed on purpose**: 10 text cases (source column, complete text, and the
  zoom hint now printed for ranges), 8 `--compact` cases (the flag did not exist,
  exit 2 → 0), and 2 `--help` cases.

Three relationships were checked across the two directories rather than asserted:
`--compact` recovers the old row text verbatim with only the source column added;
`--compact --json` equals plain `--json` byte for byte; and the shared `-n`
notice is identical before and after in text and JSON on both providers.

### Preserved behavior, checked explicitly

* **Slices 1 to 3.** `capture_show.py` rerun: **48 of 48 byte-identical** to
  `evidence-03/after/`. `capture_ranges.py` rerun: **28 of 28 byte-identical** to
  slice 3's own recheck. `show` is untouched by this slice.
* **SXR-AUD-005 / 015** — `--json` emits one complete object per distinct
  physical source line; `errors --json` still passes
  `test_json_limits_complete_distinct_records`.
* **SXR-AUD-006** — `-n` is one allowance across the range; the notice reads
  `# +3 more error records (shown 1 of 4; …)` before and after.
* **SXR-AUD-012** — a negative `-n` is still exit 2 before discovery, at both
  flag positions.
* Per-transcript dedup by `tool_use_id`, provider defaults, `--file` selection
  and the recorded-property selection rule are all unchanged; the second physical
  record for one call id still never becomes a second row.

### Two latent defects fixed inside these rows

Reading `views_read.errors` against the CSV turned up two real bugs in the
trailing zoom hint, both fixed here because they are the same rows' territory:

1. It read `picked[0].seq` after the session loop, so `picked` was the **last**
   ref's local list. For a range it named the wrong session's record number, and
   it would raise `IndexError` if the last selected session had no errors while an
   earlier one did.
2. It was suppressed for ranges (`if len(refs) == 1`) — exactly the case where a
   pasteable command helps most.

It now names the session and record of the first row actually printed.
`test_the_zoom_hint_names_the_session_of_the_first_row` pins that.

### Not run, and why

No bundle build, packaging check or relocation test: no entry point, dependency
or packaging file was touched, and `packaging/verify.py` already carries unrelated
uncommitted edits. Nothing was published, installed or released. No real
transcript was read or rewritten — every fixture is synthetic, in `tmp_path` or a
`TemporaryDirectory`, with `SXR_CACHE_DIR` redirected. No secret value appears in
any output. Linux and x86_64 are unavailable on this machine. Other command
surfaces were exercised only through the test suite and the 67-check contract
suite.

## 4. Compatibility, limitations, decisions

**The breaking change, stated plainly.** No default *text* invocation of
`sxr errors` is byte-identical any more: every row gains a source column, and
long error text is no longer trimmed. A script parsing rows positionally will
see a new field between the record number and the clock. `--compact` restores the
one-line-per-error shape but not the old column layout, because carrying identity
on every row is the point of the change. Rows still start with `#%04d`, so the
common `grep '^#0'` idiom — the one `tests/test_output_contracts.py` itself uses
— keeps working.

**Why identity is unconditional.** It would have been quieter to add the column
only when more than one session is selected, which is what slice 2's banners do.
I chose always-on so the column layout does not depend on how many sessions the
scope happened to contain: a parser needs one shape, and a row pasted out of
context still says where it came from. The cost is the one above, and it is why
the byte-identical count is 12 rather than 20.

**The source token is whatever unambiguously names the session.** It is
`ref.short_id`, which already expands from an 8- or 13-character prefix to the
full id when two sessions in scope share that prefix, and to `@N` when
`flags.sessions` finds colliding full ids. So the column is always a value `sxr
show` accepts. `test_colliding_short_ids_widen_the_source_column` and
`test_the_source_column_is_a_selector_show_accepts` pin both halves.

**A divergence left in place, deliberately.** `errors` selects on `event.is_error`
only. `show --errors` is wider: `show_select.is_error` also keeps records whose
`tag == "err"`, which for Claude is the *tool call* paired with a failed result,
not the result itself. So `sxr errors @1` and `sxr show @1 --errors` legitimately
select different record sets. `CMD-errors-typer` says to keep the recorded
properties as the selection rule, so I did not change either side; the difference
is now documented in `error_records`' docstring. **If you want them unified, that
is a decision for a later slice** — it would move counts and could move
`ERRORS-api-error`'s contract.

**The two deferred clauses you named.**

* **`--tail` under `--json` counting normalized events rather than distinct source
  records** (`PAR-show-typer-tail`): **left untouched.** It is a `show` clause and
  `errors` has no `--tail`. `errors --json` was already correct here — it calls
  `record_events(picked)` to collapse to distinct physical records *before* the
  budget counts them — and the four byte-identical `--json` captures per provider
  confirm this slice did not disturb that.
* **`--line-limit` not reaching tool-result bodies (SXR-CLI-21)**: **touched, not
  closed.** Error rows *are* tool-result bodies, and this slice removes
  `middle_trim`'s fixed 200+120 widths from the default path, so the specific
  complaint no longer applies to `sxr errors`' default output. It is not closed
  because `--compact` still uses those fixed widths and `errors` has no
  `--line-limit` flag to honour; giving it one would expand this slice's surface.
  SXR-CLI-21 keeps the clause, now narrowed to `show`'s trimmed `result` rows and
  `errors --compact`.

**No decision is needed from you to proceed.** The two questions above are for
later slices, and the ledger records them.

## 5. Ledger state and the next slice

`ledger.md` now records: SXR-CLI-03 **accepted 2026-09-11**; SXR-CLI-04
**delivered 2026-09-11**, awaiting review, with this packet, `slice-04.patch` and
`evidence-04/`; **D-05** (negative `--budget`/`--line-limit` on `show`, promoted
from S-01) and **D-06** (the approved audit-script edit) in the resolved-decisions
table, and the awaiting-confirmation table gone because it is empty. `contracts.md`
carries the `show`/`prompts` asymmetry as a do-not-harmonize rule, and a new rule
that any audit script must require an explicit `--output`.

The **Known evidence gap** section records the lost
`audit/2026-09-10/evidence/contracts.json` accurately, and corrects two details in
both directions:

* You are right that the file was the **original audit-time baseline**, not the
  67/0 remediation result, and that my earlier packet pointed at
  `remediation/final-contracts.json` as though it covered the loss. It does not,
  and the ledger now says so.
* Two of the details in your note do not match the files, and the ledger records
  what the files say. `contracts.log` holds **67 checks: 37 passed and 30 failed**,
  not 10 failures — the ten ids you listed are its first ten `FAILED` lines.
  And the 13:57:12 write is not slice 3's baseline: slice 3's baseline ran at
  15:07:55 local, slice 2's after-measurement at 13:45:24, so the overwrite falls
  in **slice 2's** verification phase. Every slice-3 `verify_cli.py` invocation
  did pass `--output` explicitly. Each timestamp is the file's own `generated_at`
  converted to local time and cross-checked against its mtime.
* Unrecoverable, confirmed independently four ways: untracked so git has no blob,
  no `audit/` path in any of the three baseline tarballs, no APFS local snapshots,
  and no other 37-passed receipt anywhere under `audit/`. No replacement JSON was
  fabricated.

A **second instance** of the same hazard turned up while fixing it:
`verify_prompts.py` also defaulted into an evidence directory, and a bare run at
15:38:52 during slice 3 rewrote slice 1's
`evidence/migrated-contracts.json`. Nothing substantive was lost there — the file
still records the same five checks with the same five `passed` statuses and
differs from slice 1's own run only in `generated_at` and per-check
`duration_seconds` — and its `.log` sibling is untouched. Both scripts now require
`--output`; a bare run exits 2 having written nothing, and the 67-check suite's
result lines are byte-identical to slice 3's afterwards. The other audit scripts
that take an output path (`capture_show.py`, `capture_ranges.py`,
`capture_errors.py`) already require it. The residual hazard I did **not** touch:
the 2026-09-10 *generator* scripts write their own products to hardcoded paths, so
rerunning one would replace preserved evidence. That is their purpose rather than
a flag default, and changing them is out of scope.

One finding about my own method, recorded in `baseline-04/NOTE.txt`: `/docs/` is
gitignored, so `git ls-files -o --exclude-standard docs` returned nothing and the
snapshots for slices 1 to 3 contain no `docs/` file even though their recipe named
`docs`. No slice changed `docs/`, so no evidence was lost, but the coverage claim
was weaker than it read. `baseline-04/` enumerates `docs/` with `find` and holds
all 15 files.

**Next slice proposed: SXR-CLI-05 — `cmds`: a filter no longer changes session
scope.** It is the highest-priority remaining defect and it is small in code:
`cli.py` reads `sessions if arg is None and grep_ else resolve(arg, sessions)`, so
a nonempty `--grep` with no selector silently searches every session in scope.
The fix is to make no-selector always mean the newest session and to add
`--all-sessions`.

**It needs your sign-off before I start, for a reason the other slices did not
have:** the generated primer teaches exactly the behavior being removed
(`sxr cmds --grep "git push"  # ALL sessions, one call`), and that primer block is
installed inside other repositories' `AGENTS.md` and `CLAUDE.md` files in the
wild — including this one's. Changing it means reissuing `PRIMER_BODY` and
bumping its version stamp, which every earlier slice avoided. Tell me whether to
proceed, or to take a different slice next.
