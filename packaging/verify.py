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
                    content=[
                        dict(type="input_text", text="portable needle"),
                    ],
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
    ):
        assert run(command, "--help")
    for provider in ("--claude", "--codex"):
        assert run("list", provider, "--path", "/w", "--json")
        for command in ("show", "prompts", "errors", "tools", "stats", "path"):
            assert run(command, provider, "--path", "/w")
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
