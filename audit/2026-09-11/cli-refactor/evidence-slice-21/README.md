# SXR-CLI-21 evidence — the compact-display caps

Reproduce with the harness in the parent directory; only this README is committed,
because the captures are generated and bulky (see `../../../README.md`).

```
uv run python capture_caps.py --output evidence-slice-21/before --source /tmp/b21
uv run python capture_caps.py --output evidence-slice-21/after
```

`/tmp/b21` is `baseline-21/worktree-snapshot.tar.gz` extracted, with
`fixture_caps.py` and `capture_caps.py` copied in — the baseline tree predates
them, and the harness looks up `util.reset_env_notices` rather than importing it so
the same file runs against both trees.

## Byte-identical index

118 invocations per side: 59 cases across two providers, grouped `flag`, `env`,
`cap`, `bypass`.

| group | cases | byte-identical | changed |
| --- | --- | --- | --- |
| `flag` explicit `--budget`/`--line-limit` values | 30 | 28 | 2 |
| `env` `SXR_BUDGET`/`SXR_LINE_LIMIT`, valid and not | 40 | 22 | 18 |
| `cap` one cap per view | 32 | 19 | 13 |
| `bypass` views documented to ignore the budget | 16 | **16** | **0** |
| total | 118 | 85 | 33 |

`changed.txt` lists the 33 by name. Every one is intended:

* **2 `flag`** — `grep --budget -1` moves from exit 0 to exit 2, on both providers.
  It joins `show --budget`, which D-05 already refused; `--budget 0` still asks
  for all.
* **18 `env`** — 16 add a stderr notice and nothing else; stdout is byte-identical
  in all 16. The other 2 are `SXR_LINE_LIMIT=-5`, where the old reading passed
  `-5` through to `show`'s footer, which printed "trimmed to -5-char lines" and
  then trimmed nothing. It now reports the value and trims at 200.
* **13 `cap`** — every one is a row that previously ignored the cap it was given.
  Measured longest row, before → after: `grep` match rows at cap 60 239 → 166 and
  at 400 239 → 439 (they were 239 at *every* cap before); at cap 0, 239 → 2438
  with no trim marker. Claude `-C` windows at 60 399 → 176. `show
  --tool-results` at 60 399 → 176. `errors --compact` at 60 383 → 160 and at 400
  383 → 703 (383 at every cap before).
* **0 `bypass`** — `--full`, `--around`, `--range`, `--tail`, `--json`, plain
  `prompts` and plain `errors` are unchanged under a 500-char budget.

Two properties hold across all 118 after-captures, checked mechanically rather
than by reading: **zero** notices appear anywhere on stdout, and the ten `--json`
cases all report every stdout line parsing, the same as before.

Default output does not move. `cap-*-grep-rows-default`, `cap-*-cmds-default` and
`cap-*-show-trimmed-default` are byte-identical, because `middle_trim`'s derived
head and tail are exactly its old 200 and 120 at the 200 default.

## Codex reaches the tool-result trim by a different route

`middle_trim`'s `event_line` branch is the `result` event kind, and the Codex
parser emits none — a Codex session of this shape yields `session_meta`,
`user_message`, `text` and `tool` only. So `cap-codex-grep-context-*` is unchanged
while `cap-claude-grep-context-*` is not. Codex does reach `middle_trim` through
`errors --compact`, and `cap-codex-errors-compact-*` changed accordingly. Same
asymmetry the slice-6 dedup finding had, from the other direction.

## Re-measured earlier slices

`recaptures/` re-runs every earlier harness against this tree; `recaptures/pre/`
re-runs three of them against `baseline-21` to attribute each difference.

| slice | harness | files | vs accepted `after/` | caused by this slice |
| --- | --- | --- | --- | --- |
| 02 | `capture_ranges.py` | 28 | 19 differ | **0** — same 19 differ from `baseline-21` too, byte-for-byte |
| 03 | `capture_show.py` | 48 | 0 differ | 0 |
| 04 | `capture_errors.py` | 38 | 0 differ | 0 |
| 05 | `capture_cmds.py` | 44 | 2 differ | **0** — same 2 differ from `baseline-21`; slice 6's `cmds --help` wording |
| 06 | `capture_grep.py` | 92 | 2 differ | **2** — `grep --help` now prints `--budget <int range>  [x>=0]` |
| 08 | `capture_time.py` | 72 | 0 differ | 0 |

Slice 02's 19 are from slices 3 through 8, each accepted with its own evidence at
the time; the set is identical before and after this slice, so nothing here
touched them.

The two oldest harnesses take the output directory as a **positional** argument,
not `--output`. Passing the flag makes them write into a directory literally named
`--output`, and `capture_ranges.py --help` writes into one named `--help`; both
happened here and both were removed. Their recaptures above were re-run with the
positional form, which is why they report a real comparison rather than 0 of 0.
