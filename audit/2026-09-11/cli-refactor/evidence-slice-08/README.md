# SXR-CLI-08 evidence — one timestamp parser for every sort, filter and format

Everything here was produced by a command that ran; the numbers below are what it
printed. The captures themselves are gitignored, so this file repeats what was
measured. Reproduce with:

```
uv run python capture_time.py --output evidence-slice-08/before --source /tmp/b08
uv run python capture_time.py --output evidence-slice-08/after
uv run python check_scope_08.py --output evidence-slice-08/scope-report.txt
```

where `/tmp/b08` is `baseline-08/worktree-snapshot.tar.gz` extracted. The same
`fixture_time.py` and `capture_time.py` are used on both sides, so the only
variable is the source tree.

## The fixture

Four sessions per provider whose recorded starts sort one way as text and another
as moments:

| key | recorded start | the moment it names |
| --- | --- | --- |
| S1 | `2026-09-10T09:00:00+02:00` | `2026-09-10T07:00:00Z` |
| S2 | `2026-09-10T07:00:00Z` | `2026-09-10T07:00:00Z` (same as S1) |
| S3 | `2026-09-10T08:00:00Z` | `2026-09-10T08:00:00Z` |
| S4 | `2026-09-11T00:30:00+02:00` | `2026-09-10T22:30:00Z` (the previous UTC day) |

## Before and after, 72 captures per side

| group | captures | changed |
| --- | --- | --- |
| order — the listing and the `@N` it decides | 16 | 16 |
| display — headers, columns, derived JSON | 22 | 22 |
| raw — `--json` source records (D-09) | 8 | 4 |
| scope — `--since`/`--before` | 26 | 20 |
| **total** | **72** | **62** |

`changed.txt` names all 62.

## What the changes are, checked mechanically not asserted

`scope-report.txt`, produced by `check_scope_08.py`, reports **failures: 0** for
three claims:

1. **Raw `--json` records are unchanged.** The 4 changed raw captures
   (`grep --json` and `cmds --json`, both providers) are *reordered, same
   records*: the printed line set is equal before and after, and only the order
   sessions are visited in differs, which is the corrected chronology.
   `show --json` and `prompts --json` are byte-identical.
2. **Every literal `--since`/`--before` bound keeps exactly the sessions it kept
   before**, on both providers, across 7 bound shapes including a date, an ISO
   instant, an offset-bearing instant and both ends of a half-open interval.
   Window filtering already compared UTC instants (`SXR-AUD-002`), so this slice
   had nothing to correct there and did not.
3. **A bound written `--since @N` can select a different set, and that is the
   renumbering rather than the window.** `--since @2` kept 4 sessions and now
   keeps 2, `--since @3` kept 2 and now keeps 4, `--before @2` kept 0 and now
   keeps 2 — identically on both providers, because `@2` is now S3 at 08:00Z
   instead of S1 at 07:00Z.

## Acceptance, from the captures

- Ordering: `@1 S4, @2 S3, @3 S2, @4 S1`. S1 and S2 record the same moment and
  are adjacent; both display `2026-09-10T07:00:00Z`. Before: `@1 S4, @2 S1,
  @3 S3, @4 S2`, with S1 shown as `09:00:00Z` and S2 as `07:00:00Z`.
- `grep -c --sort started`: `S2, S1, S3, S4` by instant. Before: `S2, S3, S1, S4`.
- `grep -c`'s date column for S4: `2026-09-10`, the UTC day whose window contains
  it. Before: `2026-09-11`, a day no window would match it under.
- The time-of-day column: S1's `09:05:00+02:00` event prints `07:05:00`. Before:
  `09:05:00`.
- `stats`: `started 2026-09-10T22:30:00Z`. Before: `2026-09-11T00:30:00Z`.
- `show --json` still prints `"timestamp": "2026-09-11T00:30:00+02:00"` verbatim.

## Earlier slices re-measured, not assumed

`recaptures/` runs all five earlier harnesses against the baseline tree and the
working tree with the same fixtures: **250 captures, 0 changed.**

| harness | captures | changed |
| --- | --- | --- |
| `capture_ranges.py` (slices 2–3) | 28 | 0 |
| `capture_show.py` (slices 3–4) | 48 | 0 |
| `capture_errors.py` (slice 4) | 38 | 0 |
| `capture_cmds.py` (slice 5) | 44 | 0 |
| `capture_grep.py` (slice 6) | 92 | 0 |

Those fixtures record `Z` timestamps, which is what both providers write today,
so zero change is the expected result and is what makes the compatibility claim
for real corpora concrete. `primer-guard.txt` re-runs the SXR-HAZ-01 guard: exit
0, and the second `init --write` still leaves the file unchanged.

## Gates

| gate | result |
| --- | --- |
| `pytest` | 1049 passed, 0 failed, 0 errors (`pytest.xml`) |
| `ruff check .` | exit 0, all checks passed |
| `ruff format --check .` | exit 0. Reports "206 files already formatted"; that figure is larger than the count of `.py` files on disk and is not a file count, so what the gate establishes is exit 0 |
| `konpy check` | 112 files, 0 violations, 0 suppressions anywhere in `src/` or `tests/` |
| `verify_cli.py` | 66 passed, 1 failed — `PROMPTS-filter`, by design since slice 1 under D-08. Unchanged |
| `verify_prompts.py` | 5 passed, 0 failed |
| tree integrity vs `baseline-08/sha256.txt` | 1842 OK, 10 changed, 0 missing |

Seven of the ten are the slice itself: `README.md`, `src/sxr/util.py`,
`src/sxr/handles.py`, `src/sxr/claude_discovery.py`, `src/sxr/providers/codex.py`,
`src/sxr/find_service.py` and `src/sxr/grep_counts.py`. The other three are the
records written while the slice ran — `contracts.md`, `ledger.md` and `tasks.md`.
`tests/test_timestamps.py`, `fixture_time.py`, `capture_time.py`,
`check_scope_08.py` and this directory are new, so they have no baseline hash.
Nothing is missing.
