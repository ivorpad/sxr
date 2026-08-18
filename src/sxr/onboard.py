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
emits the original JSONL records, never truncated. ...[+N chars] marks a
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
examples:
  sxr                          sessions for this directory (--codex for Codex)
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

Every session on this machine is recorded as JSONL. Before re-deriving how
something was done (a release, a fix, a config, a command), search history —
it is usually 1-3 calls. Every command takes --help. Exit codes: 0 content,
1 empty result, 2 usage error.

Recipes — the funnel is count -> locate -> zoom:
```
how/where did X happen?    sxr grep -c "x"             # ranked table; `first` column
                                                       #   feeds show --around directly
                           sxr grep "x" @N -C 3        # matches + surrounding events
what command did X?        sxr cmds --grep "git push"  # ALL sessions, one call
how did a session end?     sxr show @N --tail 5        # its final report, whole text
what did the human ask?    sxr prompts @N
what failed?               sxr errors @N
session overview:          sxr stats @N | sxr tools @N
read around event #1247:   sxr show @N --around 1247   # whole text, no trims
another project's history: add --path <dir> to any of the above
```

Sharp edges:
- grep patterns are smart-case regex: all-lowercase matches case-insensitively,
  capitals match exact case (-i forces any-case). Use -F for literal strings
  (error text, paths, URLs); -l prints just the matching session ids.
- `...[+N chars]` marks a display trim, never lost data: zoom (--around,
  --range, --type) or --full prints whole text; --budget 0 disables trimming.
- ids: @N from bare `sxr` (newest first), @A:@B range, unique id prefix, or
  name; no id = newest session. For the ORIGIN of X, `grep -c "x" --sort
  started`: oldest recorded mention first (history may predate the corpus).
- your own running session is in the corpus and matches your own commands:
  rows marked `(live)` are being written now; `--before today` scopes them out.
- --codex switches provider. --json emits raw untruncated JSONL; get file
  paths for jq via `sxr path @N`.
- Transcripts record ATTEMPTS, not outcomes: trust the -> ok/err/? markers
  and verify external state (git ls-remote, gh, brew) before believing a
  command worked.
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
