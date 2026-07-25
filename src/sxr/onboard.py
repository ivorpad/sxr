"""Onboarding text: the --help epilog and the paste-ready AGENTS.md block."""

EPILOG = """\b
ids: @N from the list; @A:@B names a range; any unique id prefix; a session
name (set via /rename); no id at all means the newest session.
\b
output: tab-separated rows with a # header line; data on stdout, notices on
stderr; exit 0 = content, 1 = empty result, 2 = usage or bad id. --json
emits the original JSONL records, never truncated. ...[+N chars] marks a
display trim; zooms (--around, --range, --type) and --full print whole text.
\b
budgets: scan views (show, prompts) print whole text whenever they fit
--budget chars (default 40k; env SXR_BUDGET); over budget they trim lines
to --line-limit chars (default 200; env SXR_LINE_LIMIT) and say so.
--budget 0 disables trimming entirely.
\b
examples:
  sxr                          sessions for this directory (--codex for Codex)
  sxr grep -c timeout          which sessions mention it, before reading any
  sxr grep "release" @2 -C 3   matches with 3 surrounding events inline
  sxr cmds @2                  every command a session ran, with ok/err
  sxr cmds --grep "git push"   commands that did X, across all sessions
  sxr show @2 --around 1247    untruncated window around event #1247
  sxr show @2 --tail 5         how a session ended, whole text
  sxr prompts                  user messages of the newest session, as stored
  sxr errors @2                is_error records with event indexes
  sxr init >> AGENTS.md        teach agents sxr before their first call
"""

INIT_BLOCK = """## sxr: reading past agent sessions

This machine records every Claude Code and Codex session as JSONL. When you
need to know how something was done before (a release, a fix, a command),
search the history FIRST; it is usually one call:

    sxr                          # sessions for this directory, @N handles
    sxr grep -c "<keyword>"      # which sessions mention it (counts only)
    sxr grep "<keyword>" @N -C 3 # matches with surrounding events inline
    sxr cmds @N                  # every command a session ran, with ok/err
    sxr cmds --grep "<re>"       # commands that did X, across all sessions
    sxr show @N --around <seq>   # untruncated window at one event
    sxr show @N --tail 5         # how a session ended: its final report
    sxr prompts @N               # what the human actually typed
    sxr errors @N                # what failed, structurally flagged
    sxr stats @N                 # counts by record property
    sxr path @N                  # raw JSONL paths, pipe to jq

`--codex` switches provider. Exit codes: 0 content, 1 empty, 2 usage.
`--json` emits raw records, never truncated. Transcripts record ATTEMPTS,
not outcomes: trust the `-> ok/err` markers and verify external state
(git ls-remote, gh, brew) yourself before believing a command worked.
"""
