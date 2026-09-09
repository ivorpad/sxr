# sxr

Session x-ray: find and read past Claude Code and Codex sessions.

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

## Performance

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

In the earlier 0.8.0 benchmark, a different 12-query workload took 1.09 seconds
with sxr versus 14.19 seconds with independent `rg` + JSONL evidence extraction.
Known targets ranked first in 5/5 versus 4/5 cases. Building that index took
**28.35 seconds and 338 MiB**, excluded from both warm-search comparisons.
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

Bundled installs start an owner-only local worker automatically for `sxr find`.
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

Address sessions by `@N` from the list, by any unique id prefix, by name,
or not at all: no id means the newest session. `--codex` switches provider.

```bash
sxr show @2                    # transcript skeleton, one line per event
sxr show @2 --around 1247      # zoom to event #1247, text untruncated
sxr show @2 --tail 5           # how a session ended, whole text
sxr show @2 --type ai-title    # select events by record type
sxr show --file /path/session.jsonl --around 1247 # skip discovery, either provider
sxr prompts                    # user messages of the newest session, as stored
sxr cmds @6                    # every command a session ran, with ok/err
sxr cmds --grep "git push"     # commands that did X, across all sessions
sxr errors @6                  # records flagged is_error, with denial kinds
sxr tools @6                   # per-tool call and failure counts
sxr stats @6                   # counts by record property, tokens, attribution
sxr path @6                    # file paths, pipe straight to jq
sxr grep -c "timeout" @1:@5    # which sessions mention it, before reading any
sxr grep "release" @2 -C 3     # matches with surrounding events inline
sxr grep -c "x" --before today # history only, not your own (live) session
sxr secrets                    # leaked keys/passwords as kind+fingerprint, values never shown
sxr clean                      # preview replacing those with masked markers; --apply writes
sxr errors @6 --json | jq .    # the original records, untouched
sxr init --write               # teach agents sxr before their first call
```

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
forces case-insensitive, `-F` matches the pattern literally, `-l` prints only
the ids that match, `-e` spells the pattern for one that starts with a dash.

Match rows are capped at 40k chars (`--budget`, env `SXR_BUDGET`) or at `-n`
rows, whichever comes first; the footer reports the true match count and
`-n 0` prints all of them.

When the JSONL location is known, `--file` skips session discovery. It detects
Claude or Codex from the records, retains parent-qualified Claude child IDs,
and checks an optional session ID and explicit provider/project/profile flags.
Follow-up commands printed by sxr include the file path automatically, so they
still select the same copy after changing directories. `--file` scopes every
session command to that one file, including `path` and `clean`.

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
`clean --apply` clears the index before and after cleaning. Unavailable, locked
or corrupt caches fall back to direct reads for grep and read views; `find`
reports an error. `index --clear` removes a bad cache.
Indexing requires SQLite 3.43 or newer with FTS5, included by the Homebrew install.

An agent searching history matches its own transcript: the search it just ran
is a record in the session it is running in, so counts drift between two
identical calls and the top-ranked "source" is itself. Sessions written in the
last 10 minutes are marked `(live)` in the title cell of the bare list and the
`-c` table, and `--since DATE` / `--before DATE` filter the scope by session
start (`YYYY-MM-DD`, an ISO datetime, `today`, or `@N` for that session's
start; dates are UTC, the interval is `[since, before)`, so `--before today`
drops everything recorded today). The label is not a filter because it cannot
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
sxr init --check               # exit 1 if the block is missing or a version behind
```

The block sits between `<!-- sxr:primer v0.3.0 -->` and `<!-- /sxr:primer -->`
markers stamped with the version that wrote it. `--write` replaces what is
between them and touches nothing else, so re-running after an upgrade is safe
and running it twice leaves the file byte-identical. If the markers are
unbalanced -- one without its pair, or two blocks -- both flags exit 2 and
leave the file alone rather than guess where the block ends. `--check` is the
one to put in a setup script: exit 0 means the installed primer matches the
binary, exit 1 prints which version is stale.

## Rules the output follows

- Read views preserve JSONL content. Every filter and count keys off a
  property the record already has (`is_error`, `isMeta`, `toolDenialKind`,
  `payload.type`). `find` ranks lexical matches and returns source excerpts;
  it does not generate answers or summaries.
- Truncation happens only in broad scans and is always marked
  (`...[+180 chars]`). Zoomed views (`--around`, `--range`, `--type`) and
  read-view `--json` print everything, whole. `find` always returns bounded excerpts.
- stdout carries data only; diagnostics go to stderr. Exit codes: 0 with
  content, 1 for an empty result, 2 for usage or a bad id. A bad regex is
  usage (2), never the empty result (1) — a typo must not read as "no hits".
- Table rows are tab-separated with a `#` header line; `find` groups evidence
  by session. No color into pipes, no pagers, no progress bars.
- Nothing prints unbounded. `-n` caps rows across the whole scope (not per
  session), `-n 0` lifts the cap, and any view that stopped early says how
  many rows it held back.
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

## Development

```bash
uv sync
just check    # ruff format + lint, konpy conventions, pytest
```

MIT license.
