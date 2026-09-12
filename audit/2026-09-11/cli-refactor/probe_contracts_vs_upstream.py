"""Run the five migrated prompt contracts against HEAD, this tree, and upstream.

Read-only with respect to git. Each comparison tree is materialized from a ref
with `git archive` into a temp directory; no worktree, checkout, index or HEAD
operation happens. `audit_support.Corpus` pins PYTHONPATH to this repository's
`src`, so `audit_support.REPO` is patched in memory before each corpus is built,
which is the only way to point the same checks at another tree.

    uv run python probe_contracts_vs_upstream.py --output evidence-06/contracts-vs-upstream.log
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "audit" / "2026-09-10"))

import audit_support  # noqa: E402
from verify_prompts import CHECKS  # noqa: E402


def materialize(ref: str, directory: Path) -> Path:
    """Extract one git ref into a temp directory and return its repository root."""
    target = directory / ref.replace("/", "-")
    target.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", ref], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(target)], input=archive, check=True)
    return target


def run_checks(tree: Path) -> list[tuple[str, str, str]]:
    """(check id, status, detail) for every migrated prompt contract in one tree."""
    original = audit_support.REPO
    audit_support.REPO = tree
    audit_support.SOURCE_CLI = [
        str(original / ".venv/bin/python"),
        "-c",
        "from sxr import main; main()",
    ]
    results = []
    try:
        for identity, check in CHECKS:
            with tempfile.TemporaryDirectory(prefix="sxr-cmp-", dir="/private/tmp") as directory:
                corpus = audit_support.Corpus(directory)
                try:
                    check(corpus)
                    results.append((identity, "passed", ""))
                except Exception as exc:  # noqa: BLE001 - the status is the measurement
                    detail = f"{type(exc).__name__}: {exc}".replace(directory, "<fixture>")
                    results.append((identity, "failed", detail[:200]))
    finally:
        audit_support.REPO = original
    return results


def main() -> int:
    """Write a per-tree table of the five contracts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the log")
    args = parser.parse_args()

    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    upstream = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "origin/HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    lines = [
        "The five migrated prompt contracts (verify_prompts.py), per tree",
        "",
        f"HEAD = {head}, upstream = origin/HEAD = {upstream}.",
        "'this tree' is the working tree carrying slices 1 through 5.",
        "",
    ]
    table: dict[str, list[tuple[str, str, str]]] = {}
    with tempfile.TemporaryDirectory(prefix="sxr-refs-") as directory:
        base = Path(directory)
        table[f"HEAD {head}"] = run_checks(materialize("HEAD", base))
        table["this tree"] = run_checks(REPO)
        table[f"upstream {upstream}"] = run_checks(materialize("origin/HEAD", base))

    ids = [identity for identity, _ in CHECKS]
    lines.append(f"{'contract':30s} " + " ".join(f"{name:20s}" for name in table))
    lines.append("-" * 96)
    for identity in ids:
        row = f"{identity:30s} "
        for name in table:
            status = next(s for i, s, _ in table[name] if i == identity)
            row += f"{status:20s} "
        lines.append(row.rstrip())
    lines.append("")
    for name, results in table.items():
        failed = [(i, d) for i, s, d in results if s == "failed"]
        lines.append(f"{name}: {len(results) - len(failed)} passed, {len(failed)} failed")
        for identity, detail in failed:
            lines.append(f"    {identity}: {detail}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    args.output.with_suffix(".json").write_text(
        json.dumps(
            {k: [dict(id=i, status=s, detail=d) for i, s, d in v] for k, v in table.items()},
            indent=2,
        )
        + "\n"
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
