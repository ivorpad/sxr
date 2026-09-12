# Review packet — SXR-CLI-05: `cmds`, a filter no longer changes session scope

## 1. What changed, in the CSV's own terms

Rows: **`CMD-cmds-typer`**, **`PAR-cmds-typer-arg`**, **`PAR-cmds-typer-grep_`**,
**`EXTRA-044`**. All four already carried `task:SXR-CLI-05` in
`disposition.json`; no class changed. Each row's `before` cell was re-read
against the slice-05 baseline source first and still described it (recorded in
`disposition.json` under `verified_against_source["2026-09-11 SXR-CLI-05"]`, with
the CSV's sha256 re-asserted and its 408 rows intact).

The defect, from `PAR-cmds-typer-grep_`: *"Nonempty filter with no selector
changes scope from newest to all sessions."*

```
# before, on a project with two sessions
$ sxr cmds --grep "git push"
bbbbbbb2  #0002  12:02:02  Bash  "git push origin beta" -> ok      <- newest session
aaaaaaa1  #0002  12:02:02  Bash  "git push origin alpha" -> ok     <- and every other one

$ sxr cmds @1 --grep "git push"
#0002  12:02:02  Bash  "git push origin beta" -> ok                <- one session

# after
$ sxr cmds --grep "git push"
#0002  12:02:02  Bash  "git push origin beta" -> ok
# 1 of 2 sessions searched; all of them: --all-sessions

$ sxr cmds --all-sessions --grep "git push"
bbbbbbb2  #0002  12:02:02  Bash  "git push origin beta" -> ok
aaaaaaa1  #0002  12:02:02  Bash  "git push origin alpha" -> ok
```

Clauses **closed**: scope independent of the filter, `--all-sessions` as the
explicit scope, and the primer/help/README migration named in the compatibility
cells.

Clauses **left open and unweakened**, all still visible in `tasks.md`: complete
call text by default and `--events-json` (`CMD-cmds-typer`), `-F`/`--fixed` for
literal matching (`PAR-cmds-typer-grep_`), and the `--json` duplicate-record
clause, which belongs to SXR-CLI-06.

One facet of the same defect was not in any row and was fixed with it: **the
filter also changed the error contract.** With a `--since` window that keeps no
sessions, the baseline exits 1 with `--grep` and 2 without, because `--grep`
bypassed selector resolution entirely. Measured on the baseline snapshot and the
working tree side by side:

```
BEFORE  with --grep   : exit=1  # --since 2026-07-28 kept none of 1 sessions in scope
BEFORE  without --grep: exit=2  # --since 2026-07-28 kept none of 1 sessions in scope
AFTER   with --grep   : exit=2
AFTER   without --grep: exit=2
```

## 2. The bounded diff

`slice-05.patch` — 630 lines, 425 added, 45 removed, 11 files, sha256
`fa773dd9b55540247af637c80fefd8bfa68536072ddc1e19b727aeac212f045f`,
byte-identical when regenerated. It is `diff -ruN -x __pycache__` from the
hash-verified `baseline-05/` snapshot to the same enumeration of the tree now, so
it contains no compiled files and no `Binary files … differ` lines.

`slice-05-after-sha256.txt` records all 131 files of the after-tree.

Two files this slice touched are **outside** that bounded tree by design, because
it covers `src`, `tests`, `packaging`, `docs`, `CLAUDE.md` and the root config
files, not `audit/`:

* `audit/2026-09-11/cli-refactor/verify_prompts.py` — a comment correction only,
  described in §4.
* the audit records themselves (`ledger.md`, `tasks.md`, `contracts.md`,
  `disposition.json`, `evidence-05/`, `fixture_cmds.py`, `capture_cmds.py`).

### `baseline-05/` fixes a gap in my own earlier baselines

`/CLAUDE.md` is gitignored (`.gitignore:20`), exactly like `/docs/`, so the
`git ls-files` enumeration I used for baselines 1–4 silently omitted it — I
verified all four tarballs contain no copy. This slice edits `CLAUDE.md`, so
`baseline-05/` enumerates it explicitly, along with `uv.lock`, which the version
bump touches. `baseline-05/NOTE.txt` records both. No earlier slice modified
either file, so nothing was lost, but the coverage claim was weaker than it read.

## 3. Source identity, files, and verification

Baseline (`baseline-05/`, 130 files, `sha256.txt`, snapshot tarball) taken and
measured before any edit. HEAD `48b11c6cf08200de363e108924e42fdbc52d83e8`,
unmoved.

| file | before | after |
| --- | --- | --- |
| `src/sxr/cli.py` | 286 | 296 |
| `src/sxr/views_info.py` | 263 | 275 |
| `src/sxr/search_index.py` | 101 | 112 |
| `src/sxr/onboard.py` | 298 | 298 |
| `src/sxr/__init__.py`, `pyproject.toml`, `uv.lock` | 0.12.2 | 0.14.0 |
| `README.md` | 540 | 549 |
| `CLAUDE.md` | 61 (primer v0.3.0) | 84 (primer v0.14.0) |
| `tests/test_scope.py` | 258 | 262 |
| `tests/test_cmds_scope.py` | — | 305 (new, 40 tests) |

| gate | baseline | after |
| --- | --- | --- |
| `uv run pytest` | 863 passed, 0 failed | **903 passed, 0 failed** |
| `uv run ruff check .` | clean | clean |
| `uv run ruff format --check .` | 164 files | 169 files |
| `uv run konpy validate` | valid | valid |
| `uv run konpy check` | 103 files, 0 violations | **104 files, 0 violations** |
| `verify_cli.py` (67 checks) | 66 passed, 1 failed | 66 passed, 1 failed |
| `verify_prompts.py` | 5 passed | 5 passed |

**No historical contract changed status.** Both suites were compared per check
id, not by totals: identical id sets, zero status changes. `PROMPTS-filter` is
the one pre-existing failure, unchanged since slice 1. Both suites ran with an
explicit `--output` into `evidence-05/`, as D-06 requires.

**New failures: none.** One existing test needed correcting, not weakening:
`tests/test_scope.py::test_cmds_grep_honors_the_window` asserted exit **1** for
an empty `--since` window with `--grep`. That expectation existed only because
the filter bypassed selector resolution — the same window without `--grep`
already exited 2, as does every other read command with no sessions in scope. The
test now asserts exit 2 for both spellings and keeps its message assertion, so it
pins the consistency instead of the inconsistency. The reason is in a comment
above it.

**Compatibility, by capture.** 44 invocations per tree (22 cases × 2 providers),
`before/` importing `sxr` from `/tmp/sxr-b05`. **24 byte-identical**, 20 changed
with a named reason, none unexplained (`evidence-05/before-after-index.txt`); the
`after/` capture reproduces byte for byte on a second run. Everything that names
its own scope is untouched, including `@1`, `@2`, `@1:@2`, `--json`, `--grep ""`
and the negative-limit usage error. The 20 changes are only: the four
`--all-sessions` cases per provider (new flag), the five defaulted-scope `--grep`
cases per provider (the fix), and `--help`.

**Slices 1–4 re-verified** against their own post-slice references:
`errors` 38/38, `show` 48/48, `ranges` 28/28 identical.

**Not run:** `just release` and `just release-check` (a release, and its gates
require a clean tree), `packaging/build.py` and the four-platform bundle
verification, and anything on Linux or x86_64. The installed
`/opt/homebrew/bin/sxr` was read once to establish published versions and never
invoked as the tool under test.

## 4. Compatibility, the primer, and decisions needed

### What happens to an already-installed older primer — measured, in `evidence-05/primer-staleness.log`

* **`sxr init --check FILE` is the only detector.** `check_primer` is called from
  exactly one place, `onboard.init_cmd`. Nothing else in `src/sxr/` consults it;
  no other command warns, and there is no automatic re-render or refresh.
* **It compares only the version stamp, never the body.** A primer whose body was
  edited under a matching stamp reports `primer v0.14.0 up to date`, exit 0. This
  is why the version bump is required for correctness rather than ceremony:
  without it, every repository already at 0.12.2 would keep the old `cmds`
  recipe *and* `init --check` would actively assert it was current.
* **The default target is `AGENTS.md`.** A bare `sxr init --check` in this
  repository exits 1 with "no AGENTS.md found above …" — it never looks at
  `CLAUDE.md`, so the default check gives an answer about a different file.
* **`sxr init --write FILE` is the refresh path**, and it is manual and
  per-file. It replaces only the marker span; the konpy conventions above this
  repo's block survived verbatim.

So, plainly: **after this slice, every other repository on this machine silently
keeps a primer that no longer matches the tool, until a human runs
`sxr init --write` there.** Nothing detects it, nothing warns. This repository's
own `CLAUDE.md` is the proof that the manual path does not get walked: it sat at
**v0.3.0**, nine minor versions behind the binary, still teaching
`sxr cmds --grep "git push"  # ALL sessions, one call` — the exact instruction
this slice invalidates. I reinstalled it with `sxr init --write CLAUDE.md`, which
is in scope. **No repository outside this one was touched.**

### The primer edit

One line, +15 characters, same 60 lines:

```
-recorded commands     sxr cmds --grep "git push"
+recorded commands     sxr cmds --all-sessions --grep "git push"
```

Nothing else in `PRIMER_BODY` was wrong. Its "No ID means newest" bullet was
subtly false before (it was not true for `cmds --grep`) and is simply true now.

### Version: minor, and the package version has to move with it

The stamp **is** the package version — `onboard.primer()` renders
`sxr.__version__` — so there is no primer-only number to bump. The project's
convention, from its own history: minor bumps carry user-visible behavior
changes, including the closest precedent, `fff6575` *"primer teaches the new grep
surface …; 0.3.0 for the breaking -c format"*, which reissued the primer in the
same commit as a breaking output change. The behavior being removed here was
itself introduced as a minor feature, `6ea8d47` *"0.2.2: cmds --grep finds the
commands that did X across all sessions"*. So: **minor**.

**But the number needs your decision, because this checkout is behind what is
published.** `pyproject.toml` said `0.12.2`, while origin carries `v0.12.3`,
`v0.12.4` and `v0.13.0` (none present locally) and the Homebrew tap formula
already points at the `v0.13.0` release assets, which is what
`/opt/homebrew/bin/sxr --version` reports. `0.13.0` is therefore taken. I took
**0.14.0**, the next unused number, in `src/sxr/__init__.py`, `pyproject.toml`
and the `sxr` entry in `uv.lock` — the three files the justfile's own `release`
recipe names. `uv run` was exercised after the edit and did not re-lock.

The open question: **a `0.14.0` built from this tree would not contain whatever
`0.12.3`, `0.12.4` and `0.13.0` shipped.** Nothing is published by this slice and
`just release-check` would refuse anyway (dirty tree, not on `main`), so the
number is inert and provisional. Whether to reconcile this checkout with the
released history before releasing is yours; it is logged as open decision 4.

### Other compatibility notes

* Scripts relying on `cmds --grep X` reaching every session must add
  `--all-sessions`. The empty-result path teaches it on stderr, and a filtered
  search that defaulted its scope says so on stdout as one `#` note.
* `--all-sessions` together with a selector is a usage error (exit 2, "name one
  or the other") rather than one silently winning.
* The new disclosure note appears **only** when the scope was defaulted *and* a
  filter was given. A chosen scope is never second-guessed, and plain `sxr cmds`
  gains no output. Two tests pin both halves.
* `cmds` still covers non-shell tools, still emits complete raw records under
  `--json` with `-n` as one shared allowance, and `--grep ""` still means no
  filter.

### One correction, disclosed rather than made silently

I left your corrected "Known evidence gap" wording in `ledger.md` untouched, and
I agree with all of it. Two notes:

1. A comment I wrote in `verify_prompts.py` said the overwrite happened *"during
   slice 3"*, which repeats the attribution you corrected. I changed those two
   lines to "one bare run rewrote slice 1's receipt there while slice 3 was under
   review" and pointed the reader at the ledger, rather than leaving a stale
   claim in the code. The script is otherwise unchanged and still refuses a bare
   run (exit 2) and still reports 5/5 with `--output`. The equivalent comment in
   `audit/2026-09-10/verify_cli.py` needed no change; it never attributed the run.
2. That section says "None of the three per-slice baseline snapshots contain any
   `audit/` path". There are now five; `baseline-04/` and `baseline-05/` also
   contain none, verified. That is a count going stale, not an error, so I left
   the sentence alone.

## 5. Ledger state and the next slice

`ledger.md`: SXR-CLI-04 → **accepted 2026-09-11**; SXR-CLI-05 → **delivered
2026-09-11, waiting on the reviewer**. **D-07** recorded (the approval for
dropping the implicit scope, plus the finding that the bump is load-bearing).
Open decisions now: the deferred `prompts --compact` alias; the three
`decision-needed` CSV rows; whether `errors` and `show --errors` should select
the same records; **which version number the next release takes and whether to
reconcile this checkout first**; and **that nothing detects a stale installed
primer**, which is a design question this slice deliberately did not answer.

`contracts.md` gained the rules this slice establishes: a filter never decides
which sessions are read; a view may disclose a defaulted scope but not a chosen
one; the primer's stamp is the package version and the three version files move
together; check published tags before choosing a number; keep primer edits
minimal; edit no repository outside this one.

**Proposed next slice: SXR-CLI-06 — `grep`/`cmds`: valid JSON in every mode, one
record per physical line.** Class `defect`, nine rows. It picks up the `--json`
clause this slice deliberately left on `CMD-cmds-typer`, and it is the largest
remaining correctness gap: `grep -l --json` prints bare ids that are not JSON at
all, a physical line with two matching blocks is emitted twice, `-c` silently
overrides `-l`/`-C`/the budget, and `--sort` is accepted and ignored outside
`-c`. It needs no primer change and no version decision, so it does not depend on
how you answer the two open questions above. Stopping here for the checkpoint.
