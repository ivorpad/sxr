"""Exercise a relocated release bundle with no system Python or Homebrew on PATH."""

import argparse
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


def invoke(executable, environment, *arguments, codes=(0,)):
    """Check exit status and keep fixture output available for assertions."""
    result = subprocess.run(
        [str(executable), *arguments], env=environment, capture_output=True, text=True, timeout=30
    )
    assert result.returncode in codes, (arguments, result.returncode, result.stderr)
    return result.stdout


def fixtures(root):
    """Create both providers with searchable text, a command, and a failed outcome."""
    claude = root / "claude/projects/-w/fixture.jsonl"
    codex = root / "codex/sessions/2026/09/09/rollout-fixture.jsonl"
    records = [
        [
            dict(
                type="user",
                cwd="/w",
                isMeta=True,
                message=dict(role="user", content="injected-context"),
            ),
            dict(
                type="user",
                cwd="/w",
                timestamp="2026-09-01T10:00:00Z",
                message=dict(role="user", content="portable needle"),
            ),
            dict(
                type="assistant",
                message=dict(
                    role="assistant",
                    content=[
                        dict(
                            type="tool_use",
                            id="tool1",
                            name="Bash",
                            input=dict(command="echo needle"),
                        ),
                    ],
                ),
            ),
            dict(
                type="user",
                message=dict(
                    role="user",
                    content=[
                        dict(
                            type="tool_result", tool_use_id="tool1", is_error=True, content="failed"
                        ),
                    ],
                ),
            ),
        ],
        [
            dict(
                type="session_meta",
                timestamp="2026-09-01T10:00:00Z",
                payload=dict(id="codex-fixture", cwd="/w"),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="message",
                    role="user",
                    content=[dict(type="input_text", text="injected-context")],
                    internal_chat_message_metadata_passthrough=dict(
                        content_item_kinds=["agents_md.instructions"]
                    ),
                ),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="message",
                    role="user",
                    content=[
                        dict(type="input_text", text="portable needle"),
                    ],
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
                    arguments=json.dumps(dict(cmd="echo needle")),
                    call_id="tool1",
                ),
            ),
            dict(
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id="tool1",
                    output=json.dumps(dict(output="failed", metadata=dict(exit_code=1))),
                ),
            ),
        ],
    ]
    for path, items in zip((claude, codex), records, strict=True):
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(json.dumps(item) for item in items) + "\n")
    return claude, codex


def verify_prompts(run, provider):
    """Check human-only selection and the explicit escape hatch in the installed CLI."""
    prompts = run("prompts", provider, "--path", "/w")
    assert "portable needle" in prompts and "injected-context" not in prompts
    assert "injected-context" in run("prompts", provider, "--path", "/w", "--all")
    records = run("prompts", provider, "--path", "/w", "--json").splitlines()
    assert len(records) == 1 and "portable needle" in records[0]


def verify_default_prompt_session(run, source):
    """Exercise default discovery with newer empty, subagent and review sessions."""
    original = [json.loads(line) for line in source.read_text().splitlines()]
    for day, (name, kind, message) in enumerate(
        [
            ("empty", "cli", original[1]),
            ("child", "subagent", original[2]),
            ("review", "guardian_review", original[2]),
        ],
        start=2,
    ):
        meta = {
            "type": "session_meta",
            "timestamp": f"2026-09-{day:02d}T12:00:00Z",
            "payload": {"id": name, "cwd": "/w", "source": kind},
        }
        sibling = source.with_name(f"rollout-{name}.jsonl")
        sibling.write_text(json.dumps(meta) + "\n" + json.dumps(message) + "\n")
    selected = run("prompts", "--codex", "--path", "/w", "--json")
    assert json.loads(selected) == original[2]
    assert not run("prompts", "empty", "--codex", "--path", "/w", "--json", codes=(1,))
    selected = run("prompts", "empty", "--codex", "--path", "/w", "--all", "--json")
    assert json.loads(selected) == original[1]


def verify(executable, environment, sources):
    """Test command families, bundled rule data, fresh indexing, and worker reuse."""

    def run(*args, **kwargs):
        return invoke(executable, environment, *args, **kwargs)

    assert run("--version").startswith("sxr ")
    for command in (
        "list",
        "show",
        "grep",
        "cmds",
        "errors",
        "prompts",
        "tools",
        "stats",
        "path",
        "find",
        "index",
        "secrets",
        "clean",
        "init",
        "serve",
        "skills",
    ):
        assert run(command, "--help")
    for provider in ("--claude", "--codex"):
        assert run("list", provider, "--path", "/w", "--json")
        for command in ("show", "prompts", "errors", "tools", "stats", "path"):
            assert run(command, provider, "--path", "/w")
        verify_prompts(run, provider)
        assert "needle" in run("grep", "needle", provider, "--path", "/w")
        assert "needle" in run("cmds", "--grep", "echo", provider, "--path", "/w")
        run("secrets", provider, "--path", "/w", codes=(0, 1))
        run("clean", provider, "--path", "/w", codes=(0, 1))
    result = json.loads(run("find", "needle", "--all-projects", "--json"))
    assert result["total"] == 2 and result["complete"]
    status = json.loads(run("serve", "status"))
    paths = run("find", "needle", "--all-projects", "--paths").splitlines()
    assert set(paths) == {str(path) for path in sources}
    source = sources[0]
    source.write_text(source.read_text().replace("needle", "replacement"))
    assert json.loads(run("find", "needle", "--all-projects", "--json"))["total"] == 1
    run("index", "--clear")
    assert json.loads(run("find", "replacement", "--all-projects", "--json"))["total"] == 1
    assert json.loads(run("serve", "status"))["pid"] == status["pid"]
    skill_root = Path(environment["HOME"]) / "Developer/arbitrary/notify"
    skill_root.mkdir(parents=True)
    skill_file = skill_root / "SKILL.md"
    skill_file.write_text("Fixture instructions; never executed.\n")
    assert run("skills", "notify", "--paths").strip() == str(skill_file)
    assert json.loads(run("skills", "notify", "--json"))["complete"]
    assert json.loads(run("serve", "status"))["pid"] == status["pid"]
    copy = skill_root.parent / "backup/notify/SKILL.md"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(skill_file.read_bytes())
    run("skills", "--index")
    grouped = json.loads(run("skills", "notify", "--json"))
    assert grouped["total"] == 1 and grouped["files"] == 2
    assert grouped["skills"][0]["copies"] == 2
    assert set(run("skills", "notify", "--paths", "--copies").splitlines()) == {
        str(skill_file),
        str(copy),
    }
    copy.write_text("Different instructions.\n")
    assert json.loads(run("skills", "notify", "--json", codes=(2,)))["total"] == 2
    copy.unlink()
    run("skills", "--index")
    skill_file.unlink()
    run("skills", "notify", "--paths", codes=(2,))
    run("skills", "--index")
    run("skills", "notify", "--paths", codes=(1,))
    verify_default_prompt_session(run, sources[1])
    assert run("init")
    run("serve", "stop")


def main():
    """Unpack in a private user directory and move before invoking the bundled launcher."""
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sxrb-", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        with tarfile.open(options.archive) as archive:
            archive.extractall(root / "download", filter="data")
        destination = root / "user prefix"
        shutil.move(root / "download/sxr", destination)
        sources = fixtures(root)
        environment = dict(
            HOME=str(root),
            PATH=str(root / "empty-path"),
            SXR_CACHE_DIR=str(root / "cache"),
            CODEX_HOME=str(root / "codex"),
            CLAUDE_CONFIG_DIR=str(root / "claude"),
            SXR_SALT_FILE=str(root / "salt"),
            NO_COLOR="1",
        )
        environment.update({key: value for key, value in os.environ.items() if key == "TMPDIR"})
        try:
            verify(destination / "sxr", environment, sources)
        finally:
            invoke(destination / "sxr", environment, "serve", "stop", codes=(0, 1))
    print("Relocated bundle passed command, freshness, and worker checks without Python on PATH")


if __name__ == "__main__":
    main()
