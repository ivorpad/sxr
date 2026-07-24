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
# or, from PyPI: uv tool install sxr / pipx install sxr / uvx sxr
```

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
sxr show @2 --type ai-title    # select events by record type
sxr prompts                    # user messages of the newest session, as stored
sxr errors @6                  # records flagged is_error, with denial kinds
sxr tools @6                   # per-tool call and failure counts
sxr stats @6                   # counts by record property, tokens, attribution
sxr path @6                    # file paths, pipe straight to jq
sxr grep -c "timeout" @1:@5    # which sessions mention it, before reading any
sxr errors @6 --json | jq .    # the original records, untouched
```

## Rules the output follows

- What is in the JSONL is what comes out. Every filter and count keys off a
  property the record already has (`is_error`, `isMeta`, `toolDenialKind`,
  `payload.type`); nothing classifies or interprets content.
- Truncation happens only in broad scans and is always marked
  (`...[+180 chars]`). Zoomed views (`--around`, `--range`, `--type`) and
  `--json` print everything, whole.
- stdout carries data only; diagnostics go to stderr. Exit codes: 0 with
  content, 1 for an empty result, 2 for usage or a bad id.
- Rows are single-tab-separated with a `#` header line. No color into
  pipes, no wrapping, no pagers, no progress bars.

## Status

0.1.0 covers both providers and all views above. Not built yet: `--since`,
`--all-paths`, the Codex archive and subagent flags, an index cache for the
first-line cwd scan. Session formats drift with CLI releases; the parser is
lenient by design, so unknown record types pass through as their own kind
and never crash a run.

## Development

```bash
uv sync
just check    # ruff format + lint, konpy conventions, pytest
```

MIT license.
