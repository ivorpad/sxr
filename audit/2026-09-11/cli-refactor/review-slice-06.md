# Review packet — SXR-CLI-06

`grep`/`cmds`: valid JSON in every mode, one record per physical line.
2026-09-12. Starting tree `baseline-06/` at `HEAD` `f42b1ad`; no commit made.

## 1. Task, rows verified against source, and the invocation that shows it

Nine CSV rows: `EXTRA-006`, `EXTRA-007`, `PAR-grep-typer-json_out`,
`PAR-grep-typer-count`, `PAR-grep-typer-ids_only`, `PAR-grep-typer-context`,
`PAR-grep-typer-sort`, `PAR-cmds-typer-json_out`, `PAR-cmds-typer-limit`.

Every `before` clause was checked against current source *and* run before any
code changed. All nine held; none was stale. The clause-by-clause result:

| Clause | Verified how | Verdict |
|---|---|---|
| `-l` is decided before `--json`, so `-l --json` is not JSON | `views_grep._emit` tested `ids_only` first; the run printed `bbbbbbb2` / `aaaaaaa1` | confirmed |
| raw JSON prints one object per matching *event*, repeating a physical record | Claude yields one event per content block sharing the line's `seq`; the run printed the two-block line twice per session | confirmed |
| `-c` silently overrides `-l`, `-C` and `--budget` | `grep_view` returned `_count_view` before reading either; `-c -l`, `-c -C 2` and `-c --budget 10` produced byte-identical count tables | confirmed |
| `--sort` is accepted and ignored outside `-c` | `_order` was only reachable from `_count_view`; `--sort started` and `--sort matches` without `-c` were byte-identical to no flag | confirmed |
| negative `-C` behaves like no context | `opts.context > 0` is false for `-1`; the run also *lost* the `# context inline: -C 3` footer, which `-C 0` keeps, so it was worse than documented | confirmed, with an extra effect the row does not mention |
| `cmds --json` can repeat a physical record | `cmds_view` looped over calls; a line with two `tool_use` blocks printed twice, and `--json -n 2` spent both rows on it | confirmed |

One provider asymmetry the rows do not state, measured here: Codex's parser
yields exactly one event per physical record, so the duplication was reachable on
Claude only. Every Codex raw-JSON capture is byte-identical before and after.

Concrete before/after, `grep -l --json` over two matching sessions:

```
before   $ sxr grep retry -l --json --path /w
         exit=0
         bbbbbbb2
         aaaaaaa1                       # 2 of 2 stdout lines are not JSON

after    $ sxr grep retry -l --json --path /w
         exit=0
         {"type": "grep_session", "session": "bbbbbbb2-0000-4000-8000-00000000000b",
          "provider": "claude", "path": "…/bbbbbbb2-….jsonl"}
         {"type": "grep_session", "session": "aaaaaaa1-0000-4000-8000-00000000000a",
          "provider": "claude", "path": "…/aaaaaaa1-….jsonl"}
```

and `cmds --json -n 2` where one line recorded two tool calls:

```
before   two lines, both the *same* physical record (seq 3)
after    two lines, the two distinct records (seq 3 and seq 5)
```

**Clauses closed:** valid JSON in every mode; raw records deduplicated before
`-n`; `-c` conflicts rejected; `--sort` restricted to `-c` with its choices
stated; `-C` requires N ≥ 0; `--ids` added as an alias; `-l --json` carries the
full id, provider and path so a short-id collision cannot merge two sessions.

**Clauses deliberately left open, unweakened:** `--events-json` (a new surface,
and D-09 says a projection needs its own flag and schema); merging overlapping
`-C` windows; the shared `--json` flag help, which reads "Raw JSONL records,
never truncated" and is inaccurate for `-c`, `-l`, `list`, `stats` and `tools`
alike — correcting it for `grep` alone is not possible, since the flag is shared,
and changing it moves every command's help; the shown/total/omitted notice for
`-n`-bounded JSON, which is `SXR-CLI-20`'s and depends on this slice; and
`--sort started` ordering by UTC instant, which is `SXR-CLI-08`'s.

## 2. The bounded diff

[`slice-06.patch`](slice-06.patch), 934 lines, against `baseline-06/`
(`HEAD` `f42b1ad`, 1434 files, hash-verified and restore-rehearsed before any
edit). Nine files:

| File | Change |
|---|---|
| `src/sxr/views_grep.py` | `_emit` decides `json_out` first; raw hits pass through `output.record_events`; `_session_json` added; the `-c` table and shared diagnostics moved out; 288 → 210 lines |
| `src/sxr/grep_counts.py` | **new**, 117 lines: the `-c` table plus the zero-match and pattern diagnostics both shapes print |
| `src/sxr/grep_options.py` | `GrepOpts.check()` and `.order`; `SORTS` and `METACHARS` rehoused; `sort` defaults to `None`; 27 → 63 lines |
| `src/sxr/views_info.py` | `cmds_view`'s JSON branch uses `print_records` with one scope-wide `RowBudget` |
| `src/sxr/flags.py` | `--ids` alias, `--sort` optional, `-C` help states the domain |
| `src/sxr/cli.py` | `sort` default `None`; `grep` and `cmds` docstrings state the JSON contract |
| `src/sxr/search_index.py` | `METACHARS` imported from its new home |
| `README.md` | the three `--json` shapes, the record unit, and the refusals |
| `tests/test_grep_modes.py` | **new**, 353 lines, 45 cases across both providers |

The module split was forced, not chosen: `views_grep.py` reached 320 lines
against konpy's 300-line limit. No suppression was added. The boundary is the one
the rule's hint suggests — `grep` answers two questions, "which sessions" and
"where", and the count table is the first.

## 3. Source identity and verification

Starting tree `f42b1ad` (`baseline-06/head.txt`), clean; `origin/main` still
`8f93114`; no upstream configured on `main`; 0 stashes. Nothing was committed,
amended or pushed. `uv`'s venv interpreter throughout; the installed
`/opt/homebrew/bin/sxr` was never invoked.

| Check | Baseline | After | Delta |
|---|---|---|---|
| `pytest` | 951 passed, 0 failed | 996 passed, 0 failed | +45, all new |
| `ruff check .` | exit 0 | exit 0 | — |
| `ruff format --check .` | 195 files | 200 files | exit 0 both; see the note below |
| `konpy check` | 109 files, 0 violations | 111 files, 0 violations | +2 modules, no suppressions |
| `verify_cli.py --output …` | 66 passed, `PROMPTS-filter` failed | 66 passed, `PROMPTS-filter` failed | **no status change** |
| `verify_prompts.py --output …` | 5 passed, 0 failed | 5 passed, 0 failed | **no status change** |

`PROMPTS-filter` is the single pre-existing failure, by design since SXR-CLI-01
under D-08. No new failure, and no baseline failure resolved by accident.

The baseline column comes from the `baseline-06/` tree, the format figure by
extracting its snapshot and running ruff inside it. One caveat I would rather
state than paper over: ruff's `N files already formatted` is larger than the
number of `.py` files on disk in the same tree, so I report it as ruff prints it
rather than claiming it is a file count. What the check establishes is exit 0.

**Earlier work preserved, measured not assumed.** The four earlier capture
harnesses re-run against `evidence-B/recaptures/` (the set verified at the
merge): ranges 28/28, show 48/48, errors 38/38, cmds 42/44 byte-identical. The
two differences are `cmds --help` on each provider, and the entire difference is
the two sentences added to the `cmds` docstring. No `cmds` *output* changed:
slice 5's fixture records one tool call per line, so it has nothing to dedup.

Tree integrity against `baseline-06/sha256.txt`: 1427 OK, 7 changed, 0 missing —
the 7 being exactly the edited files. The two new files are absent from that
manifest by construction.

**Not run:** no release, publish, install or bundle step; no push; the Homebrew
formula and every other repository on this machine untouched. The other capture
harnesses for slices not in scope (`prompts`) were not re-run, because
`verify_prompts.py` and the 996-case suite cover that surface and no `prompts`
code path was edited.

## 4. Compatibility, limitations, and the one decision needed

**Breaking, on purpose.** `sxr grep x --sort started` (or `--sort matches`)
without `-c` now exits 2 instead of silently ignoring the flag; `-c -l` and
`-c -C N` now exit 2 instead of printing the count table; `-C -1` now exits 2
instead of behaving like `-C 0`. Anyone whose script passed a flag that never did
anything gets an error where they used to get output. That is the point of the
row, and each message names both flags and says which to drop.

**Changed output shape.** `grep --json` and `cmds --json` print fewer lines
wherever a physical Claude record held more than one matching block or tool call,
and `-n` now counts records. A consumer that counted lines to count *matches* was
already wrong — it double-counted — but it will now see a different number.
Codex output is unaffected.

**`grep -l --json` gained a shape where it had none.** This is the decision I
want confirmed, recorded as open decision 8. `-l` answers "which sessions
matched", which no transcript line records, so there is no raw record to emit and
any fix invents a shape. The one implemented is the smallest honest answer:
`{"type": "grep_session", "session", "provider", "path"}`, typed and named like
`-c`'s existing `grep_count` rows, reusing `list --json`'s `path` key rather than
inventing a fourth spelling, and deliberately *without* a match count so `-l` and
`-c` stay distinguishable. It adds no field a caller could not already get from
`list`. Under D-09 a projection needs its own flag and a documented schema: the
flag already existed, and the schema is now in `README.md` and `grep --help`. If
you read D-09 as demanding a *new* flag even here, the alternative is to make
`-l --json` exit 2 as unsupported — defensible, but it removes a mode rather than
fixing it. Say which and I will change it.

**Not touched, deliberately.** `PRIMER_BODY` still teaches `-l` and says nothing
about `--ids` or the JSON shapes. Adding to it is a change that ships inside
other repositories, D-07 established that such a change needs explicit approval,
and `-l` remains correct, so the primer is unchanged and no version moved. The
shared `--json` flag help is left alone for the reason in section 1.

`disposition.json` is unchanged: it maps rows to tasks, and that mapping did not
change. Delivery and the open clauses are recorded in `tasks.md`, which is where
slices 1 through 5 recorded theirs.

## 5. Ledger state and the next slice

`SXR-CLI-06` is **delivered**, pending review. `SXR-DOCS-01` (the audit-trail
commit) is delivered as `f42b1ad` with finding 6's wording as `b70f3ac`. Open
decision 8 is new and is the only thing in this slice I am asking you to settle.
Decisions 1 through 5 and 7 are unchanged; 6 was answered as D-08.

**Proposed next: `SXR-CLI-07` — grep's result cap separated from its character
caps.** It is the sequence's next step, it depends on this slice (which it names)
and on `SXR-CLI-21`, and it closes the remaining half of the `-n` story: today
`-n 0` lifts the row cap *and* the character budget while the 200-char per-match
flattening still applies, so there is no way to ask for complete match text at
all. It adds `--full`, gives `--budget` an independent meaning, and separates
`--all` from `--include-zero`. It is a bigger behavior change than this slice and
carries a migration note for `-n 0` and `--all`, so it may be worth taking
`SXR-CLI-08` (one timestamp parser, which nothing depends on and which
`--sort started` needs to be correct) first if you would rather not change two
documented flag meanings in consecutive slices.
