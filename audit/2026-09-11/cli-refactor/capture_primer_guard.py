"""Reproduce the primer hazard against the real published primer, before and after.

The published v0.13.0 primer body is rendered from `origin/HEAD` with `git show`
into a temp module, so nothing is checked out and no repository is touched. Every
fixture is a scratch file under a temp directory.

    uv run python capture_primer_guard.py --output evidence-A/primer-guard.log
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN = [str(REPO / ".venv/bin/python"), "-c", "from sxr import main; main()"]


def published_primer(directory: Path) -> str:
    """The v0.13.0 primer block exactly as the published release renders it."""
    source = subprocess.run(
        ["git", "-C", str(REPO), "show", "origin/HEAD:src/sxr/onboard.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    path = directory / "published_onboard.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("published_onboard", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["published_onboard"] = module
    spec.loader.exec_module(module)
    return f"<!-- sxr:primer v0.13.0 -->\n{module.PRIMER_BODY}<!-- /sxr:primer -->\n"


def fixture(directory: Path, name: str, block: str) -> Path:
    """A scratch context file with local prose above and below the primer block."""
    target = directory / name
    target.write_text(f"# Notes\n\nLocal prose above.\n\n{block}\nLocal prose below.\n")
    return target


def run(*args: str, source: Path) -> tuple[int, str, str]:
    """Invoke one tree's CLI; source is the src directory to import sxr from."""
    environment = dict(os.environ, PYTHONPATH=str(source))
    done = subprocess.run(RUN + list(args), capture_output=True, text=True, env=environment)
    return done.returncode, done.stdout, done.stderr


def report(lines: list[str], label: str, code: int, out: str, err: str) -> None:
    """Append one invocation's exit status and streams to the log."""
    lines.append(f"$ {label}")
    lines.append(f"    exit={code}")
    for stream, text in (("out", out), ("err", err)):
        for line in text.splitlines():
            lines.append(f"    {stream}| {line}")


def before_case(lines: list[str], base: Path, block: str) -> None:
    """The destructive write as HEAD 48b11c6c shipped it, in an extracted tree."""
    tree = base / "before"
    tree.mkdir()
    archive = tree / "head.tar"
    with archive.open("wb") as handle:
        subprocess.run(["git", "-C", str(REPO), "archive", "HEAD"], stdout=handle, check=True)
    subprocess.run(["tar", "-x", "-C", str(tree), "-f", str(archive)], check=True)
    source = tree / "src"
    lines += ["=" * 78, "BEFORE, as HEAD 48b11c6c shipped it (version 0.12.2, no guard)", "=" * 78]
    target = fixture(base, "before-AGENTS.md", block)
    keep = target.read_bytes()
    report(lines, "init --check", *run("init", "--check", str(target), source=source))
    report(lines, "init --write", *run("init", "--write", str(target), source=source))
    text = target.read_text()
    lines += [
        f"    file changed: {target.read_bytes() != keep}",
        f"    --latest still documented: {'--latest' in text}",
        f"    local prose kept: {text.count('Local prose')} of 2",
        "",
    ]


def after_case(lines: list[str], base: Path, block: str) -> None:
    """The same write, and the --force override, against this tree's guard."""
    source = REPO / "src"
    lines += ["=" * 78, "AFTER, this tree with the guard", "=" * 78]
    target = fixture(base, "after-AGENTS.md", block)
    keep = target.read_bytes()
    report(lines, "init --check", *run("init", "--check", str(target), source=source))
    report(lines, "init --write", *run("init", "--write", str(target), source=source))
    lines += [
        f"    file changed: {target.read_bytes() != keep}",
        f"    --latest still documented: {'--latest' in target.read_text()}",
        "",
        "An explicit override is still available, and still keeps the prose:",
    ]
    report(
        lines,
        "init --write --force",
        *run("init", "--write", "--force", str(target), source=source),
    )
    text = target.read_text()
    lines += [
        f"    --latest documented afterwards: {'--latest' in text}",
        f"    local prose kept: {text.count('Local prose')} of 2",
        "",
    ]


def legit_case(lines: list[str], base: Path, block: str) -> None:
    """A refresh from an older primer that documents nothing this body lacks."""
    source = REPO / "src"
    older = block.replace("v0.13.0", "v0.12.2").replace(
        "and prompts --latest reads the newest human conversation. Other read views\n", ""
    )
    lines.append("A legitimate refresh from an older primer that loses nothing:")
    target = fixture(base, "legit-AGENTS.md", older)
    report(lines, "init --check", *run("init", "--check", str(target), source=source))
    report(lines, "init --write", *run("init", "--write", str(target), source=source))
    text = target.read_text()
    lines += [
        f"    stamped this version: {'v0.14.0' in text}",
        f"    local prose kept: {text.count('Local prose')} of 2",
        "",
        "And the refreshed file is then reported up to date, idempotently:",
    ]
    report(lines, "init --check", *run("init", "--check", str(target), source=source))
    keep = target.read_bytes()
    report(lines, "init --write", *run("init", "--write", str(target), source=source))
    lines.append(f"    file changed by the second write: {target.read_bytes() != keep}")


def main() -> int:
    """Capture the hazard before and after, plus the legitimate paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the log")
    args = parser.parse_args()

    lines: list[str] = []
    with tempfile.TemporaryDirectory(prefix="sxr-primer-") as directory:
        base = Path(directory)
        block = published_primer(base)
        lines += [
            "Primer hazard, reproduced against the real published v0.13.0 primer",
            "",
            f"published block: {len(block.splitlines())} lines, "
            f"mentions --latest: {'--latest' in block}",
            "",
        ]
        before_case(lines, base, block)
        after_case(lines, base, block)
        legit_case(lines, base, block)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
