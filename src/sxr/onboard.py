"""Installing the AGENTS.md primer, and refusing writes that would lose guidance.

The primer ships inside other repositories, so a rewrite from here can destroy
guidance that a newer sxr installed. Every write is checked for that first; the
text itself lives in primer_text.py.
"""

import re
import sys
from pathlib import Path
from typing import Annotated

import typer

from sxr.handles import fail
from sxr.primer_text import EPILOG, PRIMER_BODY

__all__ = ["EPILOG", "PRIMER_BODY", "init_cmd"]

OPEN_RE = re.compile(r"^[ \t]*<!--[ \t]*sxr:primer(?:[ \t]+v(\S+))?[ \t]*-->[ \t]*$", re.M)
CLOSE_RE = re.compile(r"^[ \t]*<!--[ \t]*/sxr:primer[ \t]*-->[ \t]*$", re.M)


VERBS = (
    "cmds",
    "errors",
    "find",
    "grep",
    "index",
    "init",
    "list",
    "path",
    "prompts",
    "secrets",
    "serve",
    "show",
    "skills",
    "stats",
    "tools",
)


class MarkerError(Exception):
    """A file's sxr:primer markers are unbalanced; rewriting it would mangle it."""


class DowngradeError(Exception):
    """Replacing an installed primer would drop guidance it already carries."""


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


def block_body(text: str, span: tuple[int, int, str | None]) -> str:
    """The installed primer's own text, marker lines and blank edges removed."""
    lines = text[span[0] : span[1]].splitlines()
    kept = [line for line in lines if not OPEN_RE.match(line) and not CLOSE_RE.match(line)]
    return "\n".join(kept).strip("\n") + "\n"


def surfaces(body: str) -> set[str]:
    """The command surfaces a primer body documents, as comparable tokens.

    Long flags and this tool's own subcommand names, and nothing else. Prose
    wording is deliberately excluded: rewording a paragraph is a normal part of
    a release, while dropping a flag or a command means the guidance no longer
    covers something the reader can still type.
    """
    flags = set(re.findall(r"--[a-z][a-z0-9-]+", body))
    verbs = {f"sxr {verb}" for verb in re.findall(r"\bsxr ([a-z][a-z-]+)", body) if verb in VERBS}
    return flags | verbs


def release(stamp: str | None) -> tuple[int, ...] | None:
    """A dotted numeric version as a comparable tuple; None when unparseable."""
    if not stamp:
        return None
    parts = stamp.split(".")
    if not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def write_hazard(installed_body: str, stamp: str | None, version: str) -> str | None:
    """Why replacing this installed primer would lose information, else None.

    Two independent reasons, because a version stamp alone cannot be trusted:
    the stamp may name a later release than this binary, or the installed body
    may document surfaces this binary's body does not mention at all. The second
    catches a fork, where the stamps are ordered but the content is not.
    """
    installed, mine = release(stamp), release(version)
    if installed is not None and mine is not None and installed > mine:
        return f"the installed primer is v{stamp}, newer than this binary's v{version}"
    dropped = sorted(surfaces(installed_body) - surfaces(PRIMER_BODY))
    if dropped:
        return "this binary's primer does not mention " + ", ".join(dropped)
    return None


def install_primer(target: Path, version: str, force: bool = False) -> str:
    """Insert or replace the primer block in target; returns what it did.

    Raises DowngradeError when replacing the installed block would drop guidance
    it carries, unless force is set. Creating and appending cannot lose anything,
    so neither is gated.
    """
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
    hazard = None if force else write_hazard(block_body(text, span), span[2], version)
    if hazard is not None:
        raise DowngradeError(hazard)
    target.write_text(updated)
    return "replaced"


def check_primer(target: Path, version: str) -> tuple[int, str]:
    """Exit code and one-line notice for the primer state of target.

    Never recommends a write that would lose guidance. The body is compared as
    well as the stamp, so a block reissued under an unchanged version is not
    reported as up to date.
    """
    if not target.exists():
        return 1, f"no primer: {target} does not exist; run sxr init --write"
    text = target.read_text()
    span = find_block(text)
    if span is None:
        return 1, f"no sxr primer block in {target}; run sxr init --write"
    installed, body = span[2], block_body(text, span)
    hazard = write_hazard(body, installed, version)
    if hazard is not None:
        return 1, (
            f"primer v{installed or '?'} in {target} is not this binary's v{version}, "
            f"and replacing it would lose guidance: {hazard}. "
            f"Leave it alone, or overwrite it deliberately with sxr init --write --force"
        )
    if installed != version:
        return 1, (
            f"primer v{installed or '?'} installed in {target}, "
            f"binary is v{version}; run sxr init --write"
        )
    if body != PRIMER_BODY:
        return 1, (
            f"primer v{version} in {target} is stamped this version but its body "
            f"differs from this binary's; run sxr init --write"
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
ForceF = Annotated[bool, typer.Option("--force", help="Overwrite even if guidance is lost")]


def init_cmd(
    file: FileArg = None,
    write: WriteF = False,
    check: CheckF = False,
    use_global: GlobalF = False,
    force: ForceF = False,
) -> None:
    """Print the primer that teaches agents sxr, or install it in a context file.

    Bare init writes the block to stdout. --write inserts or replaces it
    between <!-- sxr:primer vX.Y.Z --> markers in FILE (default: the nearest
    AGENTS.md walking up from cwd; --global for the user file), so running it
    twice changes nothing. --check exits 1 when the block is missing, stamped
    another version, or reissued under this one. A replacement that would drop
    flags or commands the installed primer documents is refused with exit 2 and
    needs --force. Unbalanced markers are never rewritten: exit 2.
    """
    from sxr import __version__

    if write and check:
        fail("--write and --check are mutually exclusive")
    if force and not write:
        fail("--force only applies to --write")
    if not (write or check):
        if file is not None or use_global:
            fail("FILE and --global need --write or --check")
        print(primer(__version__), end="")
        raise typer.Exit(0)
    if file is not None and use_global:
        fail("--global and an explicit FILE are mutually exclusive")
    target = file
    try:
        target = _target(file, use_global, write)
        code = _apply(target, write, __version__, force)
    except (OSError, UnicodeError) as exc:
        fail(f"cannot access primer destination {target or 'AGENTS.md'}: {exc}")
    raise typer.Exit(code)


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


def _apply(target: Path, write: bool, version: str, force: bool = False) -> int:
    """Run --write or --check against a resolved target; marker damage exits 2."""
    try:
        if write:
            print(f"{install_primer(target, version, force)} primer v{version} in {target}")
            return 0
        code, note = check_primer(target, version)
    except MarkerError as exc:
        fail(f"{target}: {exc}; fix it by hand")
        return 2
    except DowngradeError as exc:
        fail(f"{target}: refusing to replace the primer, {exc}", "override with --force")
        return 2
    print(note, file=sys.stderr)
    return code
