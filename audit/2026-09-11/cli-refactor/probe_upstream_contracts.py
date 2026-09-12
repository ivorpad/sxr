"""Run the preserved 2026-09-10 contract suite against a materialized upstream ref.

Answers two questions with numbers instead of reasoning: whether PROMPTS-filter
actually passes on the published release, and how much of the 17-finding
remediation the published release is missing. The ref is extracted with
`git archive` into a temp directory and the audit corpus is pointed at it by
patching audit_support.REPO; the repository's own venv still supplies the
interpreter, so nothing is installed and nothing is checked out.

    uv run python probe_upstream_contracts.py --output evidence-M/upstream-contracts.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AUDIT = REPO / "audit/2026-09-10"
REFS = {
    "base-48b11c6c": "48b11c6cf08200de363e108924e42fdbc52d83e8",
    "published-8f93114": "8f93114f8a1712cc7f02f2cfb91cf10d3040bb04",
}


def materialize(ref: str, directory: Path) -> Path:
    """Extract one ref's tree into directory; returns the tree root."""
    target = directory / ref[:8]
    target.mkdir(parents=True)
    archive = target / "tree.tar"
    with archive.open("wb") as handle:
        subprocess.run(["git", "-C", str(REPO), "archive", ref], stdout=handle, check=True)
    subprocess.run(["tar", "-x", "-C", str(target), "-f", str(archive)], check=True)
    return target


def suite(tree: Path) -> dict:
    """Every contract case against one tree, as {id: {ok, detail}}.

    One fresh corpus per check, exactly as verify_cli.py does it, so a check that
    mutates its fixture cannot influence the next one.
    """
    sys.path.insert(0, str(AUDIT))
    import audit_support
    import contract_checks

    original = audit_support.REPO
    audit_support.REPO = tree
    try:
        outcome = {}
        for name, description, check in contract_checks.CHECKS:
            with tempfile.TemporaryDirectory(prefix="sxr-contract-", dir="/private/tmp") as tmp:
                try:
                    check(audit_support.Corpus(tmp))
                except Exception as exc:  # noqa: BLE001 - a failing contract is data here
                    detail = f"{type(exc).__name__}: {exc}"
                    outcome[name] = {"ok": False, "detail": detail[:200], "about": description}
                else:
                    outcome[name] = {"ok": True, "detail": "", "about": description}
        return outcome
    finally:
        audit_support.REPO = original


def main() -> int:
    """Run the suite against each ref and against this tree, and compare."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the JSON")
    args = parser.parse_args()

    report = {}
    with tempfile.TemporaryDirectory(prefix="sxr-refs-") as directory:
        for label, ref in REFS.items():
            report[label] = suite(materialize(ref, Path(directory)))
    report["this-tree"] = suite(REPO)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")

    names = list(report["this-tree"])
    for label in report:
        failed = [n for n in names if not report[label][n]["ok"]]
        print(f"{label:20} {len(names) - len(failed):>3} passed, {len(failed):>3} failed")
    print("\n### PROMPTS-filter, the deliberate divergence")
    for label in report:
        case = report[label]["PROMPTS-filter"]
        print(f"  {label:20} {'passes' if case['ok'] else 'FAILS'}  {case['detail']}")
    print("\n### cases this tree passes and the published release does not")
    gap = [
        n
        for n in names
        if report["this-tree"][n]["ok"] and not report["published-8f93114"][n]["ok"]
    ]
    for name in gap:
        print(f"  {name}: {report['published-8f93114'][name]['detail'][:90]}")
    print(f"  ({len(gap)} cases)")
    print("\n### cases the published release passes and this tree does not")
    reverse = [
        n
        for n in names
        if report["published-8f93114"][n]["ok"] and not report["this-tree"][n]["ok"]
    ]
    for name in reverse:
        print(f"  {name}: {report['this-tree'][name]['detail'][:90]}")
    print(f"  ({len(reverse)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
