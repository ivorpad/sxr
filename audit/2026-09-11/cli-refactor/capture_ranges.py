"""Capture show/prompts/tools range behavior against the synthetic corpora.

Run as `uv run python capture_ranges.py <outdir>`; each invocation's stdout,
stderr and exit code land in one file per case so before/after comparisons are
byte-level. Only the synthetic transcripts from fixture_ranges are read.
"""

import sys
import tempfile
from pathlib import Path

CASES: list[tuple[str, list[str]]] = [
    ("claude-list", ["--path", "/w"]),
    ("claude-show-single", ["show", "@1", "--path", "/w"]),
    ("claude-show-range", ["show", "@1:@2", "--path", "/w"]),
    ("claude-show-range-json", ["show", "@1:@2", "--path", "/w", "--json"]),
    ("claude-show-range-limit", ["show", "@1:@2", "--path", "/w", "-n", "1"]),
    ("claude-prompts-single", ["prompts", "@1", "--path", "/w"]),
    ("claude-prompts-range", ["prompts", "@1:@2", "--path", "/w"]),
    ("claude-prompts-range-json", ["prompts", "@1:@2", "--path", "/w", "--json"]),
    ("claude-prompts-range-limit", ["prompts", "@1:@2", "--path", "/w", "-n", "1"]),
    ("claude-prompts-range-context", ["prompts", "@1:@2", "--path", "/w", "--include-context"]),
    ("claude-prompts-range-all", ["prompts", "@1:@2", "--path", "/w", "--all"]),
    ("claude-tools-single", ["tools", "@1", "--path", "/w"]),
    ("claude-tools-range", ["tools", "@1:@2", "--path", "/w"]),
    ("claude-tools-range-json", ["tools", "@1:@2", "--path", "/w", "--json"]),
    ("claude-tools-range-limit", ["tools", "@1:@2", "--path", "/w", "-n", "1"]),
    ("claude-show-range-inverted", ["show", "@2:@1", "--path", "/w"]),
    ("claude-prompts-range-self", ["prompts", "@2:@2", "--path", "/w"]),
    ("claude-show-range-overrun", ["show", "@1:@5", "--path", "/w"]),
    ("claude-prompts-range-unlimited", ["prompts", "@1:@2", "--path", "/w", "-n", "0"]),
    ("claude-show-range-around", ["show", "@1:@2", "--path", "/w", "--around", "3"]),
    ("claude-show-range-tail", ["show", "@1:@2", "--path", "/w", "--tail", "2"]),
    ("claude-show-range-empty", ["show", "@1:@2", "--path", "/w", "--type", "missing"]),
    ("claude-prompts-range-budget", ["prompts", "@1:@2", "--path", "/w", "--budget", "1"]),
    ("codex-list", ["--codex", "--path", "/w"]),
    ("codex-show-range", ["--codex", "show", "@1:@2", "--path", "/w"]),
    ("codex-prompts-range", ["--codex", "prompts", "@1:@2", "--path", "/w"]),
    ("codex-tools-range", ["--codex", "tools", "@1:@2", "--path", "/w"]),
    ("codex-tools-range-json", ["--codex", "tools", "@1:@2", "--path", "/w", "--json"]),
]


def run(argv: list[str]) -> tuple[str, str, int]:
    """Invoke the Typer app in-process and return (stdout, stderr, exit code)."""
    from typer.testing import CliRunner

    from sxr.cli import app

    result = CliRunner().invoke(app, argv)
    return result.stdout, result.stderr, result.exit_code


def main() -> int:
    """Write one capture file per case into the directory named on argv."""
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sxr-ranges-") as tmp:
        sys.path.insert(0, str(Path(__file__).parent))
        from fixture_ranges import apply_env

        apply_env(Path(tmp))
        for name, argv in CASES:
            stdout, stderr, code = run(argv)
            body = (
                f"$ sxr {' '.join(argv)}\n--- exit {code}\n--- stdout\n{stdout}--- stderr\n{stderr}"
            )
            (outdir / f"{name}.txt").write_text(body.replace(tmp, "<TMP>"))
            print(f"{name}: exit {code}, {len(stdout)} bytes stdout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
