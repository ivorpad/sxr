"""Capture every `sxr errors` shape from one checkout, for SXR-CLI-04's diff.

Runs in-process against whichever `sxr` is importable, so pointing PYTHONPATH at
the baseline snapshot captures the before-tree and pointing it at the working
tree captures the after-tree. Each case writes one file holding exit code,
stdout and stderr, so the two directories can be compared byte for byte.

    uv run python capture_errors.py --output evidence-04/before --source /tmp/sxr-b04
    uv run python capture_errors.py --output evidence-04/after
"""

import argparse
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_errors

# --compact does not exist before this slice; those cases are expected to fail there.
CASES = [
    ("default-newest", []),
    ("default-at1", ["@1"]),
    ("default-at2", ["@2"]),
    ("range", ["@1:@2"]),
    ("range-limit-1", ["@1:@2", "-n", "1"]),
    ("range-limit-3", ["@1:@2", "-n", "3"]),
    ("range-limit-0", ["@1:@2", "-n", "0"]),
    ("limit-root-position", ["@1:@2"], ["-n", "1"]),
    ("json-at1", ["@1", "--json"]),
    ("json-range", ["@1:@2", "--json"]),
    ("json-range-limit-1", ["@1:@2", "--json", "-n", "1"]),
    ("json-range-limit-0", ["@1:@2", "--json", "-n", "0"]),
    ("compact-at1", ["@1", "--compact"]),
    ("compact-range", ["@1:@2", "--compact"]),
    ("compact-range-limit-1", ["@1:@2", "--compact", "-n", "1"]),
    ("compact-json", ["@1", "--compact", "--json"]),
    ("negative-limit", ["@1", "-n", "-1"]),
    ("empty-session", ["@1", "--path", "/elsewhere"]),
    ("help", ["--help"]),
]


def _run(provider: str, root: Path, case: tuple) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr.cli import app

    args = case[1]
    root_flags = case[2] if len(case) > 2 else []
    scoped = args if ("--path" in args or "--help" in args) else [*args, "--path", "/w"]
    argv = [*root_flags, *(["--codex"] if provider == "codex" else []), "errors", *scoped]
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
    errors_text = result.stderr if result.stderr_bytes is not None else err.getvalue()
    # Absolute fixture paths differ per run; the point of comparison is the layout.
    for noisy in (str(root), tempfile.gettempdir()):
        body, errors_text = (
            body.replace(noisy, "<fixture>"),
            errors_text.replace(noisy, "<fixture>"),
        )
    return (
        f"$ sxr {' '.join(argv)}\nexit={result.exit_code}\n"
        f"--- stdout\n{body}--- stderr\n{errors_text}"
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
            getattr(fixture_errors, provider)(root)
            for case in CASES:
                text = _run(provider, root, case)
                (args.output / f"{provider}-{case[0]}.txt").write_text(text)
                print(f"{provider}-{case[0]}: {len(text)} bytes")
    print(f"wrote {len(CASES) * 2} captures to {args.output}")


if __name__ == "__main__":
    main()
