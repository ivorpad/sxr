"""Capture every timestamp-dependent output shape, for SXR-CLI-08's diff.

Runs in-process, so `--source` points the import at a baseline snapshot and its
absence captures the working tree. One file per case holds the invocation, the
exit code, stdout and stderr, so two directories compare byte for byte.

The scope cases matter more than the display cases. Window filtering already used
UTC instants before this slice, so `--since`/`--before` on a *literal* bound must
stay byte-identical; a bound written as `@N` can move, because `@N` numbering is
what the corrected ordering changes. Both kinds are captured separately so the
distinction is visible rather than argued.

    uv run python capture_time.py --output evidence-slice-08/before --source /tmp/sxr-b08
    uv run python capture_time.py --output evidence-slice-08/after
"""

import argparse
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_time

N = fixture_time.NEEDLE

# Ordering and the @N handles it decides.
ORDER_CASES = [
    ("list", ["list"]),
    ("list-json", ["list", "--json"]),
    ("list-limit-2", ["list", "-n", "2"]),
    ("handle-1", ["show", "@1", "--tail", "1"]),
    ("handle-2", ["show", "@2", "--tail", "1"]),
    ("handle-3", ["show", "@3", "--tail", "1"]),
    ("handle-4", ["show", "@4", "--tail", "1"]),
    ("handle-range", ["show", "@1:@2", "--tail", "1"]),
]

# Display of instants: headers, columns and derived JSON metadata.
DISPLAY_CASES = [
    ("stats", ["stats", "@1"]),
    ("stats-json", ["stats", "@1", "--json"]),
    ("stats-all", ["stats", "@1:@4"]),
    ("show-header", ["show", "@1", "--tail", "2"]),
    ("cmds-text", ["cmds", "--all-sessions"]),
    ("grep-count", ["grep", N, "-c"]),
    ("grep-count-json", ["grep", N, "-c", "--json"]),
    ("grep-count-sort-started", ["grep", N, "-c", "--sort", "started"]),
    ("grep-count-sort-matches", ["grep", N, "-c", "--sort", "matches"]),
    ("grep-rows", ["grep", N]),
    ("grep-context", ["grep", N, "-C", "1"]),
]

# Raw --json must keep the source timestamp verbatim (D-09).
RAW_CASES = [
    ("raw-show-json", ["show", "@1", "--json", "--tail", "3"]),
    ("raw-grep-json", ["grep", N, "--json"]),
    ("raw-cmds-json", ["cmds", "--all-sessions", "--json"]),
    ("raw-prompts-json", ["prompts", "@1", "--json"]),
]

# Scope: literal bounds must not move; an @N bound may, and that is the point.
SCOPE_CASES = [
    ("since-the-10th", ["list", "--since", "2026-09-10"]),
    ("before-the-11th", ["list", "--before", "2026-09-11"]),
    ("since-the-11th", ["list", "--since", "2026-09-11"]),
    ("since-the-10th-before-11th", ["list", "--since", "2026-09-10", "--before", "2026-09-11"]),
    ("since-iso-0730z", ["list", "--since", "2026-09-10T07:30:00Z"]),
    ("before-iso-0730z", ["list", "--before", "2026-09-10T07:30:00Z"]),
    ("since-iso-offset", ["list", "--since", "2026-09-10T09:30:00+02:00"]),
    ("since-handle-2", ["list", "--since", "@2"]),
    ("since-handle-3", ["list", "--since", "@3"]),
    ("before-handle-2", ["list", "--before", "@2"]),
    ("grep-count-since-the-10th", ["grep", N, "-c", "--since", "2026-09-10"]),
    ("cmds-since-the-11th", ["cmds", "--all-sessions", "--since", "2026-09-11"]),
    ("bad-since", ["list", "--since", "not-a-date"]),
]

GROUPS = [
    ("order", ORDER_CASES),
    ("display", DISPLAY_CASES),
    ("raw", RAW_CASES),
    ("scope", SCOPE_CASES),
]


def _run(provider: str, root: Path, args: list) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr.cli import app

    scoped = args if "--help" in args else [*args, "--path", CWD]
    argv = [*(["--codex"] if provider == "codex" else []), *scoped]
    with tempfile.TemporaryDirectory(prefix="sxr-cap-cache-") as cache:
        saved = dict(os.environ)
        os.environ["SXR_CACHE_DIR"] = cache
        os.environ.pop("SXR_NO_CACHE", None)
        os.environ["CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME"] = str(root)
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                result = CliRunner().invoke(app, argv)
        finally:
            os.environ.clear()
            os.environ.update(saved)
    body = result.stdout
    trailing = result.stderr if result.stderr_bytes is not None else err.getvalue()
    for noisy in (str(root), tempfile.gettempdir()):
        body, trailing = body.replace(noisy, "<fixture>"), trailing.replace(noisy, "<fixture>")
    return (
        f"$ sxr {' '.join(argv)}\nexit={result.exit_code}\n--- stdout\n{body}--- stderr\n{trailing}"
    )


CWD = fixture_time.CWD


def main() -> None:
    """Write one file per group, provider and case under --output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory to fill (required)")
    parser.add_argument("--source", type=Path, help="Checkout to import sxr from (default: this)")
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.source / "src"))
    args.output.mkdir(parents=True, exist_ok=True)
    written = 0
    for provider in ("claude", "codex"):
        with tempfile.TemporaryDirectory(prefix=f"sxr-cap-{provider}-") as directory:
            root = Path(directory)
            getattr(fixture_time, provider)(root)
            for group, cases in GROUPS:
                for name, case in cases:
                    target = args.output / f"{group}-{provider}-{name}.txt"
                    target.write_text(_run(provider, root, case))
                    written += 1
    print(f"wrote {written} captures to {args.output}")


if __name__ == "__main__":
    main()
