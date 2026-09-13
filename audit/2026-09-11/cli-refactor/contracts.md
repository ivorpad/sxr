# Contracts to preserve across this refactor

A task may only break one of these if its own row in `tasks.md` says so
explicitly and names the migration note. Everything else here is a regression.

## Exit codes and limits

- `0` = content (an empty session listing also exits 0, `SXR-AUD-017`),
  `1` = empty result, `2` = usage error / bad id / operation failure.
- `-n 0` means unlimited. Negative row limits are usage errors (exit 2) at root,
  group and command flag positions (`SXR-AUD-012`).
- `--tail 0` selects no events and exits 1; a negative tail is a usage error
  (`SXR-AUD-011`).
- A cleaning row limit changes reporting only, never which files are scanned or
  rewritten (`SXR-AUD-007`, `SXR-AUD-014`).
- **`show` and `prompts` treat a negative `--budget`/`--line-limit`
  differently, on purpose. Do not harmonize them.** `show` rejects a negative
  value with exit 2 (`D-05`, SXR-CLI-03): its budget is a threshold with a
  positive default, and `--budget 0` is the documented way to say "never trim".
  `prompts` accepts a negative value as "no trimming" (`D-02`, SXR-CLI-01): it
  has no default budget, so supplying the flag at all is what requests compact
  text, and `tests/test_prompt_limits.py::test_negative_character_limits_never_truncate`
  pins that. The two commands have had separate option types since SXR-CLI-01
  (`BudgetF`/`LineLimitF` vs `PromptBudgetF`/`PromptLineLimitF`); merging them
  back would silently break one of the two decisions.

## Output shapes

- `--json` in read views emits the original provider JSONL records, complete and
  untruncated.
- `show`, `prompts` and `errors` emit one record per distinct physical source
  line, and a row limit counts distinct physical records. Omission counts go to
  stderr so they never contaminate JSON (`SXR-AUD-005`, `SXR-AUD-006`).
- Physical line numbers survive malformed records: an unparseable JSONL line is
  skipped without renumbering later records, and files are never rewritten
  (`SXR-AUD-015`).
- Aggregate JSON objects keep all their fields even when rows are limited.
- **`grep -l --json` emits a documented projection, not raw records, and that is
  deliberate** (`D-12`, SXR-CLI-06). `-l` answers "which sessions matched", which
  no transcript line records, so there is nothing raw to print. The shape is
  `{"type": "grep_session", "session", "provider", "path"}`, with the full
  session id and the `path` key `list --json` already uses. Two changes are
  regressions, not corrections: reverting it to raw records or to bare ids, which
  D-09 does not require and which made the mode emit non-JSON before; and adding
  a match count, which would make `-l` and `-c` indistinguishable. `-c` keeps its
  own `grep_count` projection. Both are pinned by `tests/test_grep_modes.py`.
- Secret values are never printed, `--json` included; only kind, severity and a
  salted fingerprint.

## Timestamps

- **One reading of a recorded timestamp serves sorting, filtering and display**
  (SXR-CLI-08). `util.instant()` is the only place in `src/sxr` that parses one —
  `rg -n fromisoformat src/sxr` must return exactly one line — and `day`, `clock`,
  `date_of`, `order_key`, `is_live` and `handles._instant` all route through it.
  An offset is applied, not replaced by `Z`; a timestamp with no zone is read as
  UTC, the way both providers record them. Do not reintroduce `ts[:19]`,
  `ts[11:19]`, `ts[:10]`, or a sort keyed on the timestamp string.
- Window filtering compares instants and always did (`SXR-AUD-002`). A literal
  `--since`/`--before` bound keeps exactly the sessions it kept before
  SXR-CLI-08; `evidence-slice-08/scope-report.txt` checks that case by case on
  both providers.
- **A bound written `--since @N` may select a different session than it did
  before SXR-CLI-08, and that is accepted, not a defect** (`D-13`). The corrected
  ordering changes what `@N` names for an offset-bearing corpus, so the bound
  moves with it: measured on both providers, `--since @2` kept 4 of 4 sessions
  and now keeps 2, `--since @3` kept 2 and now keeps 4, `--before @2` kept 0 and
  now keeps 2. Do not "restore" the string ordering, and do not special-case
  `@N` resolution for window bounds so that it follows the old numbering: that
  would let one handle name two different sessions in a single command line. The
  literal case and the `@N` case are separate contracts and a later slice must
  not conflate them — `check_scope_08.py` keeps them apart by construction.
- Raw `--json` keeps each record's own timestamp string verbatim (`D-09`). Only
  derived metadata — `list --json`, `stats`, `grep -c --json` — carries the
  converted instant. `find --json`'s `started` is deliberately still the source
  string: it never appended `Z`, so it never claimed to be UTC.

## Selection

- Provider defaults are unchanged by this refactor: `find` searches both
  providers, every other command defaults to Claude, and `--file` auto-detects.
- `--claude` and `--codex` are mutually exclusive, and root-level and
  command-level shared flags OR-merge to the same result.
- `--file` selection must give byte-identical output to the equivalent
  `--path`-scoped invocation for every session view
  (`tests/test_file_selection.py`).
- `--path` matches the recorded project cwd, resolving relative paths, `~` and
  symlinks; the default scope is one exact directory.
- Human-prompt selection is decided by recorded provenance only. Never infer
  authorship from wording. Unlabelled legacy records stay human
  (`EXTRA-003`).
- **A filter never decides which sessions are read.** Scope comes from the
  selector alone: no selector means the newest session, and `--all-sessions`
  means every session in scope (`D-07`, SXR-CLI-05). `cmds --grep` used to widen
  the scope to the whole project when no selector was given, which also made an
  empty `--since` window exit 1 with a filter and 2 without; both are exit 2 now,
  as everywhere else. `tests/test_cmds_scope.py` pins this on both providers. Do
  not reintroduce a scope decision that reads a filter value in any command.
- A view may disclose that it defaulted its scope, but only when it defaulted:
  a caller who named `@N`, `@A:@B` or `--all-sessions` gets no extra line. That
  boundary is what keeps already-explicit invocations byte-identical, and
  `evidence-05/before-after-index.txt` checks it case by case.

## Structure and process

- `src/**/*.py` at or under 300 lines, `tests/**/*.py` at or under 400 lines.
- Every module, public class and public function in `src/sxr/**` has a
  docstring.
- No `konpy: ignore[...]` suppression may be added. Fix the violation or ask.
- Both dispatch paths stay in step: `find`, `skills` and `serve` have direct
  argparse entry points alongside their Typer commands. Any change to shared
  option or root-flag behavior must be checked on both.
- The 2026-09-10 audit and command-review directories are historical evidence
  and stay byte-identical. New work goes under `audit/2026-09-11/`. One
  reviewer-approved exception exists: `verify_cli.py`'s `--output` was made
  required after its default destroyed a preserved receipt (`D-06`).
- Any audit or evidence script must require an explicit `--output`. A default
  destination inside an evidence directory is how the gap below happened, and a
  temporary-path default would only make a stray run quieter, not safer.
- No publishing, installing, releasing, or rewriting real transcripts.
- **The primer is a distributed artifact and its version stamp is the package
  version.** `onboard.primer()` stamps `sxr.__version__`, so any change to
  `PRIMER_BODY` requires bumping `src/sxr/__init__.py`, `pyproject.toml` and the
  `sxr` entry in `uv.lock` together — `init --check` compares the stamp only,
  never the body, so a reissued primer under an unchanged stamp is reported "up
  to date". Editing the version files in the working tree is not a release;
  `just release` is the reviewer's to run.
- Before choosing a version number, check what is already published. This
  checkout's `pyproject.toml` has been behind origin's tags (`0.12.2` locally
  against `v0.13.0` published), so the next number is not `current + 1`.
- Keep primer edits minimal: it is a token-budgeted agent-facing document that
  other repositories carry verbatim. SXR-CLI-05 changed one line, +15 characters.
- Do not edit any repository outside this one. This repo's own `CLAUDE.md`
  primer block is in scope and is refreshed with `sxr init --write CLAUDE.md`.
