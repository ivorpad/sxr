"""Join expected features, executed checks and issue reports into JSON and CSV."""

import ast
import csv
import fnmatch
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from render_report import render
from surface_inventory import inventory

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]

AREA_SOURCES = {
    "cli": "src/sxr/cli.py",
    "output": "src/sxr/onboard.py",
    "list": "src/sxr/views_info.py",
    "selection": "src/sxr/handles.py",
    "scope": "src/sxr/discovery_scope.py",
    "show": "src/sxr/views_read.py",
    "prompts": "src/sxr/views_read.py",
    "cmds": "src/sxr/views_info.py",
    "errors": "src/sxr/views_read.py",
    "tools": "src/sxr/views_info.py",
    "stats": "src/sxr/views_info.py",
    "path": "src/sxr/views_info.py",
    "grep": "src/sxr/views_grep.py",
    "find": "src/sxr/find_service.py",
    "index": "src/sxr/search_index.py",
    "providers": "src/sxr/providers/codex.py",
    "secrets": "src/sxr/views_secrets.py",
    "clean": "src/sxr/secrets/clean.py",
    "skills": "src/sxr/skills_cli.py",
    "init": "src/sxr/onboard.py",
    "worker": "src/sxr/find_worker.py",
    "distribution": "packaging/verify.py",
    "performance": "README.md",
}

UNVERIFIED = {
    "BUILD-OTHER-PLATFORMS": "No Linux or x86_64 host is available in this audit. "
    "The documented macOS 14/15 and Ubuntu 22.04 compatibility matrix was not rerun.",
    "INSTALL-HOMEBREW": "No Homebrew install/upgrade was performed. The fresh local archive "
    "was tested independently of any published formula or release.",
    "PERFORMANCE-RELEASE": "Historical RTK/rg timing claims were not rerun against their "
    "private 738-file benchmark corpus. Functional cache and worker tests are separate evidence.",
}


def read_json(path):
    """Read one evidence file."""
    return json.loads((BASE / path).read_text())


def test_results():
    """Preserve all test attempts and use the final worker rerun for effective status."""
    results = {}
    for file in ("pytest.xml", "worker.xml"):
        for case in ET.parse(BASE / "evidence" / file).getroot().iter("testcase"):
            node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
            status = "passed"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "failed"
            elif case.find("skipped") is not None:
                status = "skipped"
            attempt = dict(
                status=status,
                evidence=f"evidence/{file}",
                duration_seconds=float(case.attrib["time"]),
            )
            result = results.setdefault(node, dict(id=node, attempts=[]))
            result["attempts"].append(attempt)
            result["status"] = status
    return results


def resolve_tests(selectors, tests):
    """Expand every selector and fail generation if any reference is stale."""
    selected = set()
    for selector in selectors:
        matches = [
            name for name in tests if fnmatch.fnmatchcase(name.removeprefix("tests/"), selector)
        ]
        if not matches:
            raise ValueError(f"No executed test matches {selector}")
        selected.update(matches)
    return sorted(selected)


def source_reference(value):
    """Resolve function, class or module-level assignment to an exact source line."""
    file, symbol = value.split(":", 1)
    tree = ast.parse((REPO / file).read_text())
    for node in ast.walk(tree):
        if getattr(node, "name", None) == symbol:
            return dict(path=file, line=node.lineno, symbol=symbol)
        if isinstance(node, ast.Name) and node.id == symbol and isinstance(node.ctx, ast.Store):
            return dict(path=file, line=node.lineno, symbol=symbol)
    raise ValueError(f"Source symbol not found: {value}")


def issues_with_evidence(contracts, tests):
    """Attach reproductions, source locations and exact failing check IDs to each report."""
    issues = read_json("issue-specifications.json")
    for issue in issues:
        prefixes = issue.pop("check_prefixes")
        issue["check_ids"] = [
            c["id"] for c in contracts if any(c["id"].startswith(p) for p in prefixes)
        ]
        issue["sources"] = [source_reference(s) for s in issue.pop("source_symbols")]
        issue["test_ids"] = resolve_tests(issue.pop("pytest_selectors", []), tests)
        issue["report"] = f"issues/{issue['id']}.md"
        issue["feature_ids"] = issue.get("feature_ids", [])
        issue["reproduce"] = [
            f"rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check {prefix} "
            "--output /private/tmp/sxr-audit-repro.json"
            for prefix in prefixes
        ]
        if not issue["check_ids"] and not issue["test_ids"]:
            raise ValueError(f"Issue has no executed evidence: {issue['id']}")
    return issues


def feature_rows(tests, contracts, issues, external):
    """Evaluate features without promoting untested assertions to a pass."""
    result = []
    with (BASE / "feature-specifications.psv").open() as stream:
        rows = csv.DictReader(stream, delimiter="|")
        for row in rows:
            selectors = list(filter(None, row.pop("pytest_selectors").split(";")))
            prefixes = list(filter(None, row.pop("contract_prefixes").split(";")))
            row["test_ids"] = resolve_tests(selectors, tests)
            selected = [c for c in contracts if any(c["id"].startswith(p) for p in prefixes)]
            for prefix in prefixes:
                if not any(c["id"].startswith(prefix) for c in selected):
                    raise ValueError(f"No executed contract matches {prefix}")
            row["check_ids"] = [c["id"] for c in selected]
            associated = [
                issue
                for issue in issues
                if row["id"] in issue["feature_ids"]
                or set(row["check_ids"]) & set(issue["check_ids"])
            ]
            row["issue_ids"] = [issue["id"] for issue in associated]
            for issue in associated:
                if row["id"] not in issue["feature_ids"]:
                    issue["feature_ids"].append(row["id"])
            statuses = [tests[t]["status"] for t in row["test_ids"]]
            statuses.extend(c["status"] for c in selected)
            if associated or "failed" in statuses:
                row["status"] = "failed"
            elif statuses and all(s == "passed" for s in statuses):
                row["status"] = "passed"
            else:
                row["status"] = "not_verified"
            row["source_refs"] = ["README.md", AREA_SOURCES[row["area"]]]
            row["verification_note"] = ""
            if row["id"] in UNVERIFIED:
                row["status"] = "not_verified"
                row["verification_note"] = UNVERIFIED[row["id"]]
            if row["id"] == "BUILD-MACOS-ARM64":
                row["status"] = external["bundle"]["status"]
                row["verification_note"] = "Built current sources and ran packaging/verify.py "
                row["verification_note"] += "after relocation on this host with an empty PATH. "
                row["verification_note"] += "See evidence/build.log and evidence/bundle.log."
            result.append(row)
    return result


def write_csv(features):
    """Provide a filterable flat view while keeping detailed evidence in JSON."""
    fields = [
        "id",
        "area",
        "expected_behavior",
        "status",
        "issue_ids",
        "check_ids",
        "test_count",
        "test_ids",
        "source_refs",
        "verification_note",
    ]
    with (BASE / "features.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for feature in features:
            row = {key: feature[key] for key in fields if key in feature}
            row["test_count"] = len(feature["test_ids"])
            writer.writerow(
                {
                    key: "; ".join(value) if isinstance(value, list) else value
                    for key, value in row.items()
                }
            )


def main():
    """Regenerate reports only after checking references and source consistency."""
    tests = test_results()
    contract_data = read_json("evidence/contracts.json")
    contracts = contract_data["results"]
    external = read_json("evidence/external-checks.json")
    issues = issues_with_evidence(contracts, tests)
    features = feature_rows(tests, contracts, issues, external)
    surface = inventory()
    feature_ids = {feature["id"] for feature in features}
    unknown = [
        f"{c['command']}:{p['name']}"
        for c in surface
        for p in c["parameters"]
        if not p["feature_ids"] or not set(p["feature_ids"]) <= feature_ids
    ]
    if unknown:
        raise ValueError(f"Unmapped CLI parameters: {unknown}")
    reported = {c for issue in issues for c in issue["check_ids"]}
    orphan_failures = [
        c["id"] for c in contracts if c["status"] == "failed" and c["id"] not in reported
    ]
    if orphan_failures:
        raise ValueError(f"Failures without reports: {orphan_failures}")
    baseline = read_json("evidence/baseline.json")
    changed = [
        name
        for name, digest in baseline["files"].items()
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != digest
    ]
    if changed:
        raise ValueError(f"Audited source changed; evidence needs refresh: {changed}")
    data = dict(
        schema_version=1,
        generated_at=datetime.now(UTC).isoformat(),
        target=dict(
            commit=baseline["commit"],
            version="0.12.2",
            working_tree=True,
            baseline="evidence/baseline.json",
            original_files_unchanged=True,
            python=baseline["python"],
            sqlite=baseline["sqlite"],
            platform=baseline["platform"],
        ),
        scope="Current working tree, including pre-existing uncommitted changes. "
        "Source and native worker tests plus isolated subprocess contracts. "
        "Passing rows mean the linked checks passed, not proof of every possible input.",
        status_definitions=dict(
            passed="Linked executed checks passed within their stated scope.",
            failed="A reproduced failure or confirmed documentation conflict exists.",
            not_verified="Required environment or evidence is unavailable; no pass claimed.",
        ),
        summary=dict(
            features=dict(Counter(f["status"] for f in features)),
            tests=dict(Counter(t["status"] for t in tests.values())),
            contract_checks=dict(Counter(c["status"] for c in contracts)),
            issue_count=len(issues),
            issue_priorities=dict(Counter(i["priority"] for i in issues)),
            parser_surfaces=len(surface),
            parameters=sum(len(c["parameters"]) for c in surface),
        ),
        features=features,
        issues=issues,
        cli_surface=surface,
        tests=list(tests.values()),
        external_checks=external,
    )
    for name, value in (
        ("features.json", data),
        ("issues.json", issues),
        ("cli-surface.json", surface),
    ):
        (BASE / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n"
        )
    write_csv(features)
    render(BASE, data, contracts)
    print(json.dumps(data["summary"], indent=2))


if __name__ == "__main__":
    sys.exit(main())
