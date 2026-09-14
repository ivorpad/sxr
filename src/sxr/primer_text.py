"""The two agent-facing documents: the --help epilog and the AGENTS.md primer.

Both are token-budgeted prose that ships to agents, so they live apart from the
install logic in onboard.py that has to reason about replacing them safely.

PRIMER_BODY is rebuilt on the body published as v0.13.0, so a refresh from this
tree never drops guidance an installed primer already carries. Two deliberate
departures from that published text: `cmds` now needs --all-sessions to search
history (SXR-CLI-05), and a bare `prompts` reads rather than lists (D-08).
"""

EPILOG = """\b
ids: @N from the list; @A:@B names a range; any unique id prefix; a session
name (set via /rename); no id at all means the newest session. A range renders
every session it names, each headed by "# session @N <id> <file>" (on stderr
under --json), and -n is one row allowance for the whole range.
\b
output: tab-separated rows with a # header line; data on stdout, notices on
stderr; exit 0 = content (list also succeeds when empty), 1 = empty result,
2 = usage, bad id or an operation failure. --json
emits original JSONL in read views; find emits ranked evidence and coverage. ...[+N chars] marks a
display trim; zooms (--around, --range, --type) and --full print whole text.
\b
budgets: show prints whole text whenever it fits --budget chars (default
40k; env SXR_BUDGET); over budget it trims lines to --line-limit chars
(default 200; env SXR_LINE_LIMIT) and says so. --budget 0 disables trimming;
negative values are a usage error. prompts has no default budget: it prints
complete human input, and only --budget/--line-limit ask for compact text.
grep flattens each match row and stops at --budget chars; --full prints matches
whole under -n, and zero-count -c rows are --include-zero. --all lifts every
limit on any command.
\b
show selection: one order, so no flag discards another -- window (--around
+/- --context, or --range A:B, never both), then kind (--type, else the
skeleton widened by --thinking/--tool-results, else every kind once a window,
--full or --errors asked for more), then --errors, then --tail, then -n. So
--type tool --around 1247 intersects, and --full --errors is every error
record whole. --tools still means --tool-results. Impossible windows exit 2.
\b
errors: one row per distinct failing tool call, naming the session it came
from, so a row from an @A:@B range is zoomable on its own. Text is complete by
default (multi-line errors become an indented block); --compact gives one
trimmed line per error and is the only thing that trims. -n is one allowance
across the range; --json is unchanged either way.
\b
secrets: sxr secrets audits the scope for leaked keys and passwords
(vendored gitleaks rules + structural checks). Rows are kind, severity,
and salted fingerprint; the value itself is never printed, --json included,
because sxr's own output lands in the corpus it audits. sxr secrets clean previews
replacing those values with [sxr:redacted:<kind>:<fp>] markers; only
--apply writes, atomically, skipping (live) sessions and entropy-tier
candidates. Rotation is the fix; cleaning only stops re-propagation.
\b
scope: exact cwd by default; --path resolves relative paths, ~ and symlinks.
--recursive includes descendants; --worktrees includes registered Git worktrees.
Repeat --claude-root for explicit profiles; --include-agents searches Claude
children; --codex --archives includes archives. --coverage shows roots on stderr.
\b
examples:
  sxr                          sessions for this directory (--codex for Codex)
  sxr find "webhook retries"   ranked sessions and evidence, both providers
  sxr skills notify --paths    locate an installed SKILL.md by name
  sxr grep -c timeout          which sessions mention it, before reading any
  sxr grep "release" @2 -C 3   matches with 3 surrounding events inline
  sxr cmds @2                  every command a session ran, with ok/err
  sxr cmds --all-sessions --grep "git push"  commands that did X, whole history
  sxr grep -c x --before today history only: not your own (live) session
  sxr show @2 --around 1247    untruncated window around event #1247
  sxr show @2 --tail 5         how a session ended, whole text
  sxr show @2 --full --errors  every error record, whole text
  sxr prompts                  complete human prompts, newest human session
  sxr errors @2                is_error records, whole text, source on each row
  sxr errors @1:@3 --compact   one trimmed line per error, to scan a range
  sxr init --write             install the primer in the nearest AGENTS.md
  sxr init --check             is the installed primer this version?
"""

PRIMER_BODY = """## sxr: search past agent sessions (Claude Code + Codex)

Before re-deriving a release, fix, decision or command, search session history.
Start with a few distinctive clues. `find` searches Claude and Codex together,
including nested Claude agents and Codex archives, and returns ranked sessions
with source excerpts. Copy a result's exact follow-up command for more context.

```
past decision         sxr find "webhook retries"  # this project's history
project unknown       sxr find "webhook retries" --all-projects
another project       sxr find "webhook retries" --path /repo
structured evidence   sxr find "webhook retries" --json
installed skill       sxr skills notify --paths
exact text counts     sxr grep -c -F "literal"
recorded commands     sxr cmds --all-sessions --grep "git push"
session ending        sxr show @N --tail 5
human requests        sxr prompts @N
recorded failures     sxr errors @N
```

Details that affect retrieval:
- find requires every clue somewhere in a session; --any broadens it. Quote
  phrases inside the query: `sxr find '\"build 19\" CloudKit'`. Matching is by
  case-insensitive words, not regex or literal bytes. It returns 5 sessions
  by default (-n changes this); displayed ranks are not @N session handles.
- find builds its index on first use and refreshes changed files. Prepare it
  ahead of searches with `sxr find --index --all-projects`. An incomplete
  search exits 2; find --json includes complete, coverage and errors. A cached
  search still checks source files. `sxr index --clear` removes session caches.
- skills locates SKILL.md files by directory name or path clues. --paths prints
  one path per distinct SKILL.md content; --copies includes identical copies,
  and --aliases includes symlinks. `sxr skills --index` discovers
  them across your home directory, including hidden folders and repositories.
  Rerun it after installing skills to refresh the JSON map; lookups reuse that
  snapshot. Add --root DIR to choose discovery roots; repeat it for more.
- grep patterns are smart-case regex: lowercase ignores case, capitals match
  exact case. Use -i to ignore case, -F for literal text, -l for matching IDs.
- find skips the invoking Codex session when its ID is in the environment;
  --include-current includes it. For Claude or other sessions, use
  --exclude-session FULL_ID. Other views still include your own commands.
  --before today filters session start dates (UTC), not last activity, so it
  does not exclude a live session resumed from yesterday.
- --path accepts relative paths and ~; symlinks resolve to their physical path.
  Scope is exact by default. --recursive includes descendants; --worktrees
  includes registered Git worktrees. --coverage prints searched/missing roots.
- --claude-root DIR selects a config profile; repeat it to search several.
  find includes children and archives by default; --claude or --codex restricts
  it to one provider. Other commands need --include-agents or --codex --archives.
- Copy the printed zoom command: --file preserves the exact source without
  rediscovery. Read views emit raw JSONL with --json; find emits bounded excerpts.
  Zoom (--around, --range, --type) or --full prints whole text.
- IDs: @N from bare sxr (newest first), @A:@B range, unique ID prefix, or name.
  No ID means newest; prompts reads rather than lists, choosing the newest
  session with human prompts and skipping empty and background ones. --latest
  says that explicitly; bare sxr is the session list. Released 0.13.0 listed
  sessions from a bare prompts instead; that default is reversed here. For an
  origin, `sxr grep -c "x" --sort started` orders oldest recorded mentions
  first; history may predate the corpus.
- -> ok/err/? describes the recorded command outcome. Nonzero exits include
  expected empty grep results. Outer exec success does not prove a nested
  command succeeded. Verify external state when the task depends on it.

Every command takes --help. Exit codes: 0 content (also an empty list),
1 empty result, 2 error.
"""
