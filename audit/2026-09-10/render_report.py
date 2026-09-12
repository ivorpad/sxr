"""Render reviewable Markdown from the evidence-backed audit inventory."""

import shlex


def issue_document(base, issue, contracts):
    """Write one fix-ready report with a reproduction and acceptance criteria."""
    lines = [
        f"# {issue['id']}: {issue['title']}",
        "",
        f"{issue['priority']} · Open · Audited working tree based on `48b11c6`",
        "",
        issue["impact"],
        "",
        f"**Expected:** {issue['expected']}",
        "",
        f"**Observed:** {issue['observed']}",
        "",
        f"**Requirement basis:** {issue['requirement_basis']}",
        "",
        "Reproduce from the repository root. The harness uses temporary synthetic files "
        "and records each CLI exit code, stdout and stderr. A failing contract makes the "
        "harness exit 1.",
        "",
    ]
    if issue["reproduce"]:
        lines.extend(["```bash", *issue["reproduce"], "```", ""])
    else:
        lines.extend(
            [
                "```bash",
                "rtk proxy .venv/bin/python -m pytest " + " ".join(issue["test_ids"]),
                "```",
                "",
                "This existing test passes and confirms the implemented exception. "
                "The discrepancy is in the global exit-code documentation.",
                "",
            ]
        )
    selected = [c for c in contracts if c["id"] in issue["check_ids"]]
    if selected:
        lines.extend(["| Check | Recorded result |", "|---|---|"])
        for check in selected:
            detail = check["detail"].replace("\n", " ").replace("|", "\\|")
            lines.append(f"| `{check['id']}` | {detail} |")
        lines.extend(
            [
                "",
                "Recorded CLI calls (fixture paths are placeholders):",
                "",
                "| Command | Exit |",
                "|---|---|",
            ]
        )
        for check in selected:
            for call in check["calls"]:
                command = shlex.join(["sxr", *call["argv"]]).replace("|", "\\|")
                lines.append(f"| `{command}` | {call['exit_code']} |")
        lines.extend(
            [
                "",
                "Full output is retained under the check IDs in "
                "[contracts.json](../evidence/contracts.json).",
                "",
            ]
        )
    lines.append("Source locations:")
    lines.append("")
    for source in issue["sources"]:
        lines.append(
            f"- [{source['path']}:{source['line']}]"
            f"(../../../{source['path']}#L{source['line']}) `{source['symbol']}`"
        )
    lines.extend(["", "Acceptance criteria:", ""])
    lines.extend(f"- [ ] {criterion}." for criterion in issue["acceptance"])
    lines.extend(["", "Feature IDs: " + ", ".join(f"`{f}`" for f in issue["feature_ids"]), ""])
    path = base / issue["report"]
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines))


def render(base, data, contracts):
    """Lead with the outcomes and expose detailed evidence through local links."""
    for issue in data["issues"]:
        issue_document(base, issue, contracts)
    summary = data["summary"]
    counts = summary["features"]
    lines = [
        "# sxr CLI feature audit",
        "",
        f"Audited the current 0.12.2 working tree at `{data['target']['commit']}` "
        "on 2026-09-10, including its pre-existing edits. "
        f"Mapped **{len(data['features'])} expected behaviors**: "
        f"{counts.get('passed', 0)} passed their linked checks, "
        f"{counts.get('failed', 0)} have a confirmed discrepancy, and "
        f"{counts.get('not_verified', 0)} remain unverified. "
        f"There are **{len(data['issues'])} issue reports**. Application source, "
        "tests and existing edits were preserved.",
        "",
        "- [Feature map, JSON](features.json): expectations, statuses, issue IDs, exact "
        "test cases, parser metadata and environment.",
        "- [Feature map, CSV](features.csv): filter by area, status or issue ID.",
        "- [Issue data, JSON](issues.json): reproducible findings and acceptance criteria.",
        f"- [CLI surface](cli-surface.json): {summary['parameters']} parameter entries "
        f"across {summary['parser_surfaces']} parser surfaces, including both fast parsers "
        "and the hidden audit alias. Every entry links to a feature.",
        "",
        f"The existing suite has **{summary['tests'].get('passed', 0)} passing cases**. "
        "Its first sandboxed run passed 538 and failed four worker tests because the "
        "sandbox denied Unix socket binding. All seven worker tests passed when run with "
        "temporary socket access. Those four environmental failures are not CLI defects.",
        "",
        f"The additional subprocess audit ran **{len(contracts)} contracts**: "
        f"{summary['contract_checks'].get('passed', 0)} passed and "
        f"{summary['contract_checks'].get('failed', 0)} failed. Those failures are grouped "
        "into 16 runtime reports; one further report documents the empty-list exit-code "
        "exception. Tests cover synthetic Claude/Codex files, cache changes, skill maps, "
        "primer files and credential-shaped fixture values. No real transcripts were cleaned.",
        "",
        "A new macOS arm64 bundle was built from this working tree and passed the "
        "repository's relocation verification with an empty PATH. The native tests also "
        "covered worker reuse, fallback, concurrent startup, idle expiry and caller settings. "
        "Formatting, lint and repository conventions passed. See "
        "[external checks](evidence/external-checks.json), [suite results](evidence/pytest.xml), "
        "[worker rerun](evidence/worker.xml), [subprocess evidence](evidence/contracts.json) "
        "and [bundle verification](evidence/bundle.log).",
        "",
        "Passing a row means its linked checks passed, not proof for every possible input. "
        "The Linux/x86_64 and older-OS compatibility matrix, Homebrew installation/upgrade, "
        "and historical performance benchmarks were not verified. These are explicitly "
        "marked in the map. Inferred consistency expectations, such as negative limits "
        "and --tail 0, are identified in their reports.",
        "",
        "| Issue | Priority | Finding |",
        "|---|---|---|",
    ]
    for issue in data["issues"]:
        lines.append(
            f"| [{issue['id']}]({issue['report']}) | {issue['priority']} | {issue['title']} |"
        )
    lines.extend(
        [
            "",
            "Start with SXR-AUD-001: the audit can miss a credential that the clean "
            "preview detects. Time filtering and missing error records also affect which "
            "historical evidence an agent can retrieve.",
            "",
            "Re-run the extra contracts from the repository root:",
            "",
            "```bash",
            "rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py "
            "--output /private/tmp/sxr-audit-contracts.json",
            "```",
            "",
            "Use `--check CHECK-ID` to reproduce one check or ID prefix. The harness "
            "returns 1 while any selected contract fails; it does not apply fixes. "
            "Each issue supplies a narrower command.",
            "",
            "[feature-specifications.psv](feature-specifications.psv) is the editable "
            "expectation catalogue. [issue-specifications.json](issue-specifications.json) "
            "holds report text. `build_report.py` rebuilds JSON, CSV and Markdown from "
            "saved evidence, validates all references, checks that every failed contract "
            "has a report, and refuses to reuse evidence after audited source changes. "
            "Fresh checks and a fresh baseline are required after fixing the CLI.",
            "",
            "Priorities: P1 means a false-clean credential audit; P2 covers incorrect "
            "results, missing evidence and broken output contracts; P3 covers validation "
            "boundaries, diagnostics or documentation.",
            "",
        ]
    )
    (base / "README.md").write_text("\n".join(lines))
