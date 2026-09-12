"""Isolated synthetic transcripts and recorded CLI calls for the feature audit."""

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CLI = [str(REPO / ".venv/bin/python"), "-c", "from sxr import main; main()"]
SYNTHETIC_PASSWORD = "AuditFixtureOnly_2026_NotACredential!"


def write_records(path, records):
    """Write test records with stable physical line numbers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records))
    return path


def user(text, timestamp="2026-08-01T12:00:00.000Z", **extra):
    """A Claude user message in the audit project."""
    return dict(
        type="user",
        timestamp=timestamp,
        cwd="/sxr-audit-project",
        message=dict(role="user", content=text),
        **extra,
    )


def assistant(blocks, **extra):
    """A Claude assistant message with content blocks."""
    return dict(type="assistant", message=dict(role="assistant", content=blocks), **extra)


def tool(identity, name="Bash", **inputs):
    """A synthetic tool call. Recorded commands are never executed."""
    return dict(type="tool_use", id=identity, name=name, input=inputs)


def failed(identity):
    """A failed Claude tool result."""
    return user(
        [dict(type="tool_result", tool_use_id=identity, is_error=True, content="synthetic failure")]
    )


class Corpus:
    """Own all inputs, cache data, and output from the subprocess checks."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.env = dict(os.environ)
        for key in ("SXR_NO_CACHE", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
            self.env.pop(key, None)
        # Use the CLI's actual provider-root settings for synthetic stores.
        self.env.update(
            SXR_CACHE_DIR=str(self.root / "cache"),
            SXR_SALT_FILE=str(self.root / "salt"),
            CLAUDE_CONFIG_DIR=str(self.root / "claude"),
            CODEX_HOME=str(self.root / "codex"),
            SXR_NO_DAEMON="1",
            NO_COLOR="1",
            PYTHONPATH=str(REPO / "src"),
        )
        self.claude = self.root / "claude/projects/-sxr-audit-project"
        self.calls = []
        self.records = [
            user("alpha needle first prompt"),
            user("beta NEEDLE second prompt"),
            user("third prompt with literal a.b and --dash"),
            assistant(
                [
                    dict(type="text", text="answer"),
                    dict(type="thinking", thinking="private reasoning fixture"),
                ]
            ),
            assistant([tool("t1", command="echo needle")]),
            failed("t1"),
            assistant([tool("t2", "Read", file_path="/tmp/example")]),
            failed("t2"),
            user("injected fixture", isMeta=True),
            dict(type="custom-title", customTitle="audit-main"),
        ]
        self.main = write_records(self.claude / "aaa-main.jsonl", self.records)
        self.second = write_records(
            self.claude / "bbb-second.jsonl",
            [
                user("second session needle", "2026-07-01T12:00:00.000Z"),
                assistant([tool("t3", command="false")]),
                failed("t3"),
            ],
        )
        self.codex_records = [
            dict(
                type="session_meta",
                timestamp="2026-08-02T12:00:00.000Z",
                payload=dict(id="codex-audit", cwd="/sxr-audit-project"),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="message",
                    role="user",
                    content=[dict(type="input_text", text="codex needle")],
                    internal_chat_message_metadata_passthrough=dict(
                        content_item_kinds=["user.text"]
                    ),
                ),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="function_call",
                    name="exec_command",
                    call_id="c1",
                    arguments=json.dumps(dict(cmd="echo needle")),
                ),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id="c1",
                    output=json.dumps(dict(output="synthetic failure", metadata=dict(exit_code=2))),
                ),
            ),
        ]
        self.codex = write_records(
            self.root / "codex/sessions/2026/08/02/rollout-audit.jsonl", self.codex_records
        )
        self.skill = self.root / "skills/notify/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("Synthetic skill instructions. Do not execute.\n")

    def extra(self, name, records):
        """Create a standalone transcript outside the discovered project."""
        return write_records(self.root / "extras" / f"{name}.jsonl", records)

    def run(self, *args, env=None, cwd=None):
        """Invoke the source CLI, preserving stdout, stderr and exit status."""
        command = [*SOURCE_CLI, *map(str, args)]
        environment = dict(self.env, **(env or {}))
        result = subprocess.run(
            command,
            env=environment,
            cwd=cwd or self.root,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.calls.append(
            dict(
                argv=list(map(str, args)),
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                environment_overrides=env or {},
            )
        )
        return result

    def file(self, command, *args, path=None, env=None):
        """Read only one synthetic file, without scanning any user sessions."""
        return self.run(command, *args, "--file", path or self.main, env=env)

    def scope(self, command, *args):
        """Use the synthetic project's isolated provider roots."""
        return self.run(command, *args, "--path", "/sxr-audit-project")


def json_lines(result):
    """Decode an unmodified JSONL response."""
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def require(condition, message):
    """Fail one contract check without stopping the rest of the audit."""
    if not condition:
        raise AssertionError(message)


def code(result, expected=0):
    """Check the public process exit status."""
    require(
        result.returncode == expected,
        f"expected exit {expected}; got {result.returncode}: {result.stderr[:250]}",
    )


def event_rows(result):
    """Count rendered event rows, including a possible session prefix."""
    import re

    return re.findall(r"(?m)^(?:[^\n\t]+\t)?#\d{4}\s.*$", result.stdout)
