"""Join the parser inventory to reviewed before/after notes with no unmapped flags."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMANDS = json.loads((HERE / "command-notes.json").read_text())
NOTES = json.loads((HERE / "flag-notes.json").read_text())
CONTRACTS = json.loads((HERE / "option-contracts.json").read_text())
SURFACE = json.loads((HERE / "surface.json").read_text())

FIELDS = [
    "id",
    "kind",
    "command",
    "parser",
    "visibility",
    "item",
    "aliases",
    "value",
    "default_before",
    "before",
    "example_before",
    "problem",
    "after",
    "example_after",
    "default_after",
    "priority",
    "compatibility",
    "acceptance",
    "source",
    "evidence",
    "status",
]


def invocation(command):
    """Return an illustrative invocation with required arguments supplied."""
    suffix = {"grep": " retry", "find": " retry", "skills": " notify"}.get(command, "")
    return "sxr" + (" " + command if command != "root" else "") + suffix


def example(command, flag):
    """Use valid flag combinations instead of repeating an unrelated command example."""
    base = invocation(command)
    special = {
        ("init", "--global"): "sxr init --global --check",
        ("init", "--help"): "sxr init --help",
        ("skills", "--aliases"): "sxr skills notify --paths --aliases",
        ("skills", "--defaults"): "sxr skills --index --defaults",
        ("skills", "--clear"): "sxr skills --clear",
        ("find", "--index"): "sxr find --index",
        ("grep", "--all"): "sxr grep retry -c --all",
        ("grep", "--sort"): "sxr grep retry -c --sort started",
        ("grep", "--regexp"): "sxr grep -e '--flag' @2",
        ("serve", "--foreground"): "sxr serve --foreground /tmp/private-worker.sock",
        ("serve", "--idle"): "sxr serve --foreground /tmp/private-worker.sock --idle 300",
    }
    if (command, flag) in special:
        return special[command, flag]
    if flag == "--help":
        return ("sxr" if command == "root" else "sxr " + command) + " --help"
    if flag == "--archives" and command != "find":
        return base + " --codex --archives"
    if command == "show" and flag == "--context":
        return base + " --around 100 --context 3"
    values = {
        "--path": "/repo",
        "--file": "/path/session.jsonl",
        "--claude-root": "~/.claude-work",
        "--since": "today",
        "--before": "today",
        "--limit": "5",
        "--around": "100",
        "--context": "3",
        "--range": "10:50",
        "--type": "text",
        "--tail": "5",
        "--budget": "0",
        "--line-limit": "200",
        "--after-context": "3",
        "--before-context": "3",
        "--grep": "'git push'",
        "--exclude-session": "FULL_ID",
        "--root": "~/.agents/skills",
    }
    return base + " " + flag + (" " + values[flag] if flag in values else "")


def parameter_note(command, parameter, flag):
    """Require a command-specific or deliberately shared review for each parameter."""
    common = COMMANDS[command]
    if parameter["kind"] == "argument":
        before, after, example_after, priority = CONTRACTS["arguments"][
            f"{command} {parameter['name']}"
        ]
        return dict(
            before=before,
            after=after,
            example_after=example_after,
            priority=priority,
            problem="No selection change proposed." if priority == "Keep" else common["problem"],
            compatibility=common["compatibility"],
            acceptance=common["acceptance"],
        )
    if flag == "--json":
        changes = {
            "grep": (
                "Ensure every JSON mode emits valid JSON. Deduplicate raw records "
                "and keep count/ID projections explicitly typed."
            ),
            "cmds": (
                "Retain raw records, deduplicate before limits and add "
                "--events-json for individual calls with paired outcome and "
                "coordinates."
            ),
            "tools": (
                "Identify the source session and make tool-entry caps explicit "
                "with total/omitted metadata."
            ),
            "stats": (
                "Use numeric counts and byte sizes, correct UTC instants and "
                "whole-session limit units."
            ),
            "skills": (
                "Honor inherited root --json and project the same path set when "
                "--paths is requested."
            ),
            "secrets clean": (
                "Retain masked file results and add a typed operation summary "
                "with changed/skipped/failed/omitted counts."
            ),
            "root": (
                "Honor root JSON for compatible commands and reject it for "
                "unsupported operations rather than ignoring it."
            ),
        }
        after = changes.get(
            command,
            (
                "Retain this command's structured/raw output contract and "
                "describe its exact schema in help. Keep notices on stderr."
            ),
        )
        problems = {
            "find": (
                "No JSON shape change proposed. Preserve explicit completeness and source evidence."
            ),
            "skills": (
                "Inherited root JSON is ignored. --paths does not project paths in JSON mode."
            ),
            "grep": "-l overrides JSON with plain IDs. Raw output can repeat source records.",
            "cmds": "Raw calls omit normalized paired outcomes and may repeat physical records.",
            "root": "Several commands silently ignore the inherited JSON request.",
        }
        problem = problems.get(
            command,
            (
                "Help calls this raw JSONL without spelling out this command's "
                "exact record/aggregate shape and limit unit."
            ),
        )
        return dict(
            before=CONTRACTS["json"][command],
            after=after,
            example_after=example(command, flag),
            problem=problem,
            priority="P1" if command in changes else "Keep" if command == "find" else "P2",
            compatibility=(
                "Preserve original record contents in raw views. Document new "
                "projections or derived-schema changes."
            ),
            acceptance=(
                "Every stdout line/document parses in the selected mode. Limits "
                "never truncate an object. Verify the command-specific fields."
            ),
        )
    if flag == "--limit":
        unit, default, after, priority = CONTRACTS["limits"][command]
        return dict(
            before=f"Limits {unit}. Default: {default}. 0 means all. Negative values are rejected.",
            after=after,
            example_after=example(command, flag),
            priority=priority,
            default_before=f"Parser: {parameter['default']}. Effective: {default}.",
            default_after=default if command != "stats" else "all complete session summaries",
            problem="No count-contract change proposed."
            if priority == "Keep"
            else "The shared row wording hides command/mode-specific units or inherited behavior.",
            compatibility=(
                "Preserve nonnegative count syntax and -n alias. Document any "
                "changed logical unit or -n 0 budget interaction."
            ),
            acceptance=(
                "Check omitted, 0, 1 and negative limits in text and JSON, "
                "including multi-session and multi-block inputs."
            ),
        )
    key = f"{command} {flag}"
    if key in NOTES["specific"]:
        return NOTES["specific"][key]
    return NOTES["shared"][flag]


def defaults(command, parameter, flag):
    """Describe effective defaults rather than making readers interpret parser nulls."""
    values = {
        "--help": "off",
        "--codex": "Both providers in find. Claude elsewhere. --file auto-detects provider.",
        "--claude": "Both providers in find. Claude elsewhere. --file auto-detects provider.",
        "--path": "Recorded process cwd, unless inherited --path selects another directory.",
        "--file": "No explicit file. Discover sessions in the selected project scope.",
        "--json": "Text output, unless --json is inherited from a compatible parent.",
        "--since": "No lower start-date bound, unless inherited from the root/group.",
        "--before": "No upper start-date bound, unless inherited from the root/group.",
        "--claude-root": "CLAUDE_CONFIG_DIR or ~/.claude unless explicit roots are inherited.",
        "--include-agents": (
            "Included by default in find. Excluded by default in ordinary discovery."
        ),
        "--archives": "Present archives included by find. Excluded by ordinary Codex discovery.",
        "--budget": "SXR_BUDGET or 40000 characters.",
        "--line-limit": "SXR_LINE_LIMIT or 200 characters, only while trimming.",
        "--root": (
            "Remembered skill discovery roots, otherwise HOME plus external configured profiles."
        ),
        "--exclude-session": (
            "No explicit exclusions. find still excludes the detected current Codex session."
        ),
    }
    declared = parameter.get("default")
    before = values.get(
        flag, "off" if declared is False else "none" if declared is None else str(declared)
    )
    after = before
    if command == "prompts" and flag == "--budget":
        after = (
            "No implicit budget. Complete human text unless a compact view is explicitly requested."
        )
    if command == "prompts" and flag == "--line-limit":
        after = "No default-view trimming. Compact mode uses the explicit/environment/default cap."
    if command == "grep" and flag in ("--after-context", "--before-context"):
        after = "0 neighboring events on this side."
    if command == "cmds" and parameter["kind"] == "argument":
        after = "Newest session, regardless of --grep."
    return before, after


def row(identity, kind, command, note, **extra):
    """Build a uniform CSV record, retaining current/proposed status explicitly."""
    value = dict.fromkeys(FIELDS, "")
    value.update({key: item for key, item in note.items() if key in value})
    label = "sxr" if command == "root" else "sxr " + command if command in COMMANDS else command
    value.update(id=identity, kind=kind, command=label)
    value.update(extra)
    value["status"] = "retain" if value["priority"] == "Keep" else "proposed, not implemented"
    return value


def main():
    """Write reviewed rows and a mechanical coverage receipt for CSV creation."""
    rows, keys, expected = [], [], []
    for surface in SURFACE["surfaces"]:
        command, parser = surface["command"], surface["parser"]
        name = command.replace(" ", "-")
        common = COMMANDS[command]
        command_row = row(
            f"CMD-{name}-{parser}",
            "command",
            command,
            common,
            parser=parser,
            visibility="hidden" if surface["hidden"] else "public",
            item="sxr" if command == "root" else "sxr " + command,
        )
        if command == "skills" and parser == "typer":
            command_row["before"] += (
                " This Typer entry has no own parameters and forwards remaining "
                "arguments to the skills argparse parser. Inherited root flags "
                "are lost."
            )
        if command == "serve" and parser == "typer":
            command_row["before"] += " This entry accepts only ACTION and --help."
        rows.append(command_row)
        for parameter in surface["parameters"]:
            flags = parameter["flags"]
            flag = next((f for f in flags if f.startswith("--")), parameter["name"])
            note = parameter_note(command, parameter, flag)
            key = (command, parser, parameter["name"])
            keys.append(key)
            expected.append(
                dict(command=command, parser=parser, name=parameter["name"], flags=flags)
            )
            default_before, default_after = defaults(command, parameter, flag)
            choices = parameter.get("choices")
            value_type = str(parameter.get("type") or "boolean")
            if value_type == "None":
                value_type = "boolean" if parameter["kind"] == "option" else "text"
            value_type += "; required" if parameter.get("required") else "; optional"
            if parameter.get("multiple") or flag in (
                "--claude-root",
                "--exclude-session",
                "--root",
            ):
                value_type += "; repeatable"
            if choices:
                value_type += "; choices=" + ", ".join(choices)
            current_example = example(command, flag) if flags else common["example_before"]
            parameter_row = row(
                f"PAR-{name}-{parser}-{parameter['name']}",
                parameter["kind"],
                command,
                note,
                parser=parser,
                visibility="hidden" if surface["hidden"] or parameter.get("hidden") else "public",
                item=flag if flags else parameter["name"].upper(),
                aliases=", ".join(f for f in flags if f != flag),
                value=value_type,
                default_before=note.get("default_before", default_before),
                default_after=note.get("default_after", default_after),
                example_before=current_example,
                source=common["source"] + "; src/sxr/flags.py; src/sxr/scope_options.py"
                if command not in ("serve", "skills", "init")
                else common["source"],
                evidence="; ".join(
                    [
                        f"surface.json:{command}/{parser}/{parameter['name']}",
                        f"help/{name}-{parser}.txt",
                    ]
                ),
            )
            rows.append(parameter_row)
    extras = json.loads((HERE / "additional-notes.json").read_text())
    for index, note in enumerate(extras, 1):
        command = note["command"]
        current = note.get("example_before") or (
            "Not currently supported"
            if note["kind"] == "proposed option"
            else COMMANDS.get(command, {}).get("example_before", note["item"])
        )
        if note["kind"] == "proposed option" and note["item"] in ("--since", "--before"):
            current = f"sxr {note['item']} today {command} --codex"
        rows.append(
            row(
                f"EXTRA-{index:03d}",
                note["kind"],
                command,
                note,
                item=note["item"],
                parser="not yet available"
                if note["kind"] == "proposed option"
                else "cross-command/source",
                visibility="proposed"
                if note["kind"] == "proposed option"
                else "documented in report",
                example_before=current,
            )
        )
    assert len(keys) == len(set(keys)), "duplicate parameter keys"
    assert len({r["id"] for r in rows}) == len(rows), "duplicate row IDs"
    for item in rows:
        for required in ("before", "after", "priority", "compatibility", "acceptance", "source"):
            assert item[required], (item["id"], required)
        for value in item.values():
            assert "\u2014" not in str(value), (item["id"], "em dash")
    (HERE / "review.json").write_text(json.dumps(dict(columns=FIELDS, rows=rows), indent=2) + "\n")
    receipt = dict(
        command_surfaces=len(SURFACE["surfaces"]),
        distinct_commands=len(COMMANDS),
        current_parameters=len(keys),
        additional_rows=len(extras),
        total_rows=len(rows),
        covered_parameters=expected,
        unmapped_parameters=[],
    )
    (HERE / "coverage.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in receipt.items() if key != "covered_parameters"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
