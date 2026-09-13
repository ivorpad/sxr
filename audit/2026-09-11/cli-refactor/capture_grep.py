"""Capture every `grep` and `cmds` output shape from one checkout, for SXR-CLI-06.

Runs in-process, so `--source` points the import at a baseline snapshot and its
absence captures the working tree. One file per case holds the exit code, stdout
and stderr, so two directories compare byte for byte. Each JSON case also records
whether every stdout line parses, which is the defect this slice is about.

    uv run python capture_grep.py --output evidence-06/before --source /tmp/sxr-b06
    uv run python capture_grep.py --output evidence-06/after
"""

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_grep

# --ids and --full do not exist before this slice; those cases fail there by design.
GREP_CASES = [
    ("plain", ["retry"]),
    ("json", ["retry", "--json"]),
    ("ids", ["retry", "-l"]),
    ("ids-json", ["retry", "-l", "--json"]),
    ("ids-alias-json", ["retry", "--ids", "--json"]),
    ("ids-long-json", ["retry", "--files-with-matches", "--json"]),
    ("count", ["retry", "-c"]),
    ("count-json", ["retry", "-c", "--json"]),
    ("count-ids", ["retry", "-c", "-l"]),
    ("count-context", ["retry", "-c", "-C", "2"]),
    ("count-budget", ["retry", "-c", "--budget", "10"]),
    ("context", ["retry", "-C", "2"]),
    ("context-json", ["retry", "-C", "2", "--json"]),
    ("context-zero", ["retry", "-C", "0"]),
    ("context-negative", ["retry", "-C", "-1"]),
    ("sort-started-no-count", ["retry", "--sort", "started"]),
    ("sort-matches-no-count", ["retry", "--sort", "matches"]),
    ("sort-started-count", ["retry", "-c", "--sort", "started"]),
    ("sort-bad", ["retry", "--sort", "bogus"]),
    ("json-limit-1", ["retry", "--json", "-n", "1"]),
    ("json-limit-2", ["retry", "--json", "-n", "2"]),
    ("json-limit-0", ["retry", "--json", "-n", "0"]),
    ("ids-limit-1", ["retry", "-l", "-n", "1"]),
    ("ids-json-limit-1", ["retry", "-l", "--json", "-n", "1"]),
    ("count-limit-1", ["retry", "-c", "-n", "1"]),
    ("negative-limit", ["retry", "-n", "-1"]),
    ("no-match", ["zzz-no-match"]),
    ("no-match-json", ["zzz-no-match", "--json"]),
    ("no-match-ids-json", ["zzz-no-match", "-l", "--json"]),
    ("no-match-count", ["zzz-no-match", "-c"]),
    ("all-with-count", ["retry", "-c", "--all"]),
    ("all-without-count", ["retry", "--all"]),
    ("fixed", ["-F", "retry", "--json"]),
    ("session-scope-json", ["retry", "@1", "--json"]),
    ("help", ["--help"]),
]

CMDS_CASES = [
    ("text", []),
    ("text-limit-1", ["-n", "1"]),
    ("json", ["--json"]),
    ("json-limit-1", ["--json", "-n", "1"]),
    ("json-limit-2", ["--json", "-n", "2"]),
    ("json-limit-0", ["--json", "-n", "0"]),
    ("json-all-sessions", ["--all-sessions", "--json"]),
    ("json-grep", ["--grep", "git", "--json"]),
    ("json-session-scope", ["@1", "--json"]),
    ("negative-limit", ["--json", "-n", "-1"]),
    ("help", ["--help"]),
]


def _json_health(body: str) -> str:
    """Whether every stdout line parses, recorded next to the output itself."""
    lines = [line for line in body.splitlines() if line]
    if not lines:
        return "no stdout lines"
    bad = []
    for index, line in enumerate(lines, start=1):
        try:
            json.loads(line)
        except ValueError as exc:
            bad.append(f"line {index}: {exc.args[0]}")
    if bad:
        return f"{len(bad)} of {len(lines)} stdout lines are not JSON; " + "; ".join(bad[:3])
    return f"all {len(lines)} stdout lines parse as JSON"


def _run(command: str, provider: str, root: Path, case: tuple) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr.cli import app

    args = case[1]
    scoped = args if "--help" in args else [*args, "--path", "/w"]
    argv = [*(["--codex"] if provider == "codex" else []), command, *scoped]
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
    health = f"json: {_json_health(body)}\n" if "--json" in args else ""
    return (
        f"$ sxr {' '.join(argv)}\nexit={result.exit_code}\n{health}"
        f"--- stdout\n{body}--- stderr\n{trailing}"
    )


def main() -> None:
    """Write one file per command, provider and case under --output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory to fill (required)")
    parser.add_argument("--source", type=Path, help="Checkout to import sxr from (default: this)")
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.source / "src"))
    args.output.mkdir(parents=True, exist_ok=True)
    written = 0
    for command, cases in (("grep", GREP_CASES), ("cmds", CMDS_CASES)):
        for provider in ("claude", "codex"):
            with tempfile.TemporaryDirectory(prefix=f"sxr-cap-{provider}-") as directory:
                root = Path(directory)
                getattr(fixture_grep, provider)(root)
                for case in cases:
                    name = f"{command}-{provider}-{case[0]}.txt"
                    (args.output / name).write_text(_run(command, provider, root, case))
                    written += 1
    print(f"wrote {written} captures to {args.output}")


if __name__ == "__main__":
    main()
