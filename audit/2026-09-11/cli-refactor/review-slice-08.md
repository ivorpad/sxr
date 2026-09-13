# Review packet — SXR-CLI-08, one timestamp parser for every sort, filter and format

Delivered 2026-09-12. Nothing pushed, no existing commit amended, and the slice is
left uncommitted in the working tree.

## 1. Task, rows, and a concrete before/after

**SXR-CLI-08**, rows `CMD-list-typer` and `EXTRA-012`.

```
$ sxr list --path /w          # a corpus with offset-bearing starts

  before                                     after
  @1 ddddddd4 2026-09-11T00:30:00Z  open S4  @1 ddddddd4 2026-09-10T22:30:00Z  open S4
  @2 aaaaaaa1 2026-09-10T09:00:00Z  open S1  @2 ccccccc3 2026-09-10T08:00:00Z  open S3
  @3 ccccccc3 2026-09-10T08:00:00Z  open S3  @3 bbbbbbb2 2026-09-10T07:00:00Z  open S2
  @4 bbbbbbb2 2026-09-10T07:00:00Z  open S2  @4 aaaaaaa1 2026-09-10T07:00:00Z  open S1
```

S1 recorded `2026-09-10T09:00:00+02:00` and S2 recorded `2026-09-10T07:00:00Z`.
They are the same moment. Before, S1 displayed two hours late and sorted two rows
away from its twin; after, they show the same `started` and are adjacent. S4
recorded `2026-09-11T00:30:00+02:00`, so it now displays the day it actually
belongs to — the day whose `--since 2026-09-10 --before 2026-09-11` window
contained it all along.

### Every clause, verified in source and by running it before editing

| row | clause | verdict |
| --- | --- | --- |
| both | `util.day()` returns `ts[:19] + "Z"` | **confirmed**, `util.py:61-63`, and reproduced: S1 printed `2026-09-10T09:00:00Z` |
| both | list ordering compares timestamp strings | **confirmed**, but not where the rows say — see corrections |
| both | `grep -c --sort started` compares strings | **confirmed**, `grep_counts.py:56`; before order `S2, S3, S1, S4`, now `S2, S1, S3, S4` |
| EXTRA-012 | window filtering already uses instants | **confirmed**, `handles.window` via `_instant`; and re-measured, unchanged |
| EXTRA-012 | `handles.py:_instant` | **confirmed** as the one correct parser already present; reused rather than rewritten |
| CMD-list-typer | empty scope exits 0 | **confirmed** and preserved (`SXR-AUD-017`) |
| CMD-list-typer | `find`'s date column slices `[:10]` | **confirmed**, `find_service.py:161` |

### Two rows to correct, and both kinds you named

- **Wrong when written, not stale.** Both rows cite
  `src/sxr/discovery.py:deduplicate` as an ordering site. It does not sort, and it
  did not at the audited base `48b11c6c` either — I checked the file at that
  commit. The sorts that actually decide `@N` are `claude_discovery.py:82` and
  `providers/codex.py:153`, which neither row names.
- **Cited files needing no change.** `discovery_scope.py` does no timestamp work,
  and `views_grep.py`'s timestamp handling moved into `grep_counts.py` during
  slice 6, so the row's file list is now one file out of date there.
- **Clauses left open, unweakened.** `CMD-list-typer` also wants a handle, the
  scope and an exact `--file` follow-up in `list --json`. That is additive
  metadata with no timestamp content; it is untouched and still open.

## 2. The diff, and where it is

- `slice-08.patch` — 1019 lines, 13 files: `git diff HEAD` for `README.md`,
  `src/` and `tests/`, plus the new `tests/test_timestamps.py`. This necessarily
  includes slice 6, which is also uncommitted.
- `slice-08-only.patch` — 596 lines, this slice alone, produced by diffing the
  working tree against `baseline-08/worktree-snapshot.tar.gz` extracted. Read
  this one to review slice 8 in isolation.

Eight files: `src/sxr/util.py` (+42), `src/sxr/handles.py` (−1),
`src/sxr/claude_discovery.py` (+1), `src/sxr/providers/codex.py` (+1),
`src/sxr/find_service.py`, `src/sxr/grep_counts.py`, `README.md`, and the new
`tests/test_timestamps.py` (328 lines, 53 cases).

## 3. Source identity, verification, and what was not run

Baseline `baseline-08/`, taken before any edit, `head.txt` = `f42b1ad5…`.

**How it was enumerated, and why differently from every earlier baseline.**
Baselines 01–05 used `git ls-files` plus `git ls-files -o --exclude-standard`,
which silently omitted every gitignored path. baseline-06 caught the worst case of
that and bolted on a `find audit`. This one stops enumerating by git state
altogether: it takes every file on disk except `.git/`, `.venv/`, the three tool
caches, `__pycache__/` and `.DS_Store`, each excluded for a reason stated in
`NOTE.txt`. That is 1852 files, including the 556 KB of gitignored working content
(`docs/`, `eval/`, `dist/`, `.claude/`, `PLAN.md`, `CLAUDE.md`) that earlier
baselines quietly skipped. Coverage was checked two ways rather than claimed: no
file on disk outside those exclusions is missing from `files.txt` (0), and no
git-tracked file is missing from it (0). The tarball was extracted to a scratch
directory and all 1852 hashes re-verified, 0 failed, 0 missing, before editing.
One limitation: `files.txt` was written before the tarball, so the tarball does not
contain `baseline-08/` itself.

| gate | result |
| --- | --- |
| `uv run pytest` | **1049 passed**, 0 failed, 0 errors (`pytest.xml`); 996 before, plus 53 new |
| `ruff check .` | exit 0 |
| `ruff format --check .` | exit 0. Prints "206 files already formatted"; that number is larger than the count of `.py` files on disk, so it is not a file count and what the gate establishes is exit 0 |
| `konpy check` | 112 files, **0 violations**, and `rg 'konpy: ignore' src tests` finds 0 suppressions |
| `verify_cli.py --output …` | **66 passed, 1 failed** — `PROMPTS-filter`, the by-design failure since slice 1 under D-08. **No status change** |
| `verify_prompts.py --output …` | **5 passed, 0 failed** |
| tree integrity vs `baseline-08/sha256.txt` | **1842 OK, 10 changed, 0 missing** — 7 are the slice, 3 are `contracts.md`, `ledger.md` and `tasks.md` written while it ran |
| earlier slices re-measured | **250 captures, 0 changed** |
| SXR-HAZ-01 primer guard | exit 0; a second `init --write` still leaves the file unchanged |

No new failures. The one failure is the pre-existing one and its message is
unchanged. Nothing was skipped or xfailed.

**Not run:** no release, publish, install or push; the installed
`/opt/homebrew/bin/sxr` was never invoked; no real transcript was read or
rewritten; the live corpus was not searched for this slice, because the fixture
needs offset-bearing timestamps that real corpora do not contain.

**Worth stating:** all 996 pre-existing tests passed *before* I wrote a single new
one, on the corrected code. No test anywhere pinned the string ordering or the
sliced display, which is why three defects survived an audit — and the reason to
report the number rather than let it look like confirmation.

## 4. Compatibility, limitations, and one decision

The single-parser claim is provable in one command:
`rg -n fromisoformat src/sxr` returns exactly one line, `util.py:65`.

**Unchanged, measured not assumed.** All 250 captures from the five earlier
harnesses are byte-identical across the change. Those fixtures record `Z`
timestamps, which is what both providers write today, so a real corpus sees no
difference in any of `show`, `prompts`, `errors`, `cmds`, `grep` or the range and
handle views.

**Raw records are intact (D-09).** Of 8 raw `--json` captures, 4 are
byte-identical and 4 are *reordered with an identical record set* — `grep --json`
and `cmds --json`, which visit sessions in scope order. `check_scope_08.py`
compares the sorted line sets to establish that, rather than asserting it.
`show --json` still emits `"timestamp": "2026-09-11T00:30:00+02:00"` verbatim.
The `grep_session` projection (D-12) and `grep_count` are untouched apart from
`grep_count`'s `started` now being the UTC day.

**UTC and local, explicitly.** A timestamp with an offset is converted; a
timestamp with no zone is read as UTC, which is what both providers write and what
`handles._instant` already assumed. Nothing anywhere reads the machine's local
zone. A bare date at a window boundary is midnight UTC, unchanged, and the interval
is still `[since, before)`. What is *corrected* rather than preserved is display:
a displayed `started`, a displayed date and a displayed time of day now name the
moment recorded rather than reprinting its digits with a `Z` appended.

**Scope selection: one shape moves, and it needs your decision.** You asked to be
told if unifying the parser changed scope for an existing valid invocation. It
does, in exactly one shape, and only for a corpus with offset-bearing timestamps:

- Every **literal** bound keeps exactly the sessions it kept before — 7 bound
  shapes including a date, an ISO instant, an offset-bearing instant and both ends
  of a half-open interval, on both providers, checked case by case in
  `scope-report.txt` with failures 0. Window filtering already compared instants,
  so there was nothing to correct and nothing was.
- A bound written **`--since @N`** can keep a different set: `--since @2` kept 4
  and now keeps 2, `--since @3` kept 2 and now keeps 4, `--before @2` kept 0 and
  now keeps 2, identically on both providers. The window did not change and
  `_stamp` did not change; `@2` simply names S3 at 08:00Z instead of S1 at 07:00Z.

Recorded as **open decision 9** with my recommendation to accept, for three
reasons: `@N` is documented as temporary and recomputed per invocation;
`CMD-list-typer`'s own compatibility cell already sanctions renumbering; and the
alternative — resolving `@N` against the old string order for window bounds only —
would make one handle mean two different sessions in a single command line. The
`README.md` migration note states the consequence plainly, including that a
literal bound is unaffected.

**Documentation.** `README.md` gains a timestamp rule under "Rules the output
follows", a sentence in the `--since`/`--before` paragraph with the worked
`00:30+02:00` example, and a migration note under "Status" covering `@N`
renumbering and the `--since @N` consequence. The primer is untouched, so no
version bump is required.

**Limitations.** `find --json`'s `started` stays the verbatim source string:
unlike `list --json` it never appended `Z`, so it never made a false UTC claim,
and changing it would be a schema change to a command whose own rows are not in
this slice. `stats` reports the first and last *records'* instants rather than the
minimum and maximum, which is what it always did, now displayed correctly. Both
are noted in `tasks.md` rather than silently left.

**One correction I made to my own evidence.** The first run of
`check_scope_08.py` reported every Codex scope case as "identical" — because its
session regex assumed an 8-character short id and Codex's are 13, so every Codex
row parsed as empty and passed vacuously. Fixed to match any width, and to return
an unknown id verbatim so a future parsing mistake shows up as a strange key
instead of a silent pass. The Codex numbers in this packet come from the corrected
run. Separately, the first capture fixture gave Codex human turns as
`response_item`/`role: user`, a valid record that yields no session title; the
fixture now uses `event_msg`/`user_message` as every other test in the repo does,
and **both** capture sides were rebuilt with it, the `before` side from the
baseline snapshot via `--source`.

## 5. Ledger state, and the next slice

- `ledger.md`: **D-12** recorded in the resolved table (reviewer, 2026-09-12);
  open decision 8 replaced by a pointer to it; the queue resequencing noted with
  its reason; `SXR-CLI-08` marked delivered; open decision 9 added.
- `contracts.md`: a new "Timestamps" section pinning the single parser, the
  literal-versus-`@N` distinction, and the raw-record exemption; plus the D-12
  paragraph stating that `-l --json`'s projection must not be reverted to raw
  records or given a match count.
- `tasks.md`: the resequencing with its reason, and SXR-CLI-08's delivery, row
  corrections and open clauses.

**Left uncommitted, deliberately.** Slice 6 is also uncommitted, and it touched
`grep_counts.py`, which slice 8 touches too — so a commit of "slice 8's files"
would carry slice 6's changes to that file with it, and the two cannot be
separated at file granularity. Rather than produce a commit whose contents do not
match its message, both slices stay in the working tree and
`slice-08-only.patch` gives you slice 8 in isolation. If you would rather see them
in history, the clean way is a commit for slice 6 and then one for slice 8, in that
order, which I can do on request.

**Next: SXR-CLI-21**, not SXR-CLI-07. I checked rather than assumed, and
SXR-CLI-07 declares `deps: SXR-CLI-06, SXR-CLI-21`; SXR-CLI-21 is still
`proposed`, and two earlier slices explicitly left clauses to it — slice 3's
`PAR-show-typer-line_cap` "same explicit cap policy for all event kinds" and
slice 4's `--line-limit` clause, where `--compact` still uses `middle_trim`'s
fixed widths. So the queue is `21 → 07`, and running 07 first would either
re-open those clauses or close them without their evidence. This also keeps the
one-slice gap between SXR-CLI-06 and SXR-CLI-07 that the resequencing was for,
since SXR-CLI-21 validates and documents the compact-display flags rather than
redefining a documented flag meaning. Confirm or redirect.
