"""Record the 2026-09-12 findings audit in disposition.json, note by note.

The second opinion's CSV-staleness finding is broader than the reconciliation
slice's, and partly wrong. This applies the adjudicated result: it appends to
existing notes rather than replacing them, so an earlier correction stays
readable next to the one that refined it, and it adds the upstream defects the
published release carries. Idempotent: a note already carrying its addition is
left alone.

    uv run python apply_audit_findings.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "disposition.json"
MEASURED = "evidence-M/upstream-defects.json, evidence-M/limit-unit.json"

APPEND = {
    "PAR-prompts-typer-budget": (
        "Correction 2026-09-12 (findings audit): the before cell is also wrong for published "
        "0.13.0, which never passes --budget to its catalog path -- bare `prompts`, "
        "`--budget 0` and `--budget 50` produce byte-identical output there. Recorded as an "
        f"upstream defect below; measured in {MEASURED}"
    ),
    "PAR-prompts-typer-line_cap": (
        "Correction 2026-09-12 (findings audit): the before cell is also wrong for published "
        "0.13.0. There --line-limit is honored but means something else: it caps the listing's "
        "first-prompt preview column unconditionally, with no budget involved (measured at 10, "
        "40 and 200 against 8f93114). This tree keeps the documented meaning"
    ),
    "PAR-prompts-typer-limit": (
        "Correction 2026-09-12 (findings audit): the before cell's JSON half was already wrong "
        "at the audited base, not just upstream. `prompts @N --json -n 1` returns all 3 records "
        "on 48b11c6c and on 8f93114, and 1 record here, so SXR-CLI-01 fixed a defect neither the "
        f"CSV nor any upstream release records. Measured in {MEASURED}"
    ),
    "EXTRA-006": (
        "Correction 2026-09-12 (findings audit): the before cell is partially wrong for published "
        "0.13.0, whose bare `prompts --json` emits synthesized prompt_session objects rather than "
        "whole provider JSONL objects. The explicit form still emits raw records there. D-09 keeps "
        "raw records unconditionally here, so the after cell stands"
    ),
    "PAR-prompts-typer-help": (
        "Reviewed 2026-09-12 (findings audit) and left unchanged. A second opinion classified this "
        "row as factually wrong upstream. It is not: the cell asserts exit 0, --help only under "
        "Typer, and -h under argparse, and all three hold on 8f93114 (measured). Published 0.13.0 "
        "did rewrite the help text of this surface, but no cell here quotes that text"
    ),
    "PAR-root-typer-help": (
        "Reviewed 2026-09-12 (findings audit) and left unchanged, for the same reason as "
        "PAR-prompts-typer-help. Root --help is the only other surface whose text changed "
        "upstream, and all four changed regions describe prompts' new listing default, which "
        "the prompts rows already cover. Exactly 2 of 18 --help surfaces differ between the "
        "refs; the other 16 are byte-identical"
    ),
    "CMD-root-typer": (
        "Reviewed 2026-09-12 (findings audit) and left unchanged. Root help did change "
        "upstream, but this row asserts bare-listing behavior and that root help is long, both "
        "still true. The four changed regions are the prompts description line, the id "
        "paragraph, the --json sentence and three example lines -- all about prompts"
    ),
}

SCOPE_ROWS = [
    "PAR-prompts-typer-use_codex",
    "PAR-prompts-typer-use_claude",
    "PAR-prompts-typer-path",
    "PAR-prompts-typer-file",
    "PAR-prompts-typer-recursive",
    "PAR-prompts-typer-worktrees",
    "PAR-prompts-typer-claude_roots",
    "PAR-prompts-typer-include_agents",
    "PAR-prompts-typer-archives",
    "PAR-prompts-typer-coverage",
]
SCOPE_NOTE = (
    "Qualification 2026-09-12 (findings audit): the scope contract holds on every ref, but this "
    "row's example_before prints a session listing on published 0.13.0 rather than prompts, "
    "because the bare form listed there. The flag's meaning is unaffected"
)

DEFECTS = {
    "why": (
        "Defects measured in the published v0.13.0 (8f93114) that Homebrew installs, recorded "
        "rather than fixed: the reviewer chose verify-and-record. Neither reaches this tree, and "
        "neither is fixed here."
    ),
    "defects": {
        "UP-DEF-01-budget-ignored": {
            "surface": "sxr prompts --budget N, with no session id, --file or --latest",
            "behavior": (
                "--budget is accepted and silently ignored. cli.prompts calls "
                "prompt_catalog(refs, parse, json_out, limit, line_cap) and never passes budget, "
                "so bare `prompts`, `--budget 0` and `--budget 50` all print byte-identical output."
            ),
            "verified": "confirmed, behaviorally and in source",
            "evidence": (
                "evidence-M/upstream-defects.json cases bare, bare-budget-0, bare-budget-50"
            ),
            "reaches_this_tree": (
                "no. The catalog path is not adopted under D-08, and prompt_command.py passes "
                "budget into PromptOpts on both the explicit and the default path."
            ),
        },
        "UP-DEF-02-limit-changes-unit": {
            "surface": "sxr prompts -n N, with no session id, --file or --latest",
            "behavior": (
                "-n silently changes unit from prompt records to session rows: with two human "
                "sessions in scope, -n 1 prints one session row and '# +1 more', -n 2 prints both. "
                "A negative -n prints zero rows and exits 0."
            ),
            "verified": "confirmed",
            "evidence": "evidence-M/limit-unit.json cases bare, bare-n1, bare-n2",
            "reaches_this_tree": (
                "no. -n counts prompt records on every path here, and PAR-tools-typer-limit's "
                "'may a limit change unit' question stays open rather than answered by adoption."
            ),
        },
    },
}


def main() -> int:
    """Append each adjudicated note and record the upstream defects."""
    data = json.loads(TARGET.read_text())
    changed = []
    for identity, addition in APPEND.items():
        note = data["dispositions"][identity]["note"]
        if addition in note:
            continue
        data["dispositions"][identity]["note"] = f"{note}. {addition}"
        changed.append(identity)
    for identity in SCOPE_ROWS:
        note = data["dispositions"][identity]["note"]
        if SCOPE_NOTE in note:
            continue
        data["dispositions"][identity]["note"] = f"{note}. {SCOPE_NOTE}"
        changed.append(identity)
    data["upstream_defects"] = DEFECTS
    data["verified_against_source"]["2026-09-12 findings audit"] = {
        "detail": (
            "A second opinion's six findings were checked against the tree after the merge. Four "
            "confirmed and applied: --budget and --line-limit rows are wrong for published 0.13.0 "
            "too; PAR-prompts-typer-limit's JSON claim was already wrong at the audited base, so "
            "SXR-CLI-01 fixed an unrecorded defect; EXTRA-006 is partially wrong upstream; and the "
            "ten prompts scope rows keep their contract but their example_before now lists. Three "
            "rejected with measurement: PAR-prompts-typer-help, PAR-root-typer-help and "
            "CMD-root-typer are not stale, because no cell of theirs quotes the help text that "
            "changed. The count is 25 rows whose command column is prompts, plus EXTRA-004 and "
            "EXTRA-006, which list prompts among several commands -- 27 in total, which is where "
            "both the earlier note and the second opinion got that number."
        ),
        "reading_changed": True,
        "rows": [*APPEND, *SCOPE_ROWS],
    }
    TARGET.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"appended to {len(changed)} notes:")
    for identity in changed:
        print(f"  {identity}")
    print(f"rows still {data['row_count']}, dispositions {len(data['dispositions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
