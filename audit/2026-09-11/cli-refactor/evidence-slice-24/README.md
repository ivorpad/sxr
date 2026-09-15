# Evidence, SXR-CLI-24 — results on stdout, omissions and notices on stderr

Captures written by [capture_streams.py](../capture_streams.py) over
[fixture_streams.py](../fixture_streams.py): four sessions per provider, each with
prompts, tool calls, one failure, a Skill input, long text and one Claude physical line
carrying two tool calls. `before/` was produced from the baseline tree restored to
`/tmp/r24` with `--source`, `after/` from this tree, both with explicit `--output`.

    uv run python capture_streams.py --output evidence-slice-24/before --source /tmp/r24
    uv run python capture_streams.py --output evidence-slice-24/after

## Byte-identical index, both providers

| group | claude | codex | what the group asks |
| --- | --- | --- | --- |
| `json` | 15 of 18 | 15 of 18 | is `--json` stdout parseable, and is an omission reported |
| `text` | 12 of 12 | 12 of 12 | human mode must not move |
| `notice` | 9 of 12 | 9 of 12 | does a capped view report itself |
| `coverage` | 4 of 6 | 4 of 6 | `--coverage`, including a path that is not here |
| `keep` | 10 of 10 | 10 of 10 | D-09, D-12, dedup, exit codes, `--help` |
| **total** | **50 of 58** | **50 of 58** | **100 of 116; 16 changed** |

The two providers changed in exactly the same eight places, which is the check that a
provider-specific path was not taken.

## The measurement that matters more than the count

Every capture records stdout and stderr separately, so the two can be compared apart:

- **stdout sections: 116 of 116 byte-identical.** Not one byte of any command's answer
  moved, in either mode, on either provider.
- **exit codes: 116 of 116 identical.**
- All 16 changed captures differ only by an added stderr line, or by the coverage line
  gaining `; path not present on this machine`.

That is the compatibility claim for this slice: a script reading stdout cannot tell the
difference, and a script reading stderr gains information it was not given before.

## The 16 changes, named

Seven per provider are new stderr notices, one per provider is the coverage label:

| capture | before | after |
| --- | --- | --- |
| `json-*-list-limit-1` | omission NOT REPORTED on either stream | `# +3 more sessions (shown 1 of 4; raise -n, -n 0 for all)` |
| `json-*-cmds-limit-1` | omission NOT REPORTED on either stream | `# +2 more records (shown 1 of 3…)` (claude), `+1 more (1 of 2)` (codex) |
| `json-*-cmds-all-sessions` | omission NOT REPORTED on either stream | `# +10 more records (shown 2 of 12…)` (claude), `+6 more (2 of 8)` (codex) |
| `notice-*-list-limit-1-json` | as above | as above |
| `notice-*-cmds-limit-1-json` | as above | as above |
| `notice-*-cmds-grep-json` | scope narrowing said nothing | `# 1 of 4 sessions searched; all of them: --all-sessions` |
| `coverage-*-missing-root` | `# coverage: /w/nowhere (exact cwd); 0 sessions` | `(exact cwd; path not present on this machine)` |
| `coverage-*-missing-root-json` | as above | as above, still on stderr, stdout still empty |

`json-*-cmds-all-sessions` is the loudest of them: an agent asking for two records out
of twelve was told nothing about the other ten.

## Tests shown to fail before they passed

`tests/test_streams.py` has 12 tests. Run against the restored baseline tree with
`PYTHONPATH=/tmp/r24/src` (confirmed importing `/tmp/r24/src/sxr/__init__.py`), **5
fail and 7 pass**:

| test | baseline |
| --- | --- |
| `test_json_stdout_stays_parseable_when_a_cap_reports_itself` | fails |
| `test_list_json_said_nothing_about_three_dropped_sessions` | fails |
| `test_cmds_json_reports_the_records_it_held_back` | fails |
| `test_an_unsearched_scope_is_disclosed_in_both_modes` | fails |
| `test_coverage_says_when_the_named_path_is_not_here` | fails |
| the other 7 | pass |

One failure per defect fixed, and the seven that pass on both trees are the
preservation tests — raw records under D-09, the `grep_session` projection under D-12,
physical line identity, the text footer's stream, exit codes and negative limits. A
preservation test that only passes after the change would not be testing preservation.

## Earlier slices re-measured, and every difference attributed

Nine harnesses re-run against both trees. Two of them take their output directory
positionally, which is the bug found during slice 21; both were driven accordingly.

| harness | identical | attributed |
| --- | --- | --- |
| `capture_caps` (slice 21) | 118 of 118 | — |
| `capture_caps2` (slice 07) | 96 of 96 | — |
| `capture_cmds` (slice 06) | 40 of 44 | 4 to this slice |
| `capture_errors` (slice 04) | 36 of 38 | 2 to this slice |
| `capture_grep` (slice 06/07) | 87 of 92 | 5 to this slice |
| `capture_time` (slice 08) | 72 of 72 | — |
| `capture_ranges` (slice 02) | 28 of 28 | — |
| `capture_show` (slice 03) | 48 of 48 | — |
| `capture_primer_guard` | not run | takes no `--source`, so it cannot address the baseline tree |

Attribution was done by running each harness against the baseline **twice** and
comparing, rather than by assuming: `capture_cmds` 44 of 44, `capture_errors` 38 of 38
and `capture_grep` 92 of 92 are stable across two baseline runs, so no difference is
nondeterminism and all 11 belong to this slice.

Of those 11: nine are the new stderr omission or unsearched-scope notice on
`cmds --json` cases, and two are the coverage label appearing for `/elsewhere`, a
synthetic cwd in slice 4's error fixture that genuinely does not exist on this machine
and whose result is empty — the label doing its job in someone else's fixture. **stdout
is identical in 11 of 11, and so are the exit codes.**

## Gates, in a clean environment

`env | rg '^(CLAUDE_CONFIG_DIR|CODEX_HOME|SXR_)'` returned nothing before these ran.

| gate | result |
| --- | --- |
| `uv run pytest` | 1123 passed |
| `uv run ruff check .` | all checks passed |
| `uv run ruff format --check .` | 221 files already formatted |
| `konpy check` | 115 files, 0 violations, no suppressions |
| `verify_cli.py --output …` | 66 passed, `PROMPTS-filter` the only failure — unchanged |
| `verify_prompts.py --output …` | 5 of 5 |

`views_info.py` is 294 lines against konpy's 300-line limit. It passes, but it is the
tightest module in the tree and the next slice to touch it will have to split it first.

## Baseline

[baseline-24](../baseline-24) holds the tarball, `sha256.txt`, `files.txt`, `head.txt`,
`git-status.txt` and `stashes.txt`, taken at `55ad925` from a clean tree by the same
on-disk enumeration as `baseline-08`, `-21` and `-07`: 4250 paths, of which 3911 are
gitignored working content a git-based enumeration would have missed. Verified two ways
rather than asserted — nothing on disk outside the exclusions is absent from
`files.txt`, and no git-tracked file is absent either. The restore was rehearsed into
`/tmp/r24` before any edit: 4250 of 4250 files verified by hash, 0 bad. That restore is
also what produced `before/`, so the baseline was exercised rather than merely stored.
