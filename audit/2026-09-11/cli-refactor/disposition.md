# Disposition map: every command-review row to one outcome

Input authority: `audit/2026-09-10/command-review/commands-before-after.csv`
(SHA-256 `c24d00ed08a09caed659c8ab3298db0b2b1166fa97f204742447f3662b1f63e4`, 408 data rows).
Machine-readable sibling: [disposition.json](disposition.json). Task definitions: [tasks.md](tasks.md).

**Completeness check.** The generator parsed the CSV with Python's `csv` module and asserted
that the set of IDs written here equals the set of IDs in the CSV, that the count is exactly 408,
that every `duplicate:` target exists and is not itself a duplicate, and that no ID appears twice.
All assertions passed; `checked_complete` is `true` in the JSON.

## Tallies

| disposition | rows |
|---|---|
| `task` | 138 |
| `duplicate` | 195 |
| `retain` | 37 |
| `deferred` | 35 |
| `decision-needed` | 3 |
| **total** | **408** |

## Rows per task

| task | title | rows |
|---|---|---|
| SXR-CLI-01 | complete human prompts | 7 |
| SXR-CLI-02 | multi-session ranges for show/prompts/tools | 4 |
| SXR-CLI-03 | show selection pipeline | 12 |
| SXR-CLI-04 | errors: source identity and complete text | 4 |
| SXR-CLI-05 | cmds: filter stops changing scope | 4 |
| SXR-CLI-06 | grep/cmds output-mode and raw-JSON contracts | 9 |
| SXR-CLI-07 | grep: result cap separated from character caps | 6 |
| SXR-CLI-08 | UTC instants for every sort and format | 2 |
| SXR-CLI-09 | stats: numeric JSON and session limit unit | 4 |
| SXR-CLI-10 | tools: bounded Skill detail and source identity | 2 |
| SXR-CLI-11 | one physical-file scope for secrets audit/clean/path | 5 |
| SXR-CLI-12 | secrets follow-up commands preserve scope and masking | 4 |
| SXR-CLI-13 | secrets audit documented in help | 2 |
| SXR-CLI-14 | --since/--before after every session command | 14 |
| SXR-CLI-15 | skills honors inherited flags and path projection | 9 |
| SXR-CLI-16 | serve: one parser contract and validated launcher flags | 8 |
| SXR-CLI-17 | find: one contract across both parsers | 8 |
| SXR-CLI-18 | reject options a command cannot use | 11 |
| SXR-CLI-19 | init --check compares block content | 4 |
| SXR-CLI-20 | index --clear reports its exact extent | 3 |
| SXR-CLI-21 | compact-display flags validated and documented | 5 |
| SXR-CLI-22 | help states units, defaults and schemas | 6 |
| SXR-CLI-23 | handles and follow-ups keep the exact source | 2 |
| SXR-CLI-24 | results on stdout, omissions on stderr | 3 |

## Reading the dispositions

- `task:SXR-CLI-NN` — scoped in [tasks.md](tasks.md).
- `retain` — behavior to keep; the note says what is being retained.
- `duplicate:<row>` — same contract as the named row; fix it there once, for every surface.
- `deferred` — real proposal, no approved need yet; the note gives the reason.
- `decision-needed` — changes a documented contract or output schema; the note is the question for a human.

## Command and argument surfaces (38 rows)

One row per parser surface; `sxr find`, `sxr skills` and `sxr serve` appear twice because argparse and Typer both parse them.

| csv_id | disposition | note |
|---|---|---|
| CMD-root-typer | `task:SXR-CLI-18` | root options rejected where meaningless; bare listing kept |
| CMD-list-typer | `task:SXR-CLI-08` | normalize instants before sorting and formatting |
| CMD-show-typer | `task:SXR-CLI-03` | one documented selection pipeline for show; delivered 2026-09-11 |
| PAR-show-typer-arg | `task:SXR-CLI-02` | range clause delivered by SXR-CLI-02; filter-precedence and --tools clauses delivered by SXR-CLI-03 (2026-09-11); row closed |
| CMD-serve-typer | `task:SXR-CLI-16` | one serve parser contract, both entry paths |
| PAR-serve-typer-action | `task:SXR-CLI-16` | shared status/stop choice type |
| CMD-prompts-typer | `task:SXR-CLI-01` | complete human prompts by default |
| PAR-prompts-typer-arg | `task:SXR-CLI-02` | range clause delivered 2026-09-11; --all/budget clauses delivered by SXR-CLI-01 |
| CMD-errors-typer | `task:SXR-CLI-04` | source identity plus complete error text |
| PAR-errors-typer-arg | `task:SXR-CLI-04` | range kept; add source session/sequence per row |
| CMD-tools-typer | `task:SXR-CLI-10` | tool limits cover the Skill-input footer |
| PAR-tools-typer-arg | `task:SXR-CLI-02` | range clause delivered 2026-09-11; the --json -n unit (PAR-tools-typer-limit) and the uncapped `# Skill inputs` line stay open |
| CMD-stats-typer | `task:SXR-CLI-09` | whole-session limit unit and numeric JSON |
| PAR-stats-typer-arg | `task:SXR-CLI-09` | selection kept; limit counts whole sessions |
| CMD-path-typer | `task:SXR-CLI-11` | path shares the audit/clean physical-file scope |
| PAR-path-typer-arg | `retain` | retains range support and deduplicated exact path output |
| CMD-grep-typer | `task:SXR-CLI-07` | independent count and character caps |
| PAR-grep-typer-pattern | `retain` | retains one-pattern grammar and targeted errors |
| PAR-grep-typer-arg | `retain` | retains optional session positional and -e shift |
| CMD-cmds-typer | `task:SXR-CLI-05` | --grep stops changing session scope |
| PAR-cmds-typer-arg | `task:SXR-CLI-05` | newest stays the default with any filter |
| CMD-init-typer | `task:SXR-CLI-19` | content-aware --check and resolved-target reporting |
| PAR-init-typer-file | `retain` | retains explicit target file and AGENTS.md fallback |
| CMD-index-typer | `task:SXR-CLI-20` | clear reports extent; scope combinations rejected |
| CMD-find-typer | `task:SXR-CLI-17` | one find contract across both parsers |
| PAR-find-typer-query | `deferred` | QUERY... positionals are additive; no approved need yet |
| CMD-skills-typer | `duplicate:CMD-skills-argparse` | same skills contract, Typer forwarding path |
| CMD-secrets-typer | `task:SXR-CLI-11` | audit uses the shared physical-file scope |
| CMD-secrets-audit-typer | `task:SXR-CLI-13` | document audit as a first-class action |
| PAR-secrets-audit-typer-arg | `task:SXR-CLI-13` | shorthand kept; selector shown in help |
| CMD-secrets-clean-typer | `task:SXR-CLI-11` | preview/apply scope aligned with audit |
| PAR-secrets-clean-typer-arg | `task:SXR-CLI-11` | one physical expansion for preview and apply |
| CMD-find-argparse | `task:SXR-CLI-17` | argparse find path shares the same contract |
| PAR-find-argparse-query | `deferred` | QUERY... positionals are additive; no approved need yet |
| CMD-skills-argparse | `task:SXR-CLI-15` | inherited flags honored; maintenance combinations validated |
| PAR-skills-argparse-query | `deferred` | multiple clue positionals additive; no approved need yet |
| CMD-serve-argparse | `task:SXR-CLI-16` | argparse serve path shares the same contract |
| PAR-serve-argparse-action | `task:SXR-CLI-16` | same choices in both parsers |

## Shared option families (232 rows)

Fifteen options repeated across up to 16 surfaces. The first row of each family carries the contract; the rest are `duplicate:` of it, and any task fixing the canonical row covers every surface listed here, both Typer and argparse.

| csv_id | disposition | note |
|---|---|---|
| PAR-root-typer-use_codex | `task:SXR-CLI-18` | provider switch rejected where it has no meaning |
| PAR-root-typer-use_claude | `task:SXR-CLI-22` | help must state each command's own provider default |
| PAR-root-typer-path | `task:SXR-CLI-18` | unsupported placement rejected instead of ignored |
| PAR-root-typer-json_out | `task:SXR-CLI-18` | inherited JSON honored or rejected, never ignored |
| PAR-root-typer-limit | `task:SXR-CLI-18` | -n passed only to commands that can use it |
| PAR-root-typer-since | `task:SXR-CLI-14` | same flag after every session command |
| PAR-root-typer-before | `task:SXR-CLI-14` | same flag after every session command |
| PAR-root-typer-file | `task:SXR-CLI-23` | exact file preserved in every generated follow-up |
| PAR-root-typer-recursive | `task:SXR-CLI-18` | irrelevant scope modifiers rejected |
| PAR-root-typer-worktrees | `task:SXR-CLI-18` | irrelevant worktree combinations rejected |
| PAR-root-typer-claude_roots | `retain` | retains repeatable profile roots and provider validation |
| PAR-root-typer-include_agents | `task:SXR-CLI-22` | document per-command child-transcript defaults |
| PAR-root-typer-archives | `task:SXR-CLI-22` | document archive inclusion defaults per command |
| PAR-root-typer-coverage | `task:SXR-CLI-24` | label unavailable roots in stderr diagnostics |
| PAR-root-typer-help | `task:SXR-CLI-22` | -h and --help everywhere; short root help |
| PAR-list-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-list-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-list-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-list-typer-json_out | `task:SXR-CLI-22` | help states this command's exact JSON schema |
| PAR-list-typer-limit | `task:SXR-CLI-24` | list JSON reports omitted session counts |
| PAR-list-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-list-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-list-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-list-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-list-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-list-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-list-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-list-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-list-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-list-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-show-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-show-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-show-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-show-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-show-typer-limit | `task:SXR-CLI-22` | limit unit documented per output format |
| PAR-show-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-show-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-show-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-show-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-show-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-show-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-show-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-show-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-serve-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-prompts-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-prompts-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-prompts-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-prompts-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-prompts-typer-limit | `duplicate:CMD-prompts-typer` | prompts -n/--all precedence owned by that row |
| PAR-prompts-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-prompts-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-prompts-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-prompts-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-prompts-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-prompts-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-prompts-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-prompts-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-errors-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-errors-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-errors-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-errors-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-errors-typer-limit | `task:SXR-CLI-04` | global error cap kept; source identity in text |
| PAR-errors-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-errors-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-errors-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-errors-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-errors-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-errors-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-errors-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-errors-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-tools-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-tools-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-tools-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-tools-typer-json_out | `task:SXR-CLI-10` | tools JSON gains source session identity |
| PAR-tools-typer-limit | `decision-needed` | May -n cap keys inside the tools JSON aggregate, given SXR-AUD-007 keeps all fields? |
| PAR-tools-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-tools-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-tools-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-tools-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-tools-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-tools-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-tools-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-tools-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-stats-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-stats-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-stats-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-stats-typer-json_out | `task:SXR-CLI-09` | numeric counts, byte sizes, real UTC instants |
| PAR-stats-typer-limit | `task:SXR-CLI-09` | one session-summary unit in text and JSON |
| PAR-stats-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-stats-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-stats-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-stats-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-stats-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-stats-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-stats-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-stats-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-path-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-path-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-path-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-path-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-path-typer-limit | `retain` | global cap after path deduplication retained |
| PAR-path-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-path-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-path-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-path-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-path-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-path-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-path-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-path-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-grep-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-grep-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-grep-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-grep-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-grep-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-grep-typer-json_out | `task:SXR-CLI-06` | valid JSON in every mode; raw records deduplicated |
| PAR-grep-typer-limit | `task:SXR-CLI-07` | -n counts results only; --all uncaps output |
| PAR-grep-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-grep-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-grep-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-grep-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-grep-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-grep-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-grep-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-grep-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-cmds-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-cmds-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-cmds-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-cmds-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-cmds-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-cmds-typer-json_out | `task:SXR-CLI-06` | raw call records deduplicated before limits |
| PAR-cmds-typer-limit | `task:SXR-CLI-06` | deduplicate whole records before applying raw JSON limits |
| PAR-cmds-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-cmds-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-cmds-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-cmds-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-cmds-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-cmds-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-cmds-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-cmds-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-init-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-index-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-index-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-index-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-index-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-index-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-index-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-index-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-index-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-index-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-index-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-index-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-index-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-index-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-find-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-find-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-find-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-find-typer-json_out | `retain` | find envelope with coverage and bounded evidence kept |
| PAR-find-typer-limit | `retain` | five ranked sessions and unlimited paths retained |
| PAR-find-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-find-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-find-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-find-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-find-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-find-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-find-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-find-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-find-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-find-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-secrets-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-secrets-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-secrets-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-secrets-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-secrets-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-secrets-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-secrets-typer-limit | `retain` | output-only cap over full-scope tallies retained |
| PAR-secrets-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-secrets-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-secrets-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-secrets-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-secrets-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-secrets-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-secrets-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-secrets-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-secrets-audit-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-secrets-audit-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-secrets-audit-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-secrets-audit-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-secrets-audit-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-secrets-audit-typer-json_out | `duplicate:PAR-list-typer-json_out` | same --json contract as the canonical row |
| PAR-secrets-audit-typer-limit | `retain` | output-only cap over full-scope tallies retained |
| PAR-secrets-audit-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-secrets-audit-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-secrets-audit-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-secrets-audit-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-secrets-audit-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-secrets-audit-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-secrets-audit-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-secrets-audit-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-secrets-clean-typer-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-secrets-clean-typer-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-secrets-clean-typer-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-secrets-clean-typer-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-secrets-clean-typer-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-secrets-clean-typer-json_out | `decision-needed` | May clean --json add a typed operation summary record alongside file results? |
| PAR-secrets-clean-typer-limit | `retain` | display-only report cap retained per SXR-AUD-007 |
| PAR-secrets-clean-typer-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-secrets-clean-typer-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-secrets-clean-typer-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-secrets-clean-typer-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-secrets-clean-typer-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-secrets-clean-typer-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-secrets-clean-typer-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-secrets-clean-typer-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-find-argparse-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-find-argparse-use_codex | `duplicate:PAR-root-typer-use_codex` | same --codex contract as the canonical row |
| PAR-find-argparse-use_claude | `duplicate:PAR-root-typer-use_claude` | same --claude contract as the canonical row |
| PAR-find-argparse-path | `duplicate:PAR-root-typer-path` | same --path contract as the canonical row |
| PAR-find-argparse-json_out | `retain` | same find envelope on the argparse path |
| PAR-find-argparse-limit | `retain` | same find defaults on the argparse path |
| PAR-find-argparse-since | `duplicate:PAR-root-typer-since` | same --since contract as the canonical row |
| PAR-find-argparse-before | `duplicate:PAR-root-typer-before` | same --before contract as the canonical row |
| PAR-find-argparse-file | `duplicate:PAR-root-typer-file` | same --file contract as the canonical row |
| PAR-find-argparse-claude_roots | `duplicate:PAR-root-typer-claude_roots` | same --claude-root contract as the canonical row |
| PAR-find-argparse-recursive | `duplicate:PAR-root-typer-recursive` | same --recursive contract as the canonical row |
| PAR-find-argparse-worktrees | `duplicate:PAR-root-typer-worktrees` | same --worktrees contract as the canonical row |
| PAR-find-argparse-include_agents | `duplicate:PAR-root-typer-include_agents` | same --include-agents contract as the canonical row |
| PAR-find-argparse-archives | `duplicate:PAR-root-typer-archives` | same --archives contract as the canonical row |
| PAR-find-argparse-coverage | `duplicate:PAR-root-typer-coverage` | same --coverage contract as the canonical row |
| PAR-skills-argparse-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |
| PAR-skills-argparse-json | `task:SXR-CLI-15` | inherited root --json honored; paths projected |
| PAR-skills-argparse-limit | `task:SXR-CLI-15` | path mode caps distinct emitted paths |
| PAR-serve-argparse-help | `duplicate:PAR-root-typer-help` | same --help contract as the canonical row |

## Command-local options (56 rows)

Options that exist on one or two surfaces only.

| csv_id | disposition | note |
|---|---|---|
| PAR-root-typer-version | `retain` | root-only --version placement retained |
| PAR-show-typer-around | `task:SXR-CLI-03` | positive coordinate; intersects --type; rejects --range; delivered 2026-09-11 |
| PAR-show-typer-context | `task:SXR-CLI-03` | nonnegative half-width; requires --around; delivered 2026-09-11 |
| PAR-show-typer-range_ | `task:SXR-CLI-03` | ordered positive bounds; intersects --type; A-B alias kept; delivered 2026-09-11 |
| PAR-show-typer-type_ | `task:SXR-CLI-03` | composes with sequence windows and --errors; actionable empty notice; delivered 2026-09-11 (show has no time window) |
| PAR-show-typer-tail | `task:SXR-CLI-03` | unit stated and ordered last; zero/negative preserved; delivered 2026-09-11. Open: JSON tail still counts events, not distinct records |
| PAR-show-typer-thinking | `task:SXR-CLI-03` | inclusion documented under the shared pipeline; delivered 2026-09-11 |
| PAR-show-typer-tools | `task:SXR-CLI-03` | --tool-results primary, --tools alias; delivered 2026-09-11 (moved from deferred: CMD-show-typer carries the same clause) |
| PAR-show-typer-errors | `task:SXR-CLI-03` | error filter applies inside a window and inside --full; delivered 2026-09-11 |
| PAR-show-typer-full | `task:SXR-CLI-03` | explicit filters constrain --full; -n still applies; delivered 2026-09-11 |
| PAR-show-typer-budget | `task:SXR-CLI-21` | compact-display threshold; negatives rejected by SXR-CLI-03 (2026-09-11); the rest stays with SXR-CLI-21 |
| PAR-show-typer-line_cap | `task:SXR-CLI-21` | negatives rejected and 0 = no per-line trim by SXR-CLI-03 (2026-09-11); uniform cap across kinds stays with SXR-CLI-21 |
| PAR-prompts-typer-include_all | `task:SXR-CLI-01` | --all lifts limits, keeps human selection |
| PAR-prompts-typer-budget | `task:SXR-CLI-01` | no implicit budget on the default prompt view |
| PAR-prompts-typer-line_cap | `task:SXR-CLI-01` | cannot silently truncate the default view |
| PAR-grep-typer-count | `task:SXR-CLI-06` | incompatible output-mode flags rejected |
| PAR-grep-typer-fixed | `retain` | literal matching with independent smart-case retained |
| PAR-grep-typer-context | `task:SXR-CLI-06` | nonnegative N; incompatible output modes rejected |
| PAR-grep-typer-ignore_case | `retain` | -i override of smart-case retained |
| PAR-grep-typer-ids_only | `task:SXR-CLI-06` | structured session identity when JSON is requested |
| PAR-grep-typer-expr | `retain` | one -e pattern and leading-dash escape retained |
| PAR-grep-typer-include_all | `task:SXR-CLI-07` | --all becomes uncapped complete output |
| PAR-grep-typer-sort | `task:SXR-CLI-06` | count-mode only, declared choices, instant ordering |
| PAR-grep-typer-after_ctx | `deferred` | asymmetric -A context; targeted error stays for now |
| PAR-grep-typer-before_ctx | `deferred` | asymmetric -B context; targeted error stays for now |
| PAR-grep-typer-budget | `task:SXR-CLI-07` | search budget separated from row cap |
| PAR-cmds-typer-grep_ | `task:SXR-CLI-05` | filter no longer broadens session scope |
| PAR-init-typer-write | `task:SXR-CLI-19` | resolved target reported; idempotent write kept |
| PAR-init-typer-check | `task:SXR-CLI-19` | compare block content, not only version |
| PAR-init-typer-use_global | `task:SXR-CLI-19` | document exact global fallback chain and target |
| PAR-index-typer-clear_ | `task:SXR-CLI-20` | report cleared cache kinds; reject scope flags |
| PAR-find-typer-all_projects | `task:SXR-CLI-18` | incompatible project modifiers rejected |
| PAR-find-typer-any_term | `retain` | OR-across-clues behavior retained |
| PAR-find-typer-index | `task:SXR-CLI-17` | preparation-only without query; search exits unchanged |
| PAR-find-typer-include_current | `retain` | Codex current-session exclusion override retained |
| PAR-find-typer-exclude_sessions | `task:SXR-CLI-17` | unmatched exclusions reported in diagnostics |
| PAR-find-typer-paths_only | `retain` | all-path default and exact projection retained |
| PAR-secrets-typer-candidates | `task:SXR-CLI-12` | reject --candidates when clean is selected |
| PAR-secrets-audit-typer-candidates | `retain` | audit-level candidate inheritance retained |
| PAR-secrets-clean-typer-apply | `task:SXR-CLI-12` | print exact scope-preserving apply command |
| PAR-find-argparse-all_projects | `task:SXR-CLI-18` | incompatible project modifiers rejected |
| PAR-find-argparse-any_term | `retain` | OR-across-clues behavior retained |
| PAR-find-argparse-index | `task:SXR-CLI-17` | same index semantics on the argparse path |
| PAR-find-argparse-paths_only | `retain` | all-path default and exact projection retained |
| PAR-find-argparse-include_current | `retain` | Codex current-session exclusion override retained |
| PAR-find-argparse-exclude_sessions | `task:SXR-CLI-17` | unmatched exclusions reported in diagnostics |
| PAR-skills-argparse-index | `task:SXR-CLI-15` | resolved roots printed with the refresh summary |
| PAR-skills-argparse-root | `task:SXR-CLI-15` | persistent versus transient root use documented |
| PAR-skills-argparse-defaults | `deferred` | --reset-roots alias; no approved need yet |
| PAR-skills-argparse-paths | `task:SXR-CLI-15` | --paths --json projects the same path list |
| PAR-skills-argparse-aliases | `task:SXR-CLI-15` | limits applied after alias expansion in path mode |
| PAR-skills-argparse-copies | `retain` | independent copy and alias controls retained |
| PAR-skills-argparse-exact | `retain` | directory-name exact matching retained |
| PAR-skills-argparse-clear | `task:SXR-CLI-15` | exact cleared extent stated; combinations rejected |
| PAR-serve-argparse-foreground | `task:SXR-CLI-16` | launcher flag validated only in internal launch mode |
| PAR-serve-argparse-idle | `task:SXR-CLI-16` | finite positive timeout; rejected outside foreground |

## Cross-command interactions, actions, environment, work state (39 rows)

The report's analysis rows. These carry most of the real proposals.

| csv_id | disposition | note |
|---|---|---|
| EXTRA-001 | `task:SXR-CLI-18` | placement must not change accepted flags silently |
| EXTRA-002 | `deferred` | cross-command --all rollout; per-command units handled in 01/07/09 |
| EXTRA-003 | `task:SXR-CLI-01` | provenance stays the authority for human prompts |
| EXTRA-004 | `task:SXR-CLI-02` | delivered 2026-09-11; no `resolve(...)[0]` truncation site remains in a view |
| EXTRA-005 | `task:SXR-CLI-23` | list JSON carries handle plus exact file follow-up |
| EXTRA-006 | `task:SXR-CLI-06` | raw JSON deduplicated; help corrected |
| EXTRA-007 | `task:SXR-CLI-06` | grep output-mode combinations validated |
| EXTRA-008 | `task:SXR-CLI-03` | documented window, kind, errors, tail, format order; delivered 2026-09-11 |
| EXTRA-009 | `task:SXR-CLI-21` | central numeric validation for display and window units |
| EXTRA-010 | `task:SXR-CLI-17` | find exit statuses fixed; per-command exits documented |
| EXTRA-011 | `task:SXR-CLI-24` | results on stdout, notices and omissions on stderr |
| EXTRA-012 | `task:SXR-CLI-08` | one timestamp parser for sort, filter, format |
| EXTRA-013 | `deferred` | broad cache restructuring; clear-extent reporting lands in 20 |
| EXTRA-014 | `task:SXR-CLI-11` | one physical-file selection for audit, clean, path |
| EXTRA-015 | `task:SXR-CLI-12` | apply suggestion rebuilt from the resolved selection |
| EXTRA-016 | `task:SXR-CLI-12` | masked follow-ups replace raw secret zoom hints |
| EXTRA-017 | `decision-needed` | May clean --json gain a summary record, and must skipped-live change its exit code? |
| EXTRA-018 | `task:SXR-CLI-18` | abbreviated long options rejected in every parser |
| EXTRA-019 | `retain` | -- terminator and -e retained; documentation only |
| EXTRA-020 | `retain` | verify against the source tree, not the installed binary |
| EXTRA-021 | `task:SXR-CLI-01` | draft prompt tests accounted for in the first slice |
| EXTRA-022 | `task:SXR-CLI-16` | status stays read-only with documented schema and exit 1 |
| EXTRA-023 | `task:SXR-CLI-16` | stop rejects foreground/idle modifiers |
| EXTRA-024 | `retain` | print/write/check spellings kept as flags |
| EXTRA-025 | `task:SXR-CLI-17` | preparation separated from search result status |
| EXTRA-026 | `task:SXR-CLI-20` | clear reports its exact cache extent |
| EXTRA-027 | `task:SXR-CLI-15` | skill refresh/clear extent documented and validated |
| EXTRA-028 | `task:SXR-CLI-21` | SXR_BUDGET validated; implicit prompt trimming removed |
| EXTRA-029 | `task:SXR-CLI-21` | one compact-view cap; complete views independent |
| EXTRA-030 | `deferred` | SXR_NO_CACHE boolean parsing; no approved need yet |
| EXTRA-031 | `deferred` | SXR_NO_DAEMON is launcher-only; documentation deferred |
| EXTRA-032 | `retain` | cache override contract unchanged |
| EXTRA-033 | `retain` | standard XDG cache precedence unchanged |
| EXTRA-034 | `retain` | Claude profile precedence unchanged |
| EXTRA-035 | `retain` | Codex root selection unchanged |
| EXTRA-036 | `retain` | current-session detection ID unchanged |
| EXTRA-037 | `retain` | legacy current-session fallback unchanged |
| EXTRA-038 | `retain` | salt file seam unchanged and never printed |
| EXTRA-039 | `retain` | config/cache separation unchanged |

## Proposed options, not available today (43 rows)

Nothing here exists in the CLI yet, so each is either scoped into a task that needs it or deferred.

| csv_id | disposition | note |
|---|---|---|
| EXTRA-040 | `task:SXR-CLI-01` | --include-context is the explicit context selector |
| EXTRA-041 | `task:SXR-CLI-04` | --compact needed once complete error text is default |
| EXTRA-042 | `deferred` | cmds text completeness not scoped; compact opt-in waits |
| EXTRA-043 | `deferred` | explicit --budget/--line-limit already give compact prompts |
| EXTRA-044 | `task:SXR-CLI-05` | --all-sessions replaces implicit --grep broadening |
| EXTRA-045 | `deferred` | cmds -F literal search; no approved need yet |
| EXTRA-046 | `task:SXR-CLI-07` | --include-zero takes over zero-count row selection |
| EXTRA-047 | `deferred` | --ids alias; no approved need yet |
| EXTRA-048 | `task:SXR-CLI-07` | --full gives complete match text after cap separation |
| EXTRA-049 | `task:SXR-CLI-03` | --tool-results alias; delivered 2026-09-11 alongside PAR-show-typer-tools |
| EXTRA-050 | `deferred` | find --no-agents; no approved need yet |
| EXTRA-051 | `deferred` | find --no-archives; no approved need yet |
| EXTRA-052 | `deferred` | --reset-roots alias; no approved need yet |
| EXTRA-053 | `deferred` | index --json needs a reviewed operation schema first |
| EXTRA-054 | `deferred` | --events-json is a new output schema; design first |
| EXTRA-055 | `deferred` | --events-json is a new output schema; design first |
| EXTRA-056 | `deferred` | --events-json is a new output schema; design first |
| EXTRA-057 | `deferred` | --events-json is a new output schema; design first |
| EXTRA-058 | `deferred` | --events-json is a new output schema; design first |
| EXTRA-059 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-060 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-061 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-062 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-063 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-064 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-065 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-066 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-067 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-068 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-069 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-070 | `deferred` | broad --all rollout; only prompts and grep are scoped |
| EXTRA-071 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-072 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-073 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-074 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-075 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-076 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-077 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-078 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-079 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-080 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-081 | `task:SXR-CLI-14` | expose root --since/--before after the command |
| EXTRA-082 | `task:SXR-CLI-14` | expose root --since/--before after the command |

## Surfaces the CSV cannot contain (added 2026-09-12)

The command review was captured against `48b11c6c`, which is three releases
behind `origin/HEAD`. Six surfaces published in `v0.12.3` through `v0.13.0` have
no row in the 408, so they are recorded in `disposition.json` under
`upstream_rows` rather than in `dispositions`, which still matches the CSV
id-for-id and still passes its completeness assertion.

| id | item | disposition |
|---|---|---|
| `UP-prompts-typer-latest` | `--latest` | `task:SXR-CLI-RECONCILE` — adopted as the explicit spelling of the default |
| `UP-prompts-typer-default-session` | default session choice | `task:SXR-CLI-RECONCILE` — newest session *with human prompts*, skipping empty and background ones |
| `UP-prompts-typer-navigation` | `# prompts:` / `# sessions:` notices | `task:SXR-CLI-RECONCILE` — adopted, pointing at `list` rather than `prompts` |
| `UP-prompts-typer-empty-scope` | no human conversation in scope | `task:SXR-CLI-RECONCILE` — exit 1 naming the scope |
| `UP-prompts-typer-catalog` | bare `prompts` lists sessions | `rejected:D-08` — duplicates `sxr list`; reading stays the default |
| `UP-prompts-typer-catalog-json` | `prompt_session` objects | `rejected:D-09` — raw records remain the `--json` contract |

Six existing rows had their notes corrected rather than their dispositions
changed, because the correction is to the `before` cell: `CMD-prompts-typer`,
`PAR-prompts-typer-arg`, `-json_out`, `-include_all`, `-limit` and `-file` all
describe the audited base and not the published surface. The reasoning is in
`disposition.json` under `verified_against_source["2026-09-12
SXR-CLI-RECONCILE"]`, and measured in
[upstream-reconciliation.md](upstream-reconciliation.md). The CSV itself is not
edited; its SHA-256 is unchanged.

