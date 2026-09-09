"""The --help epilog, the AGENTS.md primer, and the init command that installs it."""

import re
import sys
from pathlib import Path
from typing import Annotated

import typer

from sxr.handles import fail

EPILOG = """\b
ids: @N from the list; @A:@B names a range; any unique id prefix; a session
name (set via /rename); no id at all means the newest session.
\b
output: tab-separated rows with a # header line; data on stdout, notices on
stderr; exit 0 = content, 1 = empty result, 2 = usage or bad id. --json
emits original JSONL in read views; find emits ranked evidence and coverage. ...[+N chars] marks a
display trim; zooms (--around, --range, --type) and --full print whole text.
\b
budgets: scan views (show, prompts) print whole text whenever they fit
--budget chars (default 40k; env SXR_BUDGET); over budget they trim lines
to --line-limit chars (default 200; env SXR_LINE_LIMIT) and say so.
--budget 0 disables trimming entirely.
\b
secrets: sxr secrets audits the scope for leaked keys and passwords
(vendored gitleaks rules + structural checks). Rows are kind, severity,
and salted fingerprint; the value itself is never printed, --json included,
because sxr's own output lands in the corpus it audits. sxr clean previews
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
  sxr cmds --grep "git push"   commands that did X, across all sessions
  sxr grep -c x --before today history only: not your own (live) session
  sxr show @2 --around 1247    untruncated window around event #1247
  sxr show @2 --tail 5         how a session ended, whole text
  sxr prompts                  user messages of the newest session, as stored
  sxr errors @2                is_error records with event indexes
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
recorded commands     sxr cmds --grep "git push"
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
  canonical paths; --aliases includes symlinks. `sxr skills --index` discovers
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
  No ID means newest. For an origin, `sxr grep -c "x" --sort started` orders
  oldest recorded mentions first; history may predate the corpus.
- -> ok/err/? describes the recorded command outcome. Nonzero exits include
  expected empty grep results. Outer exec success does not prove a nested
  command succeeded. Verify external state when the task depends on it.

Every command takes --help. Exit codes: 0 content, 1 empty result, 2 error.
"""

OPEN_RE = re.compile(r"^[ \t]*<!--[ \t]*sxr:primer(?:[ \t]+v(\S+))?[ \t]*-->[ \t]*$", re.M)
CLOSE_RE = re.compile(r"^[ \t]*<!--[ \t]*/sxr:primer[ \t]*-->[ \t]*$", re.M)


class MarkerError(Exception):
    """A file's sxr:primer markers are unbalanced; rewriting it would mangle it."""


def primer(version: str) -> str:
    """The primer block for this version, markers included, newline-terminated."""
    return f"<!-- sxr:primer v{version} -->\n{PRIMER_BODY}<!-- /sxr:primer -->\n"


def find_block(text: str) -> tuple[int, int, str | None] | None:
    """Span and stamped version of the primer block in text; None if absent.

    Raises MarkerError when the markers are unbalanced, duplicated, or out of
    order -- every case where a blind rewrite would eat someone's prose.
    """
    opens, closes = list(OPEN_RE.finditer(text)), list(CLOSE_RE.finditer(text))
    if not opens and not closes:
        return None
    if not closes:
        raise MarkerError("opening <!-- sxr:primer --> marker with no closing <!-- /sxr:primer -->")
    if not opens:
        raise MarkerError("closing <!-- /sxr:primer --> marker with no opening <!-- sxr:primer -->")
    if len(opens) > 1 or len(closes) > 1:
        raise MarkerError(
            f"{len(opens)} opening and {len(closes)} closing sxr:primer markers, expected one each"
        )
    if closes[0].start() < opens[0].end():
        raise MarkerError("closing <!-- /sxr:primer --> marker comes before the opening one")
    end = closes[0].end()
    if text[end : end + 1] == "\n":
        end += 1
    return opens[0].start(), end, opens[0].group(1)


def install_primer(target: Path, version: str) -> str:
    """Insert or replace the primer block in target; returns what it did."""
    block = primer(version)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(block)
        return "created"
    text = target.read_text()
    span = find_block(text)
    if span is None:
        separator = "" if not text else "\n" if text.endswith("\n") else "\n\n"
        target.write_text(text + separator + block)
        return "appended"
    start, end, _ = span
    updated = text[:start] + block + text[end:]
    if updated == text:
        return "unchanged"
    target.write_text(updated)
    return "replaced"


def check_primer(target: Path, version: str) -> tuple[int, str]:
    """Exit code and one-line notice for the primer state of target."""
    if not target.is_file():
        return 1, f"no primer: {target} does not exist; run sxr init --write"
    span = find_block(target.read_text())
    if span is None:
        return 1, f"no sxr primer block in {target}; run sxr init --write"
    installed = span[2]
    if installed != version:
        return 1, (
            f"primer v{installed or '?'} installed in {target}, "
            f"binary is v{version}; run sxr init --write"
        )
    return 0, f"primer v{version} up to date in {target}"


def nearest_agents_md(start: Path) -> Path | None:
    """The nearest AGENTS.md walking up from start; None if the walk hits root."""
    start = start.resolve()
    for directory in (start, *start.parents):
        candidate = directory / "AGENTS.md"
        if candidate.is_file():
            return candidate
    return None


def user_agents_file(home: Path) -> Path:
    """--global target: ~/.agents/AGENTS.md, else ~/.claude/CLAUDE.md, else ~/AGENTS.md."""
    for candidate in (home / ".agents" / "AGENTS.md", home / ".claude" / "CLAUDE.md"):
        if candidate.is_file():
            return candidate
    return home / "AGENTS.md"


FileArg = Annotated[Path | None, typer.Argument(help="Target file; default: nearest AGENTS.md")]
WriteF = Annotated[bool, typer.Option("--write", help="Insert or replace the primer in FILE")]
CheckF = Annotated[bool, typer.Option("--check", help="Is the installed primer this version?")]
GlobalF = Annotated[bool, typer.Option("--global", help="Target the user AGENTS.md/CLAUDE.md")]


def init_cmd(
    file: FileArg = None,
    write: WriteF = False,
    check: CheckF = False,
    use_global: GlobalF = False,
) -> None:
    """Print the primer that teaches agents sxr, or install it in a context file.

    Bare init writes the block to stdout. --write inserts or replaces it
    between <!-- sxr:primer vX.Y.Z --> markers in FILE (default: the nearest
    AGENTS.md walking up from cwd; --global for the user file), so running it
    twice changes nothing. --check exits 1 when the block is missing or
    stamped another version. Unbalanced markers are never rewritten: exit 2.
    """
    from sxr import __version__

    if write and check:
        fail("--write and --check are mutually exclusive")
    if not (write or check):
        if file is not None or use_global:
            fail("FILE and --global need --write or --check")
        print(primer(__version__), end="")
        raise typer.Exit(0)
    if file is not None and use_global:
        fail("--global and an explicit FILE are mutually exclusive")
    raise typer.Exit(_apply(_target(file, use_global, write), write, __version__))


def _target(file: Path | None, use_global: bool, write: bool) -> Path:
    """Resolve the file to write or check; --check with no AGENTS.md exits 1 here."""
    if file is not None:
        return file
    if use_global:
        return user_agents_file(Path.home())
    cwd = Path.cwd()
    found = nearest_agents_md(cwd)
    if found is not None:
        return found
    if write:
        return cwd / "AGENTS.md"
    print(f"no AGENTS.md found above {cwd}; run sxr init --write", file=sys.stderr)
    raise typer.Exit(1)


def _apply(target: Path, write: bool, version: str) -> int:
    """Run --write or --check against a resolved target; marker damage exits 2."""
    try:
        if write:
            print(f"{install_primer(target, version)} primer v{version} in {target}")
            return 0
        code, note = check_primer(target, version)
    except MarkerError as exc:
        fail(f"{target}: {exc}; fix it by hand")
        return 2
    print(note, file=sys.stderr)
    return code
