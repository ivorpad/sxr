"""Capture every compact-flag surface, for SXR-CLI-21's before/after diff.

Grouped so the index is readable rather than a flat list of 100 names:

* ``flag`` — explicit `--budget`/`--line-limit` values, including the negatives
  that D-05 rejects on `show` and D-02 keeps as "never truncate" on `prompts`.
* ``env`` — `SXR_BUDGET`/`SXR_LINE_LIMIT`, valid and invalid, with `--json`
  variants to prove a diagnostic never reaches stdout.
* ``cap`` — whether every trimmed row of one view obeys one cap: grep match rows
  against `-C` windows, and tool-result bodies against text bodies.
* ``bypass`` — the views that are documented to ignore the budget entirely.

Each file records the invocation, the environment that differed, the exit code,
stdout and stderr, plus a measured `rows:` line giving the longest stdout row and
which trim markers appeared, because a cap change shows up in those numbers before
it shows up in the text.

    uv run python capture_caps.py --output evidence-slice-21/before --source /tmp/b21
    uv run python capture_caps.py --output evidence-slice-21/after
"""

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import fixture_caps

N = fixture_caps.NEEDLE

FLAG_CASES = [
    ("show-budget-negative", ["show", "--budget", "-1"], {}),
    ("show-line-limit-negative", ["show", "--line-limit", "-1"], {}),
    ("show-budget-zero", ["show", "--budget", "0"], {}),
    ("show-budget-small", ["show", "--budget", "500"], {}),
    ("show-line-limit-zero", ["show", "--line-limit", "0", "--budget", "500"], {}),
    ("show-line-limit-60", ["show", "--line-limit", "60", "--budget", "500"], {}),
    ("prompts-budget-negative", ["prompts", "--budget", "-1"], {}),
    ("prompts-line-limit-negative", ["prompts", "--line-limit", "-1"], {}),
    ("prompts-budget-60", ["prompts", "--budget", "60"], {}),
    ("prompts-line-limit-60", ["prompts", "--line-limit", "60"], {}),
    ("grep-budget-negative", ["grep", N, "--budget", "-1"], {}),
    ("grep-budget-zero", ["grep", N, "--budget", "0"], {}),
    ("grep-budget-400", ["grep", N, "--budget", "400"], {}),
    ("errors-compact", ["errors", "--compact"], {}),
    ("errors-plain", ["errors"], {}),
]

ENV_CASES = [
    ("budget-garbage-show", ["show"], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-show-json", ["show", "--json"], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-grep", ["grep", N], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-grep-json", ["grep", N, "--json"], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-prompts", ["prompts"], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-list", ["list"], {"SXR_BUDGET": "abc"}),
    ("budget-garbage-cmds", ["cmds"], {"SXR_BUDGET": "abc"}),
    ("budget-negative-show", ["show"], {"SXR_BUDGET": "-5"}),
    ("budget-empty-show", ["show"], {"SXR_BUDGET": ""}),
    ("budget-float-show", ["show"], {"SXR_BUDGET": "1.5"}),
    ("budget-zero-show", ["show"], {"SXR_BUDGET": "0"}),
    ("budget-500-show", ["show"], {"SXR_BUDGET": "500"}),
    ("budget-500-flag-wins", ["show", "--budget", "0"], {"SXR_BUDGET": "500"}),
    ("line-limit-garbage-show", ["show", "--budget", "500"], {"SXR_LINE_LIMIT": "abc"}),
    ("line-limit-garbage-json", ["show", "--json"], {"SXR_LINE_LIMIT": "abc"}),
    ("line-limit-negative-show", ["show", "--budget", "500"], {"SXR_LINE_LIMIT": "-5"}),
    ("line-limit-60-show", ["show", "--budget", "500"], {"SXR_LINE_LIMIT": "60"}),
    (
        "line-limit-60-flag-wins",
        ["show", "--budget", "500", "--line-limit", "0"],
        {"SXR_LINE_LIMIT": "60"},
    ),
    ("both-garbage-show", ["show"], {"SXR_BUDGET": "abc", "SXR_LINE_LIMIT": "abc"}),
    (
        "both-garbage-errors",
        ["errors", "--compact"],
        {"SXR_BUDGET": "abc", "SXR_LINE_LIMIT": "abc"},
    ),
]

CAP_CASES = [
    ("grep-rows-default", ["grep", N], {}),
    ("grep-rows-limit-60", ["grep", N], {"SXR_LINE_LIMIT": "60"}),
    ("grep-rows-limit-400", ["grep", N], {"SXR_LINE_LIMIT": "400"}),
    ("grep-rows-limit-zero", ["grep", N], {"SXR_LINE_LIMIT": "0"}),
    ("grep-context-default", ["grep", N, "-C", "1"], {}),
    ("grep-context-limit-60", ["grep", N, "-C", "1"], {"SXR_LINE_LIMIT": "60"}),
    ("grep-context-limit-400", ["grep", N, "-C", "1"], {"SXR_LINE_LIMIT": "400"}),
    ("cmds-default", ["cmds"], {}),
    ("cmds-limit-60", ["cmds"], {"SXR_LINE_LIMIT": "60"}),
    ("show-trimmed-default", ["show", "--budget", "500"], {}),
    ("show-trimmed-limit-60", ["show", "--budget", "500"], {"SXR_LINE_LIMIT": "60"}),
    ("show-trimmed-limit-400", ["show", "--budget", "500"], {"SXR_LINE_LIMIT": "400"}),
    (
        "show-tool-results-limit-60",
        ["show", "--budget", "500", "--tool-results"],
        {"SXR_LINE_LIMIT": "60"},
    ),
    ("errors-compact-limit-60", ["errors", "--compact"], {"SXR_LINE_LIMIT": "60"}),
    ("errors-compact-limit-400", ["errors", "--compact"], {"SXR_LINE_LIMIT": "400"}),
    ("prompts-compact-limit-60", ["prompts", "--budget", "60"], {"SXR_LINE_LIMIT": "60"}),
]

BYPASS_CASES = [
    ("show-full", ["show", "--full"], {"SXR_BUDGET": "500"}),
    ("show-around", ["show", "--around", "2", "--context", "1"], {"SXR_BUDGET": "500"}),
    ("show-range", ["show", "--range", "1:3"], {"SXR_BUDGET": "500"}),
    ("show-json", ["show", "--json"], {"SXR_BUDGET": "500"}),
    ("show-tail", ["show", "--tail", "2"], {"SXR_BUDGET": "500"}),
    ("prompts-plain", ["prompts"], {"SXR_BUDGET": "500"}),
    ("errors-plain-budget", ["errors"], {"SXR_BUDGET": "500"}),
    ("grep-json-budget", ["grep", N, "--json"], {"SXR_BUDGET": "500"}),
]

GROUPS = [("flag", FLAG_CASES), ("env", ENV_CASES), ("cap", CAP_CASES), ("bypass", BYPASS_CASES)]


def _measure(body: str) -> str:
    """Lengths and trim markers, which move before the visible text does."""
    rows = [line for line in body.splitlines() if line]
    if not rows:
        return "no stdout rows"
    longest = max(len(row) for row in rows)
    marks = [name for name in ("chars]", "chars, middle]") if name in body]
    return f"{len(rows)} rows, longest {longest}, markers {marks or 'none'}"


def _json_health(body: str) -> str:
    """Whether every stdout line parses, recorded next to the output itself."""
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


def _run(provider: str, root: Path, args: list, env: dict) -> str:
    """Invoke one case in a fresh cache root and return its recorded transcript.

    The unusable-env notice is deduplicated per process, which is right for a CLI
    where every invocation is its own process but wrong for a harness that runs a
    hundred cases in one: the first case to see a bad SXR_BUDGET would be the only
    one to report it. Each case therefore starts with that memory cleared, so a
    capture shows what a real shell invocation shows. The reset is looked up rather
    than imported because the baseline tree this also runs against predates it.
    """
    from typer.testing import CliRunner

    from sxr import util
    from sxr.cli import app

    getattr(util, "reset_env_notices", lambda: None)()

    argv = [*(["--codex"] if provider == "codex" else []), *args, "--path", fixture_caps.CWD]
    with tempfile.TemporaryDirectory(prefix="sxr-caps-cache-") as cache:
        saved = dict(os.environ)
        os.environ["SXR_CACHE_DIR"] = cache
        os.environ.pop("SXR_NO_CACHE", None)
        os.environ.pop("SXR_BUDGET", None)
        os.environ.pop("SXR_LINE_LIMIT", None)
        os.environ["CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME"] = str(root)
        os.environ.update(env)
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
    shown = " ".join(f"{k}={v!r}" for k, v in sorted(env.items())) or "(none)"
    lines = [f"$ sxr {' '.join(argv)}", f"env: {shown}", f"exit={result.exit_code}"]
    lines.append(f"rows: {_measure(body)}")
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
        with tempfile.TemporaryDirectory(prefix=f"sxr-caps-{provider}-") as directory:
            root = Path(directory)
            getattr(fixture_caps, provider)(root)
            for group, cases in GROUPS:
                for name, case, env in cases:
                    target = args.output / f"{group}-{provider}-{name}.txt"
                    target.write_text(_run(provider, root, case, env))
                    written += 1
    print(f"wrote {written} captures to {args.output}")


if __name__ == "__main__":
    main()
