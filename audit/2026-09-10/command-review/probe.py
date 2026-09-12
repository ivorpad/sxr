"""Record selected current behaviors using disposable synthetic transcripts only."""

import json
import os
import subprocess
import sys
from pathlib import Path

from collect import HERE, ROOT, hashes


def write_records(path, records):
    """Write synthetic records for one isolated provider fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(map(json.dumps, records)) + "\n")


def main():
    """Capture output characteristics and exits without running recorded commands."""
    scratch = Path("/private/tmp/sxr-command-review")
    project = scratch / "project"
    project.mkdir(parents=True, exist_ok=True)
    long_text = "human request\n" * 4000 + "human ending"

    def message(text, kind="user.text"):
        return dict(
            type="response_item",
            timestamp="2026-08-01T12:00:00Z",
            payload=dict(
                type="message",
                role="user",
                content=[dict(type="input_text", text=text)],
                internal_chat_message_metadata_passthrough=dict(content_item_kinds=[kind]),
            ),
        )

    codex_root = scratch / "codex"
    for index in (1, 2):
        stamp = f"2026-08-0{index}T12:00:00Z"
        records = [
            dict(
                type="session_meta",
                timestamp=stamp,
                payload=dict(id=f"fixture-{index}", cwd=str(project), timestamp=stamp),
            ),
            message("injected fixture", "agents_md.instructions"),
            message(long_text),
            dict(
                type="response_item",
                payload=dict(
                    type="function_call",
                    name="exec_command",
                    call_id="call-1",
                    arguments=json.dumps(dict(cmd="printf synthetic-command")),
                ),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id="call-1",
                    output="Process exited with code 1\nFinal output:\nsynthetic failure",
                ),
            ),
            message("second human fixture"),
        ]
        write_records(codex_root / "sessions" / f"rollout-fixture-{index}.jsonl", records)
    codex_file = str(codex_root / "sessions" / "rollout-fixture-2.jsonl")
    claude_file = str(scratch / "claude.jsonl")
    write_records(
        Path(claude_file),
        [
            dict(type="user", message=dict(content="human fixture")),
            dict(
                type="assistant",
                message=dict(
                    content=[
                        dict(type="text", text="same needle one"),
                        dict(type="text", text="same needle two"),
                    ]
                ),
            ),
            dict(
                type="assistant",
                message=dict(
                    content=[
                        dict(
                            type="tool_use",
                            name="Read",
                            id="read-1",
                            input=dict(file_path="fixture.txt"),
                        ),
                        dict(
                            type="tool_use",
                            name="Bash",
                            id="bash-1",
                            input=dict(command="printf fixture"),
                        ),
                    ]
                ),
            ),
        ],
    )
    skills_root = scratch / "skills"
    for index in range(3):
        skill = skills_root / f"fixture-{index}" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"Synthetic skill {index}\n")
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        SXR_NO_DAEMON="1",
        SXR_CACHE_DIR=str(scratch / "cache"),
        CODEX_HOME=str(codex_root),
        CLAUDE_CONFIG_DIR=str(scratch / "claude-profile"),
        SXR_SALT_FILE=str(scratch / "salt"),
    )
    for name in (
        "SXR_BUDGET",
        "SXR_LINE_LIMIT",
        "SXR_NO_CACHE",
        "CODEX_THREAD_ID",
        "CODEX_SESSION_ID",
    ):
        environment.pop(name, None)
    cases = [
        ("prompts-default", ["prompts", "--file", codex_file]),
        ("prompts-all", ["prompts", "--file", codex_file, "--all", "--json"]),
        ("prompts-no-limits", ["prompts", "--file", codex_file, "-n", "0", "--budget", "0"]),
        ("prompts-typo", ["prompts", "--file", codex_file, "--allç"]),
        ("prompts-proposed-option", ["prompts", "--file", codex_file, "--include-context"]),
        ("prompts-date-after", ["prompts", "--file", codex_file, "--since", "2026-01-01"]),
        (
            "prompts-date-before",
            ["--since", "2026-01-01", "prompts", "--file", codex_file, "--json"],
        ),
        ("prompts-range", ["prompts", "--codex", "--path", str(project), "@1:@2", "--json"]),
        ("show-range", ["show", "--codex", "--path", str(project), "@1:@2", "--json"]),
        ("tools-range", ["tools", "--codex", "--path", str(project), "@1:@2", "--json"]),
        ("stats-limit-text", ["stats", "--file", codex_file, "-n", "1"]),
        ("stats-limit-json", ["stats", "--file", codex_file, "-n", "1", "--json"]),
        ("show-full-errors", ["show", "--file", codex_file, "--full", "--errors", "--json"]),
        (
            "show-negative-context",
            ["show", "--file", codex_file, "--around", "3", "--context", "-1", "--json"],
        ),
        ("show-negative-budget", ["show", "--file", codex_file, "--budget", "-1"]),
        ("show-reversed-range", ["show", "--file", codex_file, "--range", "5:2", "--json"]),
        ("grep-json-ids", ["grep", "needle", "--file", claude_file, "-l", "--json"]),
        ("grep-json-records", ["grep", "needle", "--file", claude_file, "--json"]),
        (
            "grep-count-all-zero",
            ["grep", "no-match", "--file", claude_file, "-c", "--all", "--json"],
        ),
        ("grep-context-limit", ["grep", "needle", "--file", claude_file, "-C", "1", "-n", "1"]),
        ("grep-negative-context", ["grep", "needle", "--file", claude_file, "-C", "-1"]),
        ("grep-after-context", ["grep", "needle", "--file", claude_file, "-A", "1"]),
        ("cmds-non-shell", ["cmds", "--file", claude_file]),
        ("cmds-json-duplicates", ["cmds", "--file", claude_file, "--json"]),
        ("root-json-init", ["--json", "init"]),
        ("root-json-index", ["--json", "index", "--file", codex_file]),
        ("index-local-json", ["index", "--file", codex_file, "--json"]),
        ("skills-index-setup", ["skills", "--index", "--root", str(skills_root)]),
        ("skills-root-json", ["--json", "skills", "fixture"]),
        ("skills-local-json", ["skills", "fixture", "--json"]),
        ("skills-root-limit", ["-n", "1", "skills", "fixture", "--json"]),
        ("skills-local-limit", ["skills", "fixture", "-n", "1", "--json"]),
        ("serve-prefix-idle", ["--json", "serve", "--idle", "1", "--help"]),
        ("serve-direct-idle", ["serve", "--idle", "1", "--help"]),
        ("find-abbreviation", ["find", "human", "--file", codex_file, "--include-c", "--json"]),
        (
            "find-prefix-abbreviation",
            ["--json", "find", "human", "--file", codex_file, "--include-c"],
        ),
        ("find-help-claude", ["--json", "find", "--help"]),
        ("find-default", ["find", "human", "--file", codex_file, "--json"]),
        (
            "find-redundant-agent",
            ["find", "human", "--codex", "--include-agents", "--path", str(project)],
        ),
    ]
    baseline, results = hashes(), []
    for identity, args in cases:
        process = subprocess.run(
            ["rtk", "proxy", sys.executable, "-c", "from sxr import main; main()", *args],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )
        out = process.stdout
        try:
            decoded = [json.loads(line) for line in out.splitlines()]
        except ValueError:
            decoded = None
        results.append(
            dict(
                id=identity,
                argv=args,
                exit_code=process.returncode,
                stdout_chars=len(out),
                stdout_lines=len(out.splitlines()),
                stderr=process.stderr[:1800],
                stdout_preview=out[:900],
                long_prompt_complete=long_text in out,
                injected_context_present="injected fixture" in out,
                trim_marker_present="chars]" in out,
                json_records=len(decoded) if decoded is not None else None,
                json_results=len(decoded[0].get("skills", []))
                if decoded and isinstance(decoded[0], dict) and "skills" in decoded[0]
                else None,
                distinct_json_records=len(set(out.splitlines())) if decoded is not None else None,
            )
        )
    output = dict(
        basis=(
            "Synthetic fixtures only. Observations of existing behavior, not "
            "proposed behavior tests."
        ),
        source_unchanged=baseline == hashes(),
        results=results,
    )
    (HERE / "probes.json").write_text(json.dumps(output, indent=2) + "\n")
    for result in results:
        print(
            f"{result['id']}: exit={result['exit_code']} "
            f"lines={result['stdout_lines']} json={result['json_records']}"
        )
    print(f"source unchanged: {output['source_unchanged']}")


if __name__ == "__main__":
    main()
