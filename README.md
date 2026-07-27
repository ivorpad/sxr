# sxr

Session x-ray: read the sessions Claude Code and Codex leave on disk.

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

Homebrew is the only channel today; a PyPI publish is pending.

## Use

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
sxr prompts                    # user messages of the newest session, as stored
sxr cmds @6                    # every command a session ran, with ok/err
sxr cmds --grep "git push"     # commands that did X, across all sessions
sxr errors @6                  # records flagged is_error, with denial kinds
sxr tools @6                   # per-tool call and failure counts
sxr stats @6                   # counts by record property, tokens, attribution
sxr path @6                    # file paths, pipe straight to jq
sxr grep -c "timeout" @1:@5    # which sessions mention it, before reading any
sxr grep "release" @2 -C 3     # matches with surrounding events inline
sxr errors @6 --json | jq .    # the original records, untouched
sxr init --write               # teach agents sxr before their first call
```

### grep

`grep -c` ranks the scope instead of listing it, and every row carries the
argument for the next call:

```
$ sxr grep -c openclaw
# session	matches	first	started	title
8118457e	234	4	2026-07-20	Openclaw down again
eec026f8	206	16	2026-07-10	Fix opwnclaw crash after self-update
6ba59ad2	54	7	2026-06-26	Debug openclaw and hermes gateway outage
# 22 of 47 sessions match; zoom: sxr show 8118457e --around 4
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
(`grep -c "OpenClaw"` finds 12 sessions where `openclaw` finds 22). `-i`
forces case-insensitive, `-F` matches the pattern literally, `-l` prints only
the ids that match, `-e` spells the pattern for one that starts with a dash.

Match rows are capped at 40k chars (`--budget`, env `SXR_BUDGET`) or at `-n`
rows, whichever comes first; the footer reports the true match count and
`-n 0` prints all of them.

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

The block sits between `<!-- sxr:primer v0.2.3 -->` and `<!-- /sxr:primer -->`
markers stamped with the version that wrote it. `--write` replaces what is
between them and touches nothing else, so re-running after an upgrade is safe
and running it twice leaves the file byte-identical. If the markers are
unbalanced -- one without its pair, or two blocks -- both flags exit 2 and
leave the file alone rather than guess where the block ends. `--check` is the
one to put in a setup script: exit 0 means the installed primer matches the
binary, exit 1 prints which version is stale.

## Rules the output follows

- What is in the JSONL is what comes out. Every filter and count keys off a
  property the record already has (`is_error`, `isMeta`, `toolDenialKind`,
  `payload.type`); nothing classifies or interprets content.
- Truncation happens only in broad scans and is always marked
  (`...[+180 chars]`). Zoomed views (`--around`, `--range`, `--type`) and
  `--json` print everything, whole.
- stdout carries data only; diagnostics go to stderr. Exit codes: 0 with
  content, 1 for an empty result, 2 for usage or a bad id. A bad regex is
  usage (2), never the empty result (1) — a typo must not read as "no hits".
- Rows are single-tab-separated with a `#` header line. No color into
  pipes, no wrapping, no pagers, no progress bars.
- Nothing prints unbounded. `-n` caps rows across the whole scope (not per
  session), `-n 0` lifts the cap, and any view that stopped early says how
  many rows it held back.
- Errors name the flag that fixes them: the candidate list for an ambiguous
  id is capped at 5 short titles, and a wrong flag is answered with the
  right one (`-A 3` → `-C 3`, `sxr grep OVH hostname` → `"OVH.*hostname"`).

## Status

0.2.3 covers both providers and all views above. Not built yet: `--since`,
`--all-paths`, the Codex archive and subagent flags, an index cache for the
first-line cwd scan. Session formats drift with CLI releases; the parser is
lenient by design, so unknown record types pass through as their own kind
and never crash a run.

Breaking since 0.2.3: `grep -c` prints five columns (session, matches, first,
started, title), prunes zero-match rows, and exits 1 when nothing matches.
Parsers of the old two-column TSV need `--json` or `--all`.

## Development

```bash
uv sync
just check    # ruff format + lint, konpy conventions, pytest
```

MIT license.
