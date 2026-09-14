"""Capture grep's three caps separately, for SXR-CLI-07's before/after diff.

Grouped so the index says which cap each case is about:

* ``rows`` — `-n`, including the `-n 0` whose meaning changes here.
* ``chars`` — `--budget`, including whether `-n 0` still discards an explicit one.
* ``text`` — the per-match cap, and the new `--full` that lifts it.
* ``all`` — `--all`, whose meaning changes from "keep zero rows in -c" to
  "uncapped complete output", plus the new `--include-zero` that takes over the
  old job. Cases naming flags that do not exist yet are included deliberately:
  their `before` capture is the exit-2 that proves they were absent.
* ``keep`` — what must not move: raw records per D-09, the `grep_session`
  projection per D-12, dedup, exit codes, `-c` totals, `--sort`, `-C`.

Each file records the invocation, exit code, stdout and stderr, and a measured
line giving the printed row count, the widest row, whether a trim marker appeared,
and whether complete text survived — because these caps are visible in counts
before they are visible in prose.

    uv run python capture_caps2.py --output evidence-slice-07/before --source /tmp/b07
    uv run python capture_caps2.py --output evidence-slice-07/after
"""

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_caps2

N = fixture_caps2.NEEDLE
ABSENT = fixture_caps2.ABSENT

ROW_CASES = [
    ("default", ["grep", N]),
    ("limit-2", ["grep", N, "-n", "2"]),
    ("limit-5", ["grep", N, "-n", "5"]),
    ("limit-zero", ["grep", N, "-n", "0"]),
    ("limit-zero-json", ["grep", N, "-n", "0", "--json"]),
    ("limit-2-json", ["grep", N, "-n", "2", "--json"]),
    ("limit-negative", ["grep", N, "-n", "-1"]),
    ("limit-2-ids", ["grep", N, "-n", "2", "--ids"]),
    ("limit-2-count", ["grep", N, "-n", "2", "-c"]),
    ("limit-2-context", ["grep", N, "-n", "2", "-C", "1"]),
]

CHAR_CASES = [
    ("budget-400", ["grep", N, "--budget", "400"]),
    ("budget-2000", ["grep", N, "--budget", "2000"]),
    ("budget-zero", ["grep", N, "--budget", "0"]),
    ("budget-400-limit-zero", ["grep", N, "--budget", "400", "-n", "0"]),
    ("budget-400-limit-5", ["grep", N, "--budget", "400", "-n", "5"]),
    ("budget-400-json", ["grep", N, "--budget", "400", "--json"]),
    ("budget-400-ids", ["grep", N, "--budget", "400", "--ids"]),
    ("budget-negative", ["grep", N, "--budget", "-1"]),
]

TEXT_CASES = [
    ("full", ["grep", N, "--full"]),
    ("full-limit-5", ["grep", N, "--full", "-n", "5"]),
    ("full-limit-zero", ["grep", N, "--full", "-n", "0"]),
    ("full-budget-400", ["grep", N, "--full", "--budget", "400"]),
    ("full-context", ["grep", N, "--full", "-C", "1"]),
    ("full-json", ["grep", N, "--full", "--json"]),
    ("full-count", ["grep", N, "--full", "-c"]),
]

ALL_CASES = [
    ("all", ["grep", N, "--all"]),
    ("all-count", ["grep", N, "-c", "--all"]),
    ("all-count-allzero", ["grep", ABSENT, "-c", "--all"]),
    ("all-limit-2", ["grep", N, "--all", "-n", "2"]),
    ("all-budget-400", ["grep", N, "--all", "--budget", "400"]),
    ("all-json", ["grep", N, "--all", "--json"]),
    ("include-zero-count", ["grep", N, "-c", "--include-zero"]),
    ("include-zero-count-allzero", ["grep", ABSENT, "-c", "--include-zero"]),
    ("include-zero-count-json", ["grep", N, "-c", "--include-zero", "--json"]),
    ("include-zero-without-count", ["grep", N, "--include-zero"]),
    ("full-and-all", ["grep", N, "--full", "--all"]),
]

KEEP_CASES = [
    ("json-dedup", ["grep", N, "--json"]),
    ("ids-json", ["grep", N, "--ids", "--json"]),
    ("count-json", ["grep", N, "-c", "--json"]),
    ("count-plain", ["grep", N, "-c"]),
    ("count-sort-started", ["grep", N, "-c", "--sort", "started"]),
    ("context-3", ["grep", N, "-C", "3"]),
    ("no-matches", ["grep", ABSENT]),
    ("no-matches-count", ["grep", ABSENT, "-c"]),
    ("no-matches-json", ["grep", ABSENT, "--json"]),
    ("count-with-budget", ["grep", N, "-c", "--budget", "400"]),
    ("ids-plain", ["grep", N, "--ids"]),
    ("help", ["grep", "--help"]),
]

GROUPS = [
    ("rows", ROW_CASES),
    ("chars", CHAR_CASES),
    ("text", TEXT_CASES),
    ("all", ALL_CASES),
    ("keep", KEEP_CASES),
]


def _measure(body: str, args: list) -> str:
    """Counts a cap change moves: rows printed, widest row, markers, whole text."""
    rows = [line for line in body.splitlines() if line]
    if not rows:
        return "no stdout rows"
    data = [row for row in rows if not row.startswith("#")]
    complete = sum(1 for row in rows if "ENDOF" in row)
    return (
        f"{len(rows)} rows ({len(data)} data), widest {max(len(r) for r in rows)}, "
        f"trim marker {'yes' if 'chars]' in body else 'no'}, complete texts {complete}"
    )


def _json_health(body: str) -> str:
    """Whether every stdout line parses, recorded beside the output."""
    rows = [line for line in body.splitlines() if line]
    bad = []
    for index, row in enumerate(rows, start=1):
        try:
            json.loads(row)
        except ValueError as exc:
            bad.append(f"line {index}: {exc.args[0]}")
    if bad:
        return f"{len(bad)} of {len(rows)} stdout lines are not JSON; " + "; ".join(bad[:2])
    return f"all {len(rows)} stdout lines parse as JSON"


def _run(provider: str, root: Path, args: list) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr import util
    from sxr.cli import app

    getattr(util, "reset_env_notices", lambda: None)()
    scoped = args + ([] if "--help" in args else ["--path", fixture_caps2.CWD])
    argv = [*(["--codex"] if provider == "codex" else []), *scoped]
    with tempfile.TemporaryDirectory(prefix="sxr-caps2-cache-") as cache:
        saved = dict(os.environ)
        os.environ["SXR_CACHE_DIR"] = cache
        for name in ("SXR_NO_CACHE", "SXR_BUDGET", "SXR_LINE_LIMIT"):
            os.environ.pop(name, None)
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
    lines = [f"$ sxr {' '.join(argv)}", f"exit={result.exit_code}", f"rows: {_measure(body, args)}"]
    if "--json" in args:
        lines.append(f"json: {_json_health(body)}")
    return "\n".join(lines) + f"\n--- stdout\n{body}--- stderr\n{trailing}"


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
        with tempfile.TemporaryDirectory(prefix=f"sxr-caps2-{provider}-") as directory:
            root = Path(directory)
            getattr(fixture_caps2, provider)(root)
            for group, cases in GROUPS:
                for name, case in cases:
                    (args.output / f"{group}-{provider}-{name}.txt").write_text(
                        _run(provider, root, case)
                    )
                    written += 1
    print(f"wrote {written} captures to {args.output}")


if __name__ == "__main__":
    main()
