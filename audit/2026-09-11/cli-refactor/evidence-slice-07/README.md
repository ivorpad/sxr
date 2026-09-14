# SXR-CLI-07 evidence: which cap stopped the output

`before/` and `after/` hold 96 captures each, 48 per provider, from
`capture_caps2.py` against `fixture_caps2.py`. Every case records its invocation,
exit code, stdout, stderr, and a measured line — rows printed, widest row, whether
a trim marker appeared, how many complete texts survived — because these caps are
visible in counts before they are visible in prose. `--json` cases additionally
record whether every stdout line parses.

The captures in this directory are excluded from git by the `.gitignore` rules
`f42b1ad` added; this index is committed, so a reader sees what was measured without
carrying the dumps. Reproduce with:

    uv run python capture_caps2.py --output evidence-slice-07/after

## Byte-identical index

**38 of 96 byte-identical, 58 changed.** The changes are the point of the slice, so
the useful number is per group:

| group | identical | what the group is for |
| --- | --- | --- |
| `rows` (`-n`) | 10 of 20 | the result cap, including `-n 0`'s changed meaning |
| `chars` (`--budget`) | 8 of 16 | the character stop, and whether `-n 0` still discards it |
| `text` (`--full`) | 0 of 14 | all 14 were exit-2 "No such option: --full" before |
| `all` (`--all`, `--include-zero`) | 4 of 22 | the redefinition and the new flag |
| `keep` (must not move) | 16 of 24 | D-09, D-12, dedup, exit codes, `-C`, `--sort` |

The eight `keep` changes are all documentation of the rename, not behavior: six are
the `-c` footer now advertising `--include-zero` instead of `--all`, and two are
`--help` growing the caps paragraph. Every other `keep` case is byte-identical,
including `json-dedup`, `ids-json` (the `grep_session` projection, D-12),
`count-json`, `context-3`, `ids-plain`, `count-plain`'s data rows, and all three
zero-match cases with their exit codes.

## The five claims, and where each is measured

| claim | before | after | files |
| --- | --- | --- | --- |
| `-n 0` no longer discards an explicit `--budget` | `--budget 400 -n 0` printed **16 data rows**, `--budget 400` printed **1** | both print **1**, and stderr says `-n 0` lifts the result cap only | `chars-*-budget-400-limit-zero` |
| `-n` still lifts the row cap | — | `-n 2` → 2 data rows, `-n 0` → 16 | `rows-*-limit-zero`, `rows-*-limit-2` |
| `--full` prints complete text under `-n` | exit 2, unknown option | `--full -n 5` → **5 rows, 5 complete texts**, widest 765, no trim marker | `text-*-full-limit-5` |
| `--all` is exactly `--full -n 0` | `--all` was byte-identical to no flag | stdout of `--all`, `--full -n 0` and `--full --all` are byte-identical on both providers | `all-*-all`, `text-*-full-limit-zero` |
| `-c --include-zero` prints an all-zero table and exits 1 | `-c --all` on an all-zero scope printed **nothing**, exit 1 | **3 zero rows plus header and footer, exit 1** | `all-*-include-zero-count-allzero` |

The omission clause recovered from `PAR-grep-typer-budget`: `rows-*-limit-2-json`
shows 2 records on stdout with an empty stderr before, and the same 2 records with
`# 16 matches, showing first 2 …` on stderr after (12 on Codex, where one physical
line never holds two blocks). The measured line confirms all
stdout lines still parse as JSON, so D-09 holds.

## Live corpus, not only fixtures

    sxr grep "budget" -n 3 --json   → 3 stdout lines, 0 not JSON;
                                      stderr: "# 39 matches, showing first 3 …"
    sxr grep "zzzznotfoundzzzz" -c --include-zero
                                    → exit 1 with 36 stdout rows

## Earlier slices, re-measured with the corrected harnesses

`recaptures/` runs every earlier harness against this tree. `capture_ranges.py` and
`capture_show.py` take their output directory positionally — the bug found in slice
21 — so they are called that way here.

| slice | accepted `after` vs this tree | attribution |
| --- | --- | --- |
| 02 ranges | 9 of 28 | 19 predate slice 7 (documented under slice 21) |
| 03 show | **48 of 48** | — |
| 04 errors | **38 of 38** | — |
| 05 cmds | 42 of 44 | both predate slice 7 |
| 06 grep JSON | 72 of 92 | 2 predate slice 7; **18 from slice 7** |
| 08 timestamps | 64 of 72 | **8 from slice 7** |
| 21 compact caps | 116 of 118 | **2 from slice 7** |

Attribution is measured, not asserted: `recaptures/pre07/` re-runs the same
harnesses against the restored `baseline-07` tarball (this tree minus slice 7) via
`--source`, so a difference that also appears there predates this slice. All 28
differences attributed to slice 7 are one of three lines — the `-c` footer's flag
name, the capped footer's new hint, or the omission notice appearing on stderr under
`--json`. No data row, count, id, timestamp or exit code moved in any of them.

## Gates

1111 tests passed; ruff check and format clean over 217 files; konpy 114 files with
0 violations and no suppressions. `verify_cli.py` 66 passed with `PROMPTS-filter`
the only failure, and `verify_prompts.py` 5 of 5 — both unchanged, and both run with
an explicit `--output` into `contracts/`. All five `verify_prompts.py` checks matter
here, since `PROMPTS-all-lifts-limits` and `PROMPTS-all-keeps-selection` are the
D-01 behavior `grep --all` was aligned to.

One disclosure about the gate runs: a stale `CLAUDE_CONFIG_DIR=/tmp/sxr-demo02/claude`
and `SXR_CACHE_DIR` were found leaked into the working shell from an earlier
demonstration. Every gate above was re-run after clearing them, and the results are
the post-clearing ones. The captures were never affected — each harness sets its own
provider root and pops `SXR_*` per case.
