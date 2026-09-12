"""Capture show's selection behavior against the synthetic SXR-CLI-03 corpora.

Run as `uv run python capture_show.py <outdir>`; each invocation's stdout, stderr
and exit code land in one file per case, so before/after comparison is a byte
comparison. Only the synthetic transcripts from fixture_show are read.
"""

import sys
import tempfile
from pathlib import Path

CASES: list[tuple[str, list[str]]] = [
    # Single flags: the shapes existing scripts use, expected to stay identical.
    ("skeleton", ["show", "--path", "/w"]),
    ("skeleton-json", ["show", "--path", "/w", "--json"]),
    ("thinking", ["show", "--path", "/w", "--thinking"]),
    ("tools-alias", ["show", "--path", "/w", "--tools"]),
    ("tool-results", ["show", "--path", "/w", "--tool-results"]),
    ("full", ["show", "--path", "/w", "--full"]),
    ("errors", ["show", "--path", "/w", "--errors"]),
    ("type-text", ["show", "--path", "/w", "--type", "text"]),
    ("type-result", ["show", "--path", "/w", "--type", "result"]),
    ("around", ["show", "--path", "/w", "--around", "5"]),
    ("around-context", ["show", "--path", "/w", "--around", "5", "--context", "1"]),
    ("range", ["show", "--path", "/w", "--range", "3:6"]),
    ("range-dash", ["show", "--path", "/w", "--range", "3-6"]),
    ("tail", ["show", "--path", "/w", "--tail", "2"]),
    ("tail-zero", ["show", "--path", "/w", "--tail", "0"]),
    ("limit", ["show", "--path", "/w", "-n", "2"]),
    ("budget-zero", ["show", "--path", "/w", "--budget", "0"]),
    ("budget-one", ["show", "--path", "/w", "--budget", "1"]),
    # Combinations: what used to have a silent winner.
    ("full-errors", ["show", "--path", "/w", "--full", "--errors"]),
    ("type-around", ["show", "--path", "/w", "--type", "tool", "--around", "6", "--context", "1"]),
    ("type-range", ["show", "--path", "/w", "--type", "result", "--range", "1:5"]),
    ("around-errors", ["show", "--path", "/w", "--around", "7", "--context", "2", "--errors"]),
    ("range-errors", ["show", "--path", "/w", "--range", "1:5", "--errors"]),
    ("around-thinking", ["show", "--path", "/w", "--around", "2", "--context", "0", "--thinking"]),
    ("type-tail", ["show", "--path", "/w", "--type", "text", "--tail", "1"]),
    ("errors-tail", ["show", "--path", "/w", "--errors", "--tail", "1"]),
    ("full-type", ["show", "--path", "/w", "--full", "--type", "thinking"]),
    ("errors-json", ["show", "--path", "/w", "--errors", "--json"]),
    ("full-errors-json", ["show", "--path", "/w", "--full", "--errors", "--json"]),
    # Invalid or meaningless input that used to succeed quietly.
    ("around-zero", ["show", "--path", "/w", "--around", "0"]),
    ("around-negative", ["show", "--path", "/w", "--around", "-3"]),
    ("context-negative", ["show", "--path", "/w", "--around", "5", "--context", "-1"]),
    ("context-without-around", ["show", "--path", "/w", "--context", "3"]),
    ("range-reversed", ["show", "--path", "/w", "--range", "6:3"]),
    ("range-zero-start", ["show", "--path", "/w", "--range", "0:4"]),
    ("range-junk", ["show", "--path", "/w", "--range", "junk"]),
    ("around-and-range", ["show", "--path", "/w", "--around", "5", "--range", "1:3"]),
    ("budget-negative", ["show", "--path", "/w", "--budget", "-1"]),
    ("line-limit-negative", ["show", "--path", "/w", "--line-limit", "-5"]),
    ("type-unknown", ["show", "--path", "/w", "--type", "nosuchkind"]),
    ("around-past-end", ["show", "--path", "/w", "--around", "999", "--context", "0"]),
    # Codex reads the same pipeline through a different parser.
    ("codex-skeleton", ["--codex", "show", "--path", "/w"]),
    ("codex-full-errors", ["--codex", "show", "--path", "/w", "--full", "--errors"]),
    ("codex-type-around", ["--codex", "show", "--path", "/w", "--type", "tool", "--around", "5"]),
    ("codex-range-errors", ["--codex", "show", "--path", "/w", "--range", "1:8", "--errors"]),
    (
        "codex-around-and-range",
        ["--codex", "show", "--path", "/w", "--around", "3", "--range", "1:2"],
    ),
    ("codex-tail", ["--codex", "show", "--path", "/w", "--tail", "2"]),
    # Help text carries the documented order, so it is part of the contract.
    ("help", ["show", "--help"]),
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
    with tempfile.TemporaryDirectory(prefix="sxr-show-") as tmp:
        sys.path.insert(0, str(Path(__file__).parent))
        from fixture_show import apply_env

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
