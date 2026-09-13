# sxr

Session x-ray: find and read past Claude Code and Codex sessions, and locate installed skills.

Both CLIs record everything to JSONL (`~/.claude/projects/`,
`~/.codex/sessions/`), but the files run to megabytes and the interesting
facts (what the human corrected, what broke, which tools failed, what it
cost) are buried in thousands of records. sxr locates the right files for
your current directory, slices them by event index, and counts what you'd
otherwise re-derive by hand. The primary consumer is a coding agent, so
output is tab-separated, deterministic, and cheap; humans get the same
plain text.

## Install

```bash
brew install ivorpad/tap/sxr
```

To update an existing installation, run `brew upgrade sxr`.

Homebrew installs a prebuilt bundle containing Python, SQLite, and the other
runtime libraries. It does not depend on Homebrew's Python or OpenSSL, so a
custom Homebrew prefix does not trigger compilation of that dependency chain.

Without Homebrew, download the matching macOS or Linux archive from
[Releases](https://github.com/ivorpad/sxr/releases), unpack it into a directory
you own, and symlink its `sxr` executable into `~/.local/bin`. Keep the bundle's
files together; the launcher finds its runtime relative to itself. No root
access or existing Python installation is needed. Both arm64 and x86_64 builds
are provided. Bundles are tested on macOS 14/15 and Ubuntu 22.04; Linux builds
use glibc. A PyPI publish is pending.

## Find installed skills

```bash
sxr skills notify --exact --paths  # exact directory name, paths only
sxr skills notify                  # broader matches, with copy counts
sxr skills notify --paths --copies # every matching copy
sxr skills 'project-name:notify' --json
sxr skills --index                 # discover skills and refresh the map
```

Queries match directory names and path clues without regard to case. A query
like `notify` also matches names such as `notify-user`; `--exact` requires the
whole directory name. Path clues select installations before grouping, so
`project-name:notify` restricts results to matching project paths.

Indexing computes SHA-256 from each `SKILL.md`. Identical contents share one
result with a `copies` count; different contents remain separate even when their
directory names match. No pre-existing hash is needed. `--copies` expands the
matching files. JSON groups list those files and their aliases in `locations`.
Symlink aliases do not count as extra copies. Add `--aliases` to `--paths` to
include symlinked paths for the returned files.

The index reports both file counts and distinct instruction contents. These
counts describe instruction files. Supporting scripts and assets are not compared
and can differ between copies with identical `SKILL.md` contents.

`--index` discovers files named `SKILL.md` recursively across your home directory.
The containing directory is the skill; no registry or frontmatter is required.
Repositories, downloads, hidden folders, plugin caches, and dependency directories
are all searched. Configured Claude, Codex, and OpenCode directories outside
your home are included too. Symlinked directories are followed, each physical
directory is scanned once, and cycles are skipped. Only sxr's own cache is excluded.

Choose narrower discovery roots when needed:

```bash
sxr skills --index --root ~/Developer --root ~/.agents
sxr skills notify --exact --paths   # use that map
sxr skills --index --defaults       # restore discovery across your home
sxr skills notify --root ~/Downloads --paths # separate discovery map
```

`--index --root` remembers the chosen roots; repeat `--root` for each location.
A lookup with `--root` uses a separate map. `--root /` searches the filesystem
accessible to your user without requesting root access. Inaccessible directories
make discovery incomplete.

The first lookup builds the map if needed. After installing a new skill, rerun
`sxr skills --index`. Later lookups validate matching files without walking your
home again. Edited files are rehashed before grouping. Reindexing reuses hashes
when file identity, size, permissions, and timestamps are unchanged.

If a recorded path is no longer present during indexing, sxr omits that entry.
Older maps that saved errors for these vanished paths are repaired when loaded,
so an unrelated lookup does not replay those errors. Index maintenance does
not delete, move, edit, or execute skill files.

A matching file or alias that changes after indexing still prompts a reindex.
Permission failures and missing explicit roots remain errors (exit 2). Normal
lookups summarize discovery failures; `sxr skills --index --json` shows the full
diagnostics and coverage.

The map lives at `~/.cache/sxr/skills.json`, respecting `XDG_CACHE_HOME` and
`SXR_CACHE_DIR`, and survives CLI upgrades. Indexing replaces it atomically in
a separate process, allowing lookups to keep using the previous snapshot.
The native bundle reuses its worker for fast lookups.

Text and JSON return 20 results by default; `-n 0` returns all. `--paths` returns
all matching groups unless limited with `-n`. JSON includes `skills`, `total`
results, `unique` contents, matching `files`, `complete`, `errors`, `coverage`,
`indexed_at`, `cycles_skipped`, and the map's `index` path. Copy counts cover
matching files in the snapshot; new installations require reindexing.
`sxr skills --clear` removes the default map and saved roots.
`SXR_NO_CACHE=1` scans without saving a map.

## Performance

### RTK (sxr 0.9.0)

With a prepared index and running search worker, the 0.9.0 release returned
ranked session evidence **3.0× faster than RTK's filename search** and **31×
faster than its displayed matching lines** in a local benchmark.

| 12 queries, sum of per-query medians | Time |
|---|---:|
| sxr find, top five sessions with evidence | **0.255 s** |
| sxr find --paths, all matching source paths | **0.220 s** |
| RTK 0.48.0 rg -l, all matching raw-file paths | 0.763 s |
| RTK 0.48.0 rg -n, compressed matching lines | 7.921 s |

Path-only lookup was **3.5× faster in aggregate**, winning all 12 queries.
Ranked lookup won 11; the common `pnpm` clue took 33.4 ms versus RTK's
24.9 ms filename search. The five clues with identical physical file sets
(including three misses) took 89 ms with sxr paths versus 407 ms with RTK,
a **4.6×** difference.

Measured on 2026-09-09, macOS arm64 and bundled Python 3.13.15, across
**738 transcripts (1.60 GB)**: 606 Codex and 132 Claude files from two profiles,
including children and archives. Seven trials per clue rotated command order,
336 calls total. Process startup and output serialization were included.
The native launcher reused a worker; index preparation and worker startup were
excluded. Every sxr request still checked files for changes. Filesystem caches
were not controlled, and the corpus was hash-verified before timing.
All 12 ranked responses matched the previously source-verified 0.8.1 results
exactly.

These commands do different work: sxr searches decoded event words and phrases;
RTK searches literal JSONL bytes with `-i -F`. Match counts can differ. RTK paths
are unranked; its displayed matches are capped. These numbers measure session
retrieval, not agent reasoning time, and do not establish a winner for every
query. The private transcript corpus is not distributed with this repository.

### rg + JSONL (sxr 0.8.0)

With a prepared index, sxr returned ranked session evidence about **13× faster**
than an independent `rg` + JSONL extraction workflow.

| Measurement | sxr find | rg + JSONL |
|---|---:|---:|
| 12 queries, sum of per-query medians | **1.09 s** | 14.19 s |
| Known historical targets ranked first | **5/5** | 4/5 |

Individual queries were **1.5×–28× faster**. This benchmark used sxr 0.8.0 and
the same 738-file corpus, with a different set of 12 queries from the RTK race.
Seven trials per query alternated command order. Both arms received the same
clues and roots without a known filename or event location, and returned ranked
sessions with bounded excerpts. The baseline used `rg -l -i -F` to locate files,
then decoded JSONL to extract evidence. All returned excerpts were checked
against source records.

Building the index took **28.35 seconds and 338 MiB**, excluded from both
warm-search comparisons.
Including preparation, a single run of those 12 queries was slower than direct
JSONL. Direct reads can also win when the file and location are already known.

## Use

Start with clues when you do not know the session or filename:

```bash
sxr find "webhook retries"                    # this project, both providers
sxr find '"build 19" CloudKit' --all-projects # project unknown
sxr find "release signing" --path ~/src/app --json
sxr find "release signing" --all-projects --paths # every matching source path
```

`find` returns the top five sessions with source excerpts and an exact command
for reading more context. Claude children and Codex archives are included.
All clues must appear somewhere in the same session; `--any` broadens the
search. Quoted phrases must occur within one event. Matching uses words,
ignores case and most Latin diacritics, and treats punctuation as separators.
Use `grep -F` for literal strings in decoded text, or `grep` for regexes and counts.

Results carry provider, full session ID, project, source paths, and physical
JSONL line numbers. Up to three excerpts per result are capped at 600 characters,
with `…` marking a cut. `--json` returns one object containing `results`, `total`,
`complete`, `coverage`, and `errors`. This is bounded evidence, not raw JSONL.
`-n` changes the session limit; `-n 0` returns all. Result ranks are not `@N`
handles: use the printed follow-up command to select the same source.

`--paths` skips ranking and excerpt loading. It prints all matching physical
source paths in sorted order, including duplicate copies; `-n` limits that list.
Its JSON response uses `paths` instead of `results`. Matching, scope, freshness,
and completeness checks are the same as ranked search.

Bundled installs start an owner-only local worker automatically for `sxr find`
and `sxr skills`.
It exits after five idle minutes. `sxr serve status` shows its PID and version;
`sxr serve stop` releases it immediately. Each call forwards its own working
directory, provider roots, and current-session ID. `SXR_NO_DAEMON=1` runs in a
fresh process. Source/Python installs also use the fresh-process path. A worker
that cannot start falls back to normal execution.

The first search builds a local ranked index. Prepare it ahead of an agent's
first lookup with `sxr find --index --all-projects`. Every request checks the
file inventory, reuses unchanged metadata and text, and refreshes changed
transcripts. Warm searches load text only for the displayed results. Missing
roots or files changed during a query make coverage incomplete and exit 2.
A locked or corrupt ranked index reports an error with recovery instructions.
`find` needs its index; `grep` remains available for direct scans.

Use `--claude` or `--codex` to restrict `find` to one provider, and repeat
`--claude-root` for alternate profiles. The other commands below default to
Claude and require explicit flags for child transcripts and archives.

Inside Codex, `find` excludes the invoking session using `CODEX_THREAD_ID`
(or the older `CODEX_SESSION_ID`). This avoids searching the agent's own copied
evidence and rebuilding its growing transcript on every lookup. `--include-current`
includes it; an explicit `--file` also selects it. `--exclude-session FULL_ID`
excludes a session for either provider and can be repeated. Coverage reports
the number of excluded files. No sessions are excluded just because they are live.

```
$ sxr                    # sessions for this directory, newest first
# @   id        started               msgs  errs  tokens  size  title
@1    bbdded20  2026-07-24T17:33:26Z     0     0  0       1k
@2    5592699c  2026-07-24T16:54:43Z    14     0  23k     110k
@6    1b1fbf4d  2026-07-24T15:52:49Z   691    13  690k    2.7M  some-name
```

Address sessions by `@N` from the list, by an inclusive `@A:@B` range, by any
unique id prefix, by name, or not at all: no id means the newest session.
`--codex` switches provider.

A range reads every session it names. Each session's output is preceded by
`# session @N  <id>  <file>` so a block is always attributable — on stdout for
text, on stderr under `--json`, where stdout stays raw JSONL. `-n` is one row
allowance for the whole range, as it already is for `errors`, `cmds` and
`stats`. A range naming one session prints no header and is identical to `@N`.

```bash
sxr show @2                    # transcript skeleton, one line per event
sxr show @2 --around 1247      # zoom to event #1247, text untruncated
sxr show @2 --tail 5           # how a session ended, whole text
sxr show @2 --type ai-title    # select events by record type
sxr show @2 --full --errors    # every error record, whole text
sxr show @2 --type tool --around 1247   # tool calls inside that window
sxr show @1:@3                 # every session in the range, each one headed
sxr show --file /path/session.jsonl --around 1247 # skip discovery, either provider
sxr prompts                    # complete human prompts, newest human session
sxr prompts @2                 # that session's human prompts, however empty
sxr cmds @6                    # every command a session ran, with ok/err
sxr cmds --all-sessions --grep "git push"  # commands that did X, whole history
sxr errors @6                  # is_error records, whole text, each row's session named
sxr errors @1:@3 --compact     # one trimmed line per error, to scan a range first
sxr tools @6                   # per-tool call and failure counts
sxr stats @6                   # counts by record property, tokens, attribution
sxr path @6                    # file paths, pipe straight to jq
sxr grep -c "timeout" @1:@5    # which sessions mention it, before reading any
sxr grep "release" @2 -C 3     # matches with surrounding events inline
sxr grep -c "x" --before today # history only, not your own (live) session
sxr secrets                    # leaked keys/passwords as kind+fingerprint, values never shown
sxr secrets clean              # preview redaction; --apply writes changes
sxr errors @6 --json | jq .    # the original records, untouched
sxr init --write               # teach agents sxr before their first call
```

`show`'s selectors compose in one documented order, so none of them can discard
another: a window first (`--around N` plus or minus `--context`, or `--range
A:B` — never both), then kind (`--type K`, else the default skeleton widened by
`--thinking` and `--tool-results`, else every kind once a window, `--full` or
`--errors` asked for more), then `--errors`, then `--tail N`, then `-n`. So
`--type tool --around 1247` is the tool calls inside that window, and `--full
--errors` is every error record with its text whole. `--tools` is still accepted
as the older spelling of `--tool-results`. Windows that cannot mean anything are
usage errors rather than a quiet empty result: `--around` below 1, a negative
`--context`, `--context` without `--around`, `--range` outside `0 < A <= B`,
`--around` together with `--range`, and a negative `--budget`/`--line-limit`
(`0` remains the explicit "never trim" value). An empty selection still exits 1,
and says on stderr which selectors emptied it.

`errors` prints every record the transcript itself marked as failed, one row per
distinct failing tool call, and each row names the session it came from between
the record number and the clock. That is the token `sxr show` accepts, so a row
found by grep can be zoomed on its own, and two failures at the same record
number in different sessions no longer look alike. Error text prints complete by
default, because the exit status and the assertion are usually at the end: a
one-line error stays on its row, and a multi-line one becomes an indented block
below it so the row itself stays greppable. `--compact` restores one trimmed line
per error for scanning a wide range, and it is the only thing that trims. `-n`
remains one allowance shared by every selected session, and `--json` still emits
the complete original records, `--compact` or not.

`cmds` takes its scope from the selector alone. No selector means the newest
session whether or not `--grep` is present, and `--all-sessions` searches every
session in scope. Until 0.14.0 a nonempty `--grep` with no selector silently
widened the scope to the whole project, so `sxr cmds --grep "git push"` searched
history while `sxr cmds @1 --grep "git push"` searched one session; that is the
behavior `--all-sessions` now names. A filtered view that searched fewer sessions
than the scope holds says so and names the flag, in the empty case on stderr and
otherwise as a `#` note.

`prompts` reads, it does not list. With no selector it reads the newest session
that has human prompts, walking past newer sessions that are empty, subagent
transcripts or automated reviews, and naming its choice on stderr along with the
`sxr list` command that shows what it skipped. `--latest` is that same default
spelled out, for scripts that want to say so; it cannot be combined with an id,
a range or `--file`. An explicit selection is honored exactly as given, including
sessions the default would have walked past, and prints no such notice. `--json`
is always the original records -- selecting a session never turns the output into
a summary of sessions.

`prompts --codex` uses explicit user-message events when present. Otherwise,
it reads user-role text and uses recorded content labels to exclude injected
instructions, environment context and internal reminders. Older transcripts
without those labels retain the user-role text fallback. For Claude, the
default also excludes records marked as metadata or compaction summaries.

Selection and completeness are separate flags. Plain `sxr prompts` prints the
selected human input in full: it has no default character budget, so
`SXR_BUDGET` and `SXR_LINE_LIMIT` cannot trim it. `--budget CHARS` or
`--line-limit CHARS` asks for compact text (`--budget 0` asks for whole text
and wins over `--line-limit`); negative values never truncate. `--all` lifts
every row and character limit, in text and `--json` alike, and overrides an
explicit `-n`/`--budget` supplied at either flag position. `--include-context`
is the flag that widens selection to the other user-role records — injected
instructions, environment context, compaction summaries and tool results —
each labelled with its recorded provenance. Codex compaction boundary records
are never replayed into either view.

Migration, two changes. `--all` used to widen selection to injected context and
tool results; that behavior is now `--include-context`, and `--all` only lifts
limits. And a bare `sxr prompts` reads a session rather than listing human
conversations, which reverses the default of the released 0.13.0 -- the version
Homebrew installs today -- and not merely an internal draft: use `sxr list` for
the catalog of sessions, `sxr prompts` or `sxr prompts --latest` to read the
newest human one, and note that a bare `prompts --json` is now that session's
records rather than session metadata. Anyone scripting against 0.13.0's bare
`prompts` output, or against `-n` counting session rows there, has to change.

`--path` accepts absolute paths, relative paths and `~`. Both the requested
path and the recorded cwd resolve symlinks to their physical path. The default
scope is one exact directory. Broader searches are explicit:

```bash
sxr --path ~/src/tries --recursive grep -c "release"
sxr --path ~/src/project --worktrees list
sxr --claude-root ~/.claude --claude-root ~/.claude-work --coverage list
sxr --include-agents grep -c "child-only evidence"
sxr --codex --archives --coverage grep -c "old failure"
```

These flags work before or after the command. `--recursive` includes descendant
directories, with path boundaries respected. `--worktrees` adds the selected
repository's registered Git worktrees. Without explicit `--claude-root` flags,
`CLAUDE_CONFIG_DIR` selects one profile, defaulting to `~/.claude`; explicit roots
replace that selection. Codex uses `CODEX_HOME`, defaulting to `~/.codex`.
`--coverage` reports searched and unavailable roots on stderr, including when
using `--json`. Empty discovery and searches across multiple roots also report
the roots checked.

Nested Claude sessions have IDs such as `parent-uuid/agent-a1` so reused agent
names stay distinct. Byte-identical copies of one ID are counted once and retain
all source paths in list JSON and coverage diagnostics. Conflicting copies keep
their separate paths and an exact-ID lookup fails with candidates. Codex IDs
identify the actual thread; the parent remains lineage metadata.

Copy generated zoom commands to carry provider, absolute path, profile roots
and discovery flags into the next call, even from another working directory.

### grep

`grep -c` ranks the scope instead of listing it, and every row carries the
argument for the next call:

```
$ sxr grep -c webhook
# session	matches	first	started	title
8118457e	234	4	2026-07-20	Webhook retries dropping events
eec026f8	206	16	2026-07-10	Fix webhok typo in route table
6ba59ad2	54	7	2026-06-26	Debug webhook and queue outage
# 22 of 47 sessions match; zoom: sxr --file /home/me/.claude/projects/-repo/8118457e-1111-2222-3333-444444444444.jsonl show 8118457e-1111-2222-3333-444444444444 --around 4
# oldest first: --sort started; keep zero-match rows: --all
```

`first` is the event index of the first match, so `show <id> --around <first>`
is the immediate next call. Sessions with no matches are pruned (`--all`
restores them) and a scope with zero matches exits 1. `--sort started` orders
oldest first when the question is where something started, not where it is
loudest.

Patterns are smart-case regexes: an all-lowercase pattern matches any case, a
pattern with capitals matches exactly, and the footer says so, because a
capitalised or metacharacter-laden pattern otherwise misses matches silently
(`grep -c "Webhook"` can find 12 sessions where `webhook` finds 22). `-i`
forces case-insensitive, `-F` matches the pattern literally, `--ids` (also `-l`,
`--files-with-matches`) lists the sessions that match rather than the matches,
`-e` spells the pattern for one that starts with a dash.

Match rows are capped at 40k chars (`--budget`, env `SXR_BUDGET`) or at `-n`
rows, whichever comes first; the footer reports the true match count and
`-n 0` prints all of them.

Each of `grep`'s three shapes has its own `--json`, and all three emit JSON.
Plain `--json` prints the matching source records, one per physical JSONL line:
a single line whose content holds two matching blocks is one record, printed
once, and `-n` counts those records. `-c --json` prints one `grep_count` object
per ranked session. `--ids --json` prints one `grep_session` object per matching
session, carrying the full id, the provider and the source `path` under the same
key `sxr list --json` uses for it -- a projection,
not a source record, because "which sessions matched" is not a line the
transcript contains. `sxr cmds --json` follows the same record rule: one line
that recorded two tool calls is one record.

Flags that describe a shape the mode cannot produce are refused rather than
ignored: `-c` with `--ids` or with `-C`, and `--sort` without `-c`, all exit 2
naming both flags, and `-C` requires a count of 0 or more. `--budget` with `-c`
says on stderr that it caps match text the table does not print.

When the JSONL location is known, `--file` skips session discovery. It detects
Claude or Codex from the records, retains parent-qualified Claude child IDs,
and checks an optional session ID and explicit provider/project/profile flags.
Follow-up commands printed by sxr include the file path automatically, so they
still select the same copy after changing directories. `--file` scopes every
session command to that one file, including `path` and `secrets clean`.

The first `show --around`, `--range`, `--type` or `--tail` caches event positions
and annotations for the selected file. Repeated zooms seek to the selected
records, preserving whole-session tool outcomes and the total event count.
Appending a result can change an earlier call's status, so any file change
rebuilds this read cache. For a one-off read that should skip cache construction:

```bash
SXR_NO_CACHE=1 sxr show --file /path/session.jsonl --around 1247
```

Literal searches of at least three characters automatically build a local
search index. This includes plain patterns such as `grep timeout`, `grep -F`
and literal `cmds --grep` searches. The first search pays the indexing cost;
later searches skip unchanged files that cannot match. Short patterns and
regexes with operators use direct reads. Results still come from the JSONL
parser, with the same case rules, counts and event numbers.

```bash
sxr --codex --archives index   # build ahead of the next search, in this scope
sxr index --clear              # discard search and event-position caches
SXR_NO_CACHE=1 sxr grep timeout # bypass the index
```

Search, ranked retrieval, and read caches share
`$XDG_CACHE_HOME/sxr/search.sqlite3`, defaulting to
`~/.cache/sxr/search.sqlite3`; `SXR_CACHE_DIR` chooses another directory.
It contains derived transcript data and is created with owner-only access.
Verified appends index new records; edits, replacements and truncations rebuild
the affected file. An incomplete final line is revisited when more bytes arrive.
`secrets clean --apply` clears the index before and after cleaning. Unavailable, locked
or corrupt caches fall back to direct reads for grep and read views; `find`
reports an error. `index --clear` removes a bad cache.
Indexing requires SQLite 3.43 or newer with FTS5, included by the Homebrew install.

`sxr secrets` audits the selected sessions and prints masked fingerprints.
`sxr secrets clean` previews redaction; add `--apply` to replace the files.
The former top-level `sxr clean` command has moved under `secrets`. Both commands
default to Claude sessions in the current project. Use `--codex` for Codex,
repeat `--claude-root` for multiple Claude profiles, or use `--file` for one file.

Auditing and cleaning detect credentials in decoded JSON string values, including escaped
text, serialized JSON, multiline private keys and structured password fields. It preserves
property names, unrelated values, untouched lines and line endings. Invalid
UTF-8 or JSON lines remain unchanged. Only certain/probable findings are
redacted; entropy-only candidates remain review material. Unsupported bundled
rules stop the scan with an error instead of silently reducing coverage.

Each run scans the selected files. Activity checks read timestamps from the
end of each file, and files without findings need no temporary copy. Cleaning
includes selected duplicate copies and Claude children, checks each file for
recent activity, and skips sessions with a timestamp within ten minutes of now.
An explicit `--file` includes no copies or children. Changed files are replaced
atomically after checking their identity, size and timestamps; no backup is kept.
These checks cannot exclude a write between the final check and replacement,
so run `--apply` after the selected sessions have stopped. File errors return
exit 2. Redaction removes local occurrences, but does not revoke credentials.

`secrets -n 1` shows one fingerprint and reports the full finding count.
`secrets clean -n 1` limits printed file rows; it still scans or cleans every file
in the selected scope. Clean `--json` emits one masked result per changed file,
with `applied` distinguishing preview from writes. Totals and omissions go to stderr.
`path --json` emits objects containing `type` and `path`.

An agent searching history matches its own transcript: the search it just ran
is a record in the session it is running in, so counts drift between two
identical calls and the top-ranked "source" is itself. Sessions written in the
last 10 minutes are marked `(live)` in the title cell of the bare list and the
`-c` table, and `--since DATE` / `--before DATE` filter the scope by session
start (`YYYY-MM-DD`, an ISO datetime, `today`, or `@N` for that session's
start; dates are UTC, the interval is `[since, before)`, so `--before today`
drops everything recorded today). Every displayed timestamp is UTC too, and is
the moment the record names rather than its digits: a session recorded at
`2026-09-11T00:30:00+02:00` is listed as `2026-09-10T22:30:00Z` and is inside
the window `--since 2026-09-10 --before 2026-09-11`, not the next day's. Two
sessions recording the same moment in different offsets show the same `started`
and sort adjacently. The label is not a filter because it cannot
be: a teammate's concurrent session looks exactly like your own, and dropping
it silently would be worse than showing it.

```
$ sxr grep -c "live session" --path ~/src/sxr
# session	matches	first	started	title
d2e9fcb0	2	39	2026-07-27	(live) implement the (live) label and --since/--bef
31e98111	1	9	2026-07-27	implement the bounded grep output
# 3 of 24 sessions match; zoom: sxr --file /home/me/.claude/projects/-home-me-src-sxr/d2e9fcb0-1111-2222-3333-444444444444.jsonl show d2e9fcb0-1111-2222-3333-444444444444 --around 39
# (live) = written in the last 10 min, your own session included; scope it out with --before today
```

## Teaching an agent to use it

An agent that has never heard of sxr will not run it, so the primer belongs
in a file the agent already reads. `sxr init` prints that primer; `sxr init
--write` installs it:

```bash
sxr init --write               # nearest AGENTS.md walking up from cwd
sxr init --write --global      # ~/.agents/AGENTS.md, ~/.claude/CLAUDE.md, or ~/AGENTS.md
sxr init --write CLAUDE.md     # any file you name
sxr init --check               # exit 1 if the block is missing, stale or reissued
sxr init --write --force       # overwrite even if guidance would be lost
```

The block sits between `<!-- sxr:primer v0.3.0 -->` and `<!-- /sxr:primer -->`
markers stamped with the version that wrote it. `--write` replaces what is
between them and touches nothing else, so re-running after an upgrade is safe
and running it twice leaves the file byte-identical. If the markers are
unbalanced -- one without its pair, or two blocks -- both flags exit 2 and
leave the file alone rather than guess where the block ends. `--check` is the
one to put in a setup script: exit 0 means the installed primer matches the
binary, exit 1 prints why it does not: missing, stamped another version, or
stamped this one over a different body.

The primer lives in someone else's repository, so a write that would leave the
reader worse informed is refused rather than performed. Before replacing an
installed block, `--write` compares what the two bodies document -- long flags
and subcommand names -- and exits 2 without touching the file if the installed
one covers anything this binary's primer does not mention, or if its stamp
names a later release. `--check` reports the same condition and does not
suggest a write. Rewording is not a loss and passes, since only flags and
commands are compared. `--force` overwrites deliberately, still replacing only
what is between the markers. Two independent checks are used because a version
stamp alone can be wrong: a build made from a checkout that predates a release
can carry both a higher stamp and older guidance, and that is exactly the case
that used to destroy content silently.

## Rules the output follows

- Read views preserve JSONL content. Every filter and count keys off a
  property the record already has (`is_error`, `isMeta`, `toolDenialKind`,
  `payload.type`). `find` ranks lexical matches and returns source excerpts;
  it does not generate answers or summaries.
- Truncation happens only in broad scans and is always marked
  (`...[+180 chars]`). Zoomed views (`--around`, `--range`, `--type`) and
  `--full`, `--tail` and read-view `--json` keep returned text whole. Row limits
  still apply. `find` always returns bounded excerpts.
- Exit codes: 0 with content, 1 for an empty result, 2 for usage, a bad id or
  an operation failure. Listing is the exception: bare `sxr` and `sxr list`
  return 0 even when the scope is empty, in text and JSON modes. A bad regex
  returns 2. JSON stdout contains data only; diagnostics go to stderr.
- Table rows are tab-separated with a `#` header line; `find` groups evidence
  by session. No color into pipes, no pagers, no progress bars.
- Nothing prints unbounded. `-n` caps rows across the whole scope (not per
  session), `-n 0` lifts the cap, and any view that stopped early says how
  many rows it held back. Negative limits return 2. JSON read views count
  physical records, keeping every field of each returned record. Tools JSON
  is one complete aggregate; stats JSON has one complete object per session.
  `--tail 0` selects no events and returns 1; negative tails return 2.
- One timestamp reading serves sorting, filtering and display. A recorded
  timestamp is converted to its UTC instant, not sliced: an offset is applied
  rather than replaced by `Z`, and a timestamp with no zone is read as UTC, the
  way both providers record them. Ordering compares instants, so `@N`, the bare
  list, `find`'s ranking and `grep -c --sort started` agree with each other and
  with `--since`/`--before`. Raw `--json` still emits the source record verbatim,
  its own timestamp string included; only derived metadata such as `list --json`
  carries the converted instant.
- Errors name the flag that fixes them: the candidate list for an ambiguous
  id is capped at 5 short titles, and a wrong flag is answered with the
  right one (`-A 3` → `-C 3`, `sxr grep webhook retries` → `"webhook.*retries"`).

## Status

Both providers support the views above. Codex completed command items retain
command text, output, status, exit code and original JSONL line numbers. `cmds`
shows the command; `grep` and `errors` also search or display its output. Stable
item IDs remove repeated representations without merging separate executions.
A nonzero exit is a recorded outcome, including expected empty grep results.

The search index narrows candidate files. Cached zooms read selected source
records and restore their canonical annotations. Unknown record types pass
through as their own kind.

Breaking since 0.2.3: `grep -c` prints five columns (session, matches, first,
started, title), prunes zero-match rows, and exits 1 when nothing matches.
Parsers of the old two-column TSV need `--json` or `--all`.

Timestamps are now read as instants everywhere, which corrects chronology for a
corpus containing offset-bearing timestamps and therefore changes what `@N`
names in one: a session recorded at `09:00+02:00` used to sort after one
recorded at `08:00Z`, though it happened an hour earlier. `@N` was always
documented as temporary and recomputed per invocation, so this is a correction
rather than a break, but two consequences are worth stating. A displayed
`started` can move by the recorded offset, and a bound written as `--since @2`
can select a different session than before, so it may keep a different set;
a literal bound such as `--since 2026-09-10` keeps exactly the sessions it
always did, because window filtering already compared instants. Corpora
recording only `Z` timestamps, which is what both providers write today, are
unaffected in every respect.

## Development

```bash
uv sync
just check    # ruff format + lint, konpy conventions, pytest
```

MIT license.
