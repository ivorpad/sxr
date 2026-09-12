"""Derive a fresh remediation report without rewriting the historical audit."""

import argparse
import csv
import fnmatch
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime

from capture import BASE, REPO, identity


def read(name):
    """Read JSON relative to the remediation directory."""
    return json.loads((BASE / name).read_text())


def write(name, data):
    """Write a derived view in the remediation directory only."""
    (BASE / name).write_text(json.dumps(data, indent=2) + "\n")


def verified_run(name):
    """Reject stale source identity, changed artifacts and unsuccessful commands."""
    run = read(f"{name}.run.json")
    if run["exit_code"] or not run["source_unchanged"]:
        raise ValueError(f"Unsuccessful or changing-source run: {name}")
    recorded, current = read(run["source_identity"]), identity()
    # Rendering changes do not invalidate executed code. Every implementation,
    # test, harness and capture input must still match its recorded hash.
    renderer = str((BASE / "report.py").relative_to(REPO))
    recorded["files"].pop(renderer)
    current["files"].pop(renderer)
    if recorded != current:
        raise ValueError(f"Source changed since {name}; rerun verification")
    for artifact, digest in run["artifacts"].items():
        if hashlib.sha256((BASE / artifact).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Evidence changed after {name}: {artifact}")
    return run


def test_results(path):
    """Retain exact executed pytest IDs and statuses from this suite, including skips."""
    result = {}
    for case in ET.parse(BASE / path).getroot().iter("testcase"):
        name = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        status = "passed"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "failed"
        elif case.find("skipped") is not None:
            status = "skipped"
        result[name] = dict(status=status, evidence=path)
    if not result:
        raise ValueError("No executed tests")
    return result


def expand(selectors, tests):
    """Resolve regression selectors and reject references to unexecuted tests."""
    found = set()
    for selector in selectors:
        matches = {
            name
            for name in tests
            if name.removeprefix("tests/") == selector
            or fnmatch.fnmatchcase(name.removeprefix("tests/"), selector)
        }
        if not matches:
            raise ValueError(f"No executed regression test: {selector}")
        found.update(matches)
    return sorted(found)


def documentation():
    """Record the actual wording of the retained empty-list exception in all three surfaces."""
    from sxr.onboard import EPILOG, PRIMER_BODY

    readme = (REPO / "README.md").read_text()
    surfaces = {
        "README.md": (readme, "Listing is the exception:", "return 0 even"),
        "src/sxr/onboard.py:EPILOG": (EPILOG, "exit 0", "list also succeeds when empty"),
        "src/sxr/onboard.py:PRIMER_BODY": (
            PRIMER_BODY,
            "Exit codes:",
            "0 content (also an empty list)",
        ),
    }
    observations = []
    for surface, (text, start, required) in surfaces.items():
        if required not in text:
            raise ValueError(f"Missing empty-list documentation: {surface}")
        offset = text.index(start)
        observations.append(dict(surface=surface, excerpt=text[offset : offset + 260]))
    write("documentation-review.json", dict(status="passed", observations=observations))


def resolutions(tests, contracts, contract_file, notes, suite_xml):
    """A resolution needs a decision, passing reproductions and passing maintained tests."""
    originals = read("../issues.json")
    before = {r["id"]: r for r in read("after-secrets-contracts.json")["results"]}
    before.update(
        {
            r["id"]: r
            for name in ("before-001.json", "before-014.json")
            for r in read(name)["results"]
        }
    )
    result = {}
    for issue in originals:
        row = dict(notes[issue["id"]])
        row["regression_tests"] = expand(row.pop("regression_selectors"), tests)
        passed = all(tests[t]["status"] == "passed" for t in row["regression_tests"])
        passed &= all(contracts[c]["status"] == "passed" for c in row["check_ids"])
        if not row["decision"] or not row["regression_tests"] or not passed:
            raise ValueError(f"Resolution lacks passing evidence: {issue['id']}")
        row.update(
            title=issue["title"],
            priority=issue["priority"],
            status="resolved",
            test_evidence=suite_xml,
            reproduction_evidence=contract_file,
            before_results={c: before[c]["status"] for c in row["check_ids"]},
            after_results={c: contracts[c]["status"] for c in row["check_ids"]},
        )
        if issue["id"] == "SXR-AUD-017":
            row["documentation_evidence"] = "documentation-review.json"
        result[issue["id"]] = row
    return result


def features(baseline, tests, contracts, resolved, bundle, suite_xml):
    """Compute current status from linked evidence, retaining untested platform exclusions."""
    rows = []
    for original in baseline["features"]:
        row = dict(original, baseline_status=original["status"])
        row["test_ids"] = sorted(
            set(row["test_ids"])
            | {t for issue in row["issue_ids"] for t in resolved[issue]["regression_tests"]}
        )
        missing = set(row["test_ids"]) - tests.keys()
        if missing:
            raise ValueError(f"Unexecuted feature tests: {row['id']}: {missing}")
        statuses = [tests[t]["status"] for t in row["test_ids"]]
        statuses.extend(contracts[c]["status"] for c in row["check_ids"])
        row["status"] = (
            "failed"
            if "failed" in statuses
            else "passed"
            if statuses and all(s == "passed" for s in statuses)
            else "not_verified"
        )
        row["evidence"] = [suite_xml] if row["test_ids"] else []
        if row["check_ids"]:
            row["evidence"].append("final-contracts.json")
        if row["issue_ids"]:
            row["evidence"].append("resolutions.json")
        if original["status"] == "not_verified":
            row["status"] = "not_verified"
        if row["id"] == "BUILD-MACOS-ARM64":
            row["status"] = "passed"
            row["evidence"] = [bundle["evidence"]]
            row["verification_note"] = (
                "Fresh macOS arm64 bundle passed relocation verification with an empty PATH."
            )
        rows.append(row)
    return rows


def render(data):
    """Write a compact human index and a filterable feature table."""
    with (BASE / "features.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, ["id", "area", "status", "baseline_status", "issue_ids", "evidence"]
        )
        writer.writeheader()
        for row in data["features"]:
            writer.writerow(
                {
                    key: "; ".join(row[key]) if isinstance(row[key], list) else row[key]
                    for key in writer.fieldnames
                }
            )
    summary = data["summary"]
    lines = [
        "# Audit remediation",
        "",
        f"Resolved {len(data['resolutions'])} findings. The fresh suite has "
        f"{summary['tests'].get('passed', 0)} passing tests; all "
        f"{summary['contracts'].get('passed', 0)} CLI contracts pass.",
        "",
        "[Issue dispositions and regression tests](resolutions.json) · "
        "[Current feature map](features.json) · [Feature table](features.csv) · "
        "[Verification runs](verification.json)",
        "",
        "The original audit remains unchanged. Each verification run records its source "
        "hashes, exit code and output hashes. This report rejects changed source or evidence.",
        "",
        "| Issue | Disposition | Change |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {key} | {row['disposition']} | {row['decision']} |"
        for key, row in data["resolutions"].items()
    )
    lines.extend(
        [
            "",
            "The macOS arm64 bundle passed relocation verification with an empty PATH. "
            "Linux/x86_64, older OS compatibility, Homebrew installation and historical "
            "benchmarks remain unverified. See the feature map for the exact exclusions.",
            "",
            "Behavior choices: negative row limits and tails return 2; -n 0 is unlimited; "
            "--tail 0 selects no events and returns 1. Empty listing retains exit 0. "
            "Cleaning row limits affect reporting, while every selected file is processed.",
            "",
        ]
    )
    (BASE / "README.md").write_text("\n".join(lines))


def main():
    """Require fresh suite, CLI and bundle checks before deriving current statuses."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks", default="final-checks")
    parser.add_argument("--contracts", default="final-contracts")
    parser.add_argument("--build", default="bundle-build")
    parser.add_argument("--bundle", default="bundle-verify")
    parser.add_argument("--suite-xml", default="pytest-final.xml")
    args = parser.parse_args()
    runs = {
        key: verified_run(getattr(args, key)) for key in ("checks", "contracts", "build", "bundle")
    }
    if args.suite_xml not in runs["checks"]["artifacts"]:
        raise ValueError("Suite XML was not captured with the repository checks")
    if "final-contracts.json" not in runs["contracts"]["artifacts"]:
        raise ValueError("Contract results were not captured with the CLI checks")
    for path, digest in read("historical-files.json").items():
        if hashlib.sha256((BASE.parent / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Historical evidence was changed: {path}")
    baseline = read("../features.json")
    tests = test_results(args.suite_xml)
    contracts = {row["id"]: row for row in read("final-contracts.json")["results"]}
    if len(contracts) != 67 or any(row["status"] != "passed" for row in contracts.values()):
        raise ValueError("The full contract set has not passed")
    documentation()
    resolved = resolutions(
        tests, contracts, "final-contracts.json", read("resolution-notes.json"), args.suite_xml
    )
    rows = features(baseline, tests, contracts, resolved, runs["bundle"], args.suite_xml)
    data = dict(
        generated_at=datetime.now(UTC).isoformat(),
        historical_baseline="../features.json",
        source_identity=runs["checks"]["source_identity"],
        renderer_sha256=hashlib.sha256((BASE / "report.py").read_bytes()).hexdigest(),
        features=rows,
        resolutions=resolved,
        summary=dict(
            features=dict(Counter(r["status"] for r in rows)),
            tests=dict(Counter(r["status"] for r in tests.values())),
            contracts=dict(Counter(r["status"] for r in contracts.values())),
        ),
    )
    write("verification.json", runs)
    write("resolutions.json", resolved)
    write("features.json", data)
    render(data)
    print(json.dumps(data["summary"]))


if __name__ == "__main__":
    main()
