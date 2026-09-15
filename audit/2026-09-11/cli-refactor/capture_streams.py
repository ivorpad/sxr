"""Capture which stream every line goes to, for SXR-CLI-24's before/after diff.

The whole slice is "results on stdout, notices on stderr", so each capture records
stdout and stderr separately and then answers the two questions that matter:

* Does stdout stay parseable when the mode says it is machine-readable? A `#`
  comment or a bare notice on `--json` stdout is the defect, so every `--json` case
  reports whether `2>/dev/null` would leave valid JSON only.
* Is an omission reported anywhere at all? A capped view that says nothing on either
  stream is how an agent silently loses results.

Groups: ``json`` for machine-readable stdout purity, ``text`` for where headers and
footers go in human mode, ``notice`` for omission reporting under a row cap,
``coverage`` for `--coverage` and discovery diagnostics, and ``keep`` for what must
not move — raw records per D-09, the `grep_session` projection per D-12, dedup, exit
codes and `--file` selection.

    uv run python capture_streams.py --output evidence-slice-24/before --source /tmp/r24
    uv run python capture_streams.py --output evidence-slice-24/after
"""

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_streams

N = fixture_streams.NEEDLE

JSON_CASES = [
    ("list", ["list", "--json"]),
    ("list-limit-1", ["list", "-n", "1", "--json"]),
    ("list-limit-0", ["list", "-n", "0", "--json"]),
    ("grep-limit-1", ["grep", N, "-n", "1", "--json"]),
    ("grep-ids", ["grep", N, "--ids", "--json"]),
    ("grep-count", ["grep", N, "-c", "--json"]),
    ("cmds-limit-1", ["cmds", "-n", "1", "--json"]),
    ("cmds-all-sessions", ["cmds", "--all-sessions", "-n", "2", "--json"]),
    ("show-limit-1", ["show", "@1", "-n", "1", "--json"]),
    ("prompts-limit-1", ["prompts", "@1", "-n", "1", "--json"]),
    ("errors-limit-1", ["errors", "@1", "-n", "1", "--json"]),
    ("tools", ["tools", "@1", "--json"]),
    ("tools-limit-1", ["tools", "@1", "-n", "1", "--json"]),
    ("stats-limit-1", ["stats", "@1:@2", "-n", "1", "--json"]),
    ("path", ["path", "@1", "--json"]),
    ("show-range", ["show", "@1:@2", "--json"]),
    ("tools-range", ["tools", "@1:@2", "--json"]),
    ("stats-range", ["stats", "@1:@2", "--json"]),
]

TEXT_CASES = [
    ("list", ["list"]),
    ("list-limit-1", ["list", "-n", "1"]),
    ("grep-limit-1", ["grep", N, "-n", "1"]),
    ("cmds-limit-1", ["cmds", "-n", "1"]),
    ("errors-limit-1", ["errors", "@1", "-n", "1"]),
    ("errors-compact", ["errors", "@1", "--compact"]),
    ("tools", ["tools", "@1"]),
    ("tools-limit-1", ["tools", "@1", "-n", "1"]),
    ("stats", ["stats", "@1"]),
    ("show-limit-1", ["show", "@1", "-n", "1"]),
    ("prompts-limit-1", ["prompts", "@1", "-n", "1"]),
    ("show-range", ["show", "@1:@2"]),
]

NOTICE_CASES = [
    ("list-limit-1", ["list", "-n", "1"]),
    ("list-limit-1-json", ["list", "-n", "1", "--json"]),
    ("tools-limit-1", ["tools", "@1", "-n", "1"]),
    ("tools-limit-1-json", ["tools", "@1", "-n", "1", "--json"]),
    ("stats-limit-1-json", ["stats", "@1:@2", "-n", "1", "--json"]),
    ("cmds-limit-1-json", ["cmds", "-n", "1", "--json"]),
    ("grep-limit-1-json", ["grep", N, "-n", "1", "--json"]),
    ("show-limit-1-json", ["show", "@1", "-n", "1", "--json"]),
    ("prompts-limit-1-json", ["prompts", "@1", "-n", "1", "--json"]),
    ("errors-limit-1-json", ["errors", "@1", "-n", "1", "--json"]),
    # A filtered cmds view that fell back to the default scope: the sessions it did
    # not read are a completeness fact, not a display detail.
    ("cmds-grep", ["cmds", "--grep", "git"]),
    ("cmds-grep-json", ["cmds", "--grep", "git", "--json"]),
]

COVERAGE_CASES = [
    ("list", ["list", "--coverage"]),
    ("list-json", ["list", "--coverage", "--json"]),
    ("grep-json", ["grep", N, "--coverage", "--json"]),
    ("missing-root", ["list", "--coverage", "--path", "/w/nowhere"]),
    ("missing-root-json", ["list", "--coverage", "--json", "--path", "/w/nowhere"]),
    ("recursive", ["list", "--coverage", "--recursive"]),
]

KEEP_CASES = [
    ("grep-json-dedup", ["grep", N, "--json"]),
    ("grep-all", ["grep", N, "--all"]),
    ("grep-include-zero", ["grep", N, "-c", "--include-zero"]),
    ("show-json", ["show", "@1", "--json"]),
    ("cmds-json", ["cmds", "--json"]),
    ("errors-json", ["errors", "@1", "--json"]),
    ("list-plain", ["list"]),
    ("no-matches", ["grep", "quernstone"]),
    ("limit-negative", ["list", "-n", "-1"]),
    ("help", ["--help"]),
]

GROUPS = [
    ("json", JSON_CASES),
    ("text", TEXT_CASES),
    ("notice", NOTICE_CASES),
    ("coverage", COVERAGE_CASES),
    ("keep", KEEP_CASES),
]


def _stdout_health(body: str, json_mode: bool) -> str:
    """Whether stdout is what its mode promises: pure JSON, or plain rows."""
    lines = [line for line in body.splitlines() if line]
    if not json_mode:
        comments = sum(1 for line in lines if line.startswith("#"))
        return f"{len(lines)} stdout lines, {comments} start with '#'"
    bad = []
    for index, line in enumerate(lines, start=1):
        try:
            json.loads(line)
        except ValueError:
            bad.append(f"line {index}: {line[:40]!r}")
    if bad:
        return f"NOT PURE: {len(bad)} of {len(lines)} stdout lines are not JSON; " + "; ".join(
            bad[:2]
        )
    return f"pure: all {len(lines)} stdout lines parse as JSON"


def _omission(body: str, err: str) -> str:
    """Where an omission was reported, if anywhere at all."""
    words = ("more", "omitted", "hidden", "showing first", "of 4", "raise -n")
    on_out = any(w in line for line in body.splitlines() for w in words if line.startswith("#"))
    on_err = any(w in err for w in words)
    if on_out and on_err:
        return "reported on both streams"
    if on_out:
        return "reported on stdout only"
    if on_err:
        return "reported on stderr only"
    return "NOT REPORTED on either stream"


def _run(provider: str, root: Path, args: list) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript."""
    from typer.testing import CliRunner

    from sxr import util
    from sxr.cli import app

    getattr(util, "reset_env_notices", lambda: None)()
    scoped = args + (
        [] if "--help" in args or "--path" in args else ["--path", fixture_streams.CWD]
    )
    argv = [*(["--codex"] if provider == "codex" else []), *scoped]
    with tempfile.TemporaryDirectory(prefix="sxr-streams-cache-") as cache:
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
        body = body.replace(noisy, "<fixture>")
        trailing = trailing.replace(noisy, "<fixture>")
    lines = [
        f"$ sxr {' '.join(argv)}",
        f"exit={result.exit_code}",
        f"stdout: {_stdout_health(body, '--json' in args)}",
        f"omission: {_omission(body, trailing)}",
        f"stderr lines: {len([x for x in trailing.splitlines() if x])}",
    ]
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
        with tempfile.TemporaryDirectory(prefix=f"sxr-streams-{provider}-") as directory:
            root = Path(directory)
            getattr(fixture_streams, provider)(root)
            for group, cases in GROUPS:
                for name, case in cases:
                    (args.output / f"{group}-{provider}-{name}.txt").write_text(
                        _run(provider, root, case)
                    )
                    written += 1
    print(f"wrote {written} captures to {args.output}")


if __name__ == "__main__":
    main()
