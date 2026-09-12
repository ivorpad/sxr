"""Verify CSV fidelity, exhaustive parser coverage and unchanged product source."""

import csv
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

from collect import HERE, ROOT, collect, hashes


def main():
    """Check report coverage independently of the assembler's row counts."""
    source = json.loads((HERE / "surface.json").read_text())
    expected = json.loads((HERE / "review.json").read_text())
    path = HERE / "commands-before-after.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, strict=True)
        actual = list(reader)
        assert reader.fieldnames == expected["columns"]
    assert actual == expected["rows"], "CSV changed a report value or omitted rows"
    assert len({r["id"] for r in actual}) == len(actual)
    live = collect()
    current = {
        (s["command"], s["parser"], p["name"]): p["flags"] for s in live for p in s["parameters"]
    }
    parameter_rows = {r["id"]: r for r in actual if r["kind"] in ("argument", "option")}
    assert len(current) == len(parameter_rows)
    for (command, parser, name), flags in current.items():
        identity = f"PAR-{command.replace(' ', '-')}-{parser}-{name}"
        item = parameter_rows[identity]
        if flags:
            recorded = {item["item"], *filter(None, item["aliases"].split(", "))}
            assert recorded == set(flags), (identity, recorded, flags)
    command_ids = {r["id"] for r in actual if r["kind"] == "command"}
    assert command_ids == {f"CMD-{s['command'].replace(' ', '-')}-{s['parser']}" for s in live}
    assert all(check["exit_code"] == 0 for check in source["help_checks"])
    assert hashes() == source["source"], "Product source/tests changed during report-only work"
    probes = json.loads((HERE / "probes.json").read_text())
    assert probes["source_unchanged"]
    observations = {item["id"]: item for item in probes["results"]}
    assert not observations["prompts-default"]["long_prompt_complete"]
    assert observations["prompts-all"]["injected_context_present"]
    assert observations["prompts-no-limits"]["long_prompt_complete"]
    assert observations["prompts-proposed-option"]["exit_code"] == 2
    assert observations["prompts-range"]["json_records"] == 2
    assert observations["show-range"]["json_records"] == 4
    assert observations["tools-range"]["json_records"] == 1
    assert observations["grep-json-ids"]["json_records"] is None
    for identity in ("grep-json-records", "cmds-json-duplicates"):
        assert observations[identity]["json_records"] == 2
        assert observations[identity]["distinct_json_records"] == 1
    assert observations["skills-root-json"]["json_records"] is None
    assert observations["skills-local-json"]["json_records"] == 1
    assert observations["skills-root-limit"]["json_results"] == 3
    assert observations["skills-local-limit"]["json_results"] == 1
    assert observations["find-abbreviation"]["exit_code"] == 0
    assert observations["find-prefix-abbreviation"]["exit_code"] == 2
    for identity in (
        "skills-root-json",
        "skills-local-json",
        "skills-root-limit",
        "skills-local-limit",
    ):
        assert observations[identity]["exit_code"] == 0
    log = (HERE.parent / "remediation" / "prompt-defaults-before.log").read_text()
    assert "8 failed, 2 passed" in log
    for row in actual:
        for field in ("before", "after", "example_before", "example_after", "source", "acceptance"):
            assert row[field], (row["id"], field)
        assert not any(key is None or value is None for key, value in row.items())
    receipt = dict(
        verified_at=datetime.now(UTC).isoformat(),
        result="passed",
        report=str(path.relative_to(ROOT)),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rows=len(actual),
        columns=len(expected["columns"]),
        by_kind=dict(Counter(row["kind"] for row in actual)),
        command_entries=len({s["command"] for s in live}),
        parser_surfaces=len(live),
        parameter_entries=len(current),
        flag_spellings=len({f for flags in current.values() for f in flags}),
        help_checks=len(source["help_checks"]),
        synthetic_observations=len(probes["results"]),
        csv_round_trip=True,
        all_parameters_and_aliases_covered=True,
        product_source_unchanged=True,
        prior_prompt_test_state=(
            "8 failed, 2 passed. Proposal tests remain unimplemented and unchanged."
        ),
        scope=(
            "Report validation only. Does not claim the current full product "
            "test suite passes or that proposals have shipped."
        ),
    )
    (HERE / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
