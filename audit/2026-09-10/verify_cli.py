"""Run repeatable CLI contract checks and retain failures as audit evidence."""

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from audit_support import SYNTHETIC_PASSWORD, Corpus
from contract_checks import CHECKS


def main():
    """Execute all checks, or one issue's reproduction, in fresh temporary stores."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", help="Run check IDs starting with this value")
    # Required on purpose. This used to default to evidence/contracts.json, so one bare
    # run destroyed the preserved audit-time baseline there (see cli-refactor/ledger.md,
    # "Known evidence gap"). Naming the destination is now the caller's job.
    parser.add_argument(
        "--output", type=Path, required=True, help="Write the JSON receipt here (required)"
    )
    args = parser.parse_args()
    results = []
    for identity, expectation, check in CHECKS:
        if args.check and not identity.startswith(args.check):
            continue
        with tempfile.TemporaryDirectory(prefix="sxr-audit-", dir="/private/tmp") as directory:
            corpus = Corpus(directory)
            started = datetime.now(UTC)
            try:
                check(corpus)
                status, detail = "passed", ""
            except Exception as exc:
                status, detail = "failed", f"{type(exc).__name__}: {exc}"
            result = dict(
                id=identity,
                expected=expectation,
                status=status,
                detail=detail,
                duration_seconds=(datetime.now(UTC) - started).total_seconds(),
                calls=corpus.calls,
            )
            # These are synthetic inputs, but keep credential-shaped values out of reports.
            serialized = json.dumps(result).replace(SYNTHETIC_PASSWORD, "<synthetic-password>")
            serialized = serialized.replace(directory, "<fixture-root>")
            results.append(json.loads(serialized))
            print(f"{status.upper()} {identity}" + (f": {detail}" if detail else ""), flush=True)
    if not results:
        parser.error("no matching checks")
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
