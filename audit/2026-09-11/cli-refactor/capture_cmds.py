"""Capture every `sxr cmds` shape from one checkout, for SXR-CLI-05's diff.

Runs in-process, so `--source` points the import at the baseline snapshot and
its absence captures the working tree. One file per case holds exit code, stdout
and stderr, so the two directories compare byte for byte.

    uv run python capture_cmds.py --output evidence-05/before --source /tmp/sxr-b05
    uv run python capture_cmds.py --output evidence-05/after
"""

import argparse
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_cmds

# --all-sessions does not exist before this slice; those cases fail there by design.
CASES = [
    ("no-selector", []),
    ("at1", ["@1"]),
    ("at2", ["@2"]),
    ("range", ["@1:@2"]),
    ("grep-no-selector", ["--grep", "git push"]),
    ("grep-at1", ["@1", "--grep", "git push"]),
    ("grep-at2", ["@2", "--grep", "git push"]),
    ("grep-range", ["@1:@2", "--grep", "git push"]),
    ("grep-only-oldest", ["--grep", "alpha"]),
    ("grep-empty-string", ["--grep", ""]),
    ("grep-no-match", ["--grep", "nothing-matches-this"]),
    ("grep-limit-1", ["--grep", "git push", "-n", "1"]),
    ("json-no-selector", ["--json"]),
    ("json-grep", ["--grep", "git push", "--json"]),
    ("json-range", ["@1:@2", "--json"]),
    ("json-grep-limit-1", ["--grep", "git push", "--json", "-n", "1"]),
    ("all-sessions", ["--all-sessions"]),
    ("all-sessions-grep", ["--all-sessions", "--grep", "git push"]),
    ("all-sessions-json", ["--all-sessions", "--json"]),
    ("all-sessions-with-selector", ["@1", "--all-sessions"]),
    ("negative-limit", ["-n", "-1"]),
    ("help", ["--help"]),
]


def _run(provider: str, root: Path, case: tuple) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr.cli import app

    args = case[1]
    scoped = args if "--help" in args else [*args, "--path", "/w"]
    argv = [*(["--codex"] if provider == "codex" else []), "cmds", *scoped]
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


def main() -> None:
    """Write one file per provider and case under --output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory to fill (required)")
    parser.add_argument("--source", type=Path, help="Checkout to import sxr from (default: this)")
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.source / "src"))
    args.output.mkdir(parents=True, exist_ok=True)
    for provider in ("claude", "codex"):
        with tempfile.TemporaryDirectory(prefix=f"sxr-cap-{provider}-") as directory:
            root = Path(directory)
            getattr(fixture_cmds, provider)(root)
            for case in CASES:
                (args.output / f"{provider}-{case[0]}.txt").write_text(_run(provider, root, case))
    print(f"wrote {len(CASES) * 2} captures to {args.output}")


if __name__ == "__main__":
    main()
