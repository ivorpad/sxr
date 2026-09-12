"""Re-verify the historical PROMPTS-filter contract under the migrated flag names.

The 2026-09-10 contract suite is preserved unchanged, so its PROMPTS-filter case
still asserts the old `--all` selection meaning and now fails by design. This
script reuses the very same audit corpus to show that the contract's intent is
still met: the default view omits injected context, `--include-context` restores
every user-role record, and `--all` only lifts limits.

What the failing case costs is worth stating exactly. PROMPTS-filter passes both
on the audit base 48b11c6c and on the published 8f93114 that Homebrew installs
(measured by probe_upstream_contracts.py, evidence-M/upstream-contracts.json), so
the divergence is from a shipped release, not only from a preserved audit check.
The same measurement shows the published release failing 31 of the 67 cases this
tree passes, so the divergence is one case wide and runs the other way 31 times.

Run from this file's directory:
    uv run python verify_prompts.py --output evidence/migrated-contracts.json
"""

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / "2026-09-10"
sys.path.insert(0, str(AUDIT))

from audit_support import Corpus, code, json_lines, require  # noqa: E402


def default_view_omits_context(corpus):
    """Plain prompts still selects exactly the three human prompts."""
    result = corpus.file("prompts", "--json")
    code(result)
    require(
        len(json_lines(result)) == 3 and "injected fixture" not in result.stdout,
        "prompt selection wrong",
    )


def include_context_restores_records(corpus):
    """--include-context restores all six user-role records the old --all showed."""
    result = corpus.file("prompts", "--include-context", "--json")
    code(result)
    require(
        len(json_lines(result)) == 6, f"--include-context showed {len(json_lines(result))} records"
    )


def all_does_not_widen_selection(corpus):
    """--all leaves selection alone; it only lifts limits."""
    plain = corpus.file("prompts", "--json")
    lifted = corpus.file("prompts", "--all", "--json")
    code(lifted)
    require(plain.stdout == lifted.stdout, "--all changed which records qualify")


def all_lifts_an_explicit_row_limit(corpus):
    """--all overrides an explicit -n in the same invocation."""
    limited = corpus.file("prompts", "--json", "-n", "1")
    lifted = corpus.file("prompts", "--json", "-n", "1", "--all")
    code(lifted)
    require(len(json_lines(limited)) == 1, "-n 1 did not cap records")
    require(len(json_lines(lifted)) == 3, "--all did not lift -n 1")


def default_text_is_complete(corpus):
    """No environment budget can trim the plain text view."""
    result = corpus.file("prompts", env={"SXR_BUDGET": "1", "SXR_LINE_LIMIT": "10"})
    code(result)
    require("chars]" not in result.stdout, "environment budget trimmed the default view")


CHECKS = [
    ("PROMPTS-default-selection", default_view_omits_context),
    ("PROMPTS-include-context", include_context_restores_records),
    ("PROMPTS-all-keeps-selection", all_does_not_widen_selection),
    ("PROMPTS-all-lifts-limits", all_lifts_an_explicit_row_limit),
    ("PROMPTS-default-complete", default_text_is_complete),
]


def main():
    """Execute every migrated prompt contract in a fresh temporary corpus."""
    parser = argparse.ArgumentParser(description=__doc__)
    # Required for the same reason as verify_cli.py: this used to default into evidence/,
    # and one bare run rewrote slice 1's receipt there while slice 3 was under review.
    # See cli-refactor/ledger.md, "Known evidence gap", for who ran it and when.
    parser.add_argument(
        "--output", type=Path, required=True, help="Write the JSON receipt here (required)"
    )
    args = parser.parse_args()
    results = []
    for identity, check in CHECKS:
        with tempfile.TemporaryDirectory(prefix="sxr-slice-", dir="/private/tmp") as directory:
            corpus = Corpus(directory)
            started = datetime.now(UTC)
            try:
                check(corpus)
                status, detail = "passed", ""
            except Exception as exc:
                status, detail = "failed", f"{type(exc).__name__}: {exc}"
            payload = json.dumps(
                dict(
                    id=identity,
                    status=status,
                    detail=detail,
                    duration_seconds=(datetime.now(UTC) - started).total_seconds(),
                    calls=corpus.calls,
                )
            ).replace(directory, "<fixture-root>")
            results.append(json.loads(payload))
            print(f"{status.upper()} {identity}" + (f": {detail}" if detail else ""), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            dict(
                generated_at=datetime.now(UTC).isoformat(),
                passed=sum(r["status"] == "passed" for r in results),
                failed=sum(r["status"] == "failed" for r in results),
                results=results,
            ),
            indent=2,
        )
        + "\n"
    )
    raise SystemExit(int(any(r["status"] == "failed" for r in results)))


if __name__ == "__main__":
    main()
