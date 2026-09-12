"""The plain prompts command prints complete human input without recovery flags."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()


@pytest.fixture(params=["claude", "codex"])
def prompt_file(request, tmp_path):
    provider = request.param
    text = "human request\n" * 4000 + "human ending"
    if provider == "claude":
        human = {"type": "user", "message": {"content": text}}
        context = {"type": "user", "isMeta": True, "message": {"content": "injected fixture"}}
        tool = {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "t", "content": "tool fixture"}]
            },
        }
        records = [context, human, tool, human]
    else:

        def message(content, kind):
            return {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": content}],
                    "internal_chat_message_metadata_passthrough": {"content_item_kinds": [kind]},
                },
            }

        human = message(text, "user.text")
        context = message("injected fixture", "agents_md.instructions")
        tool = {
            "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": "t", "output": "tool fixture"},
        }
        records = [
            {"type": "session_meta", "payload": {"id": "fixture", "cwd": "/w"}},
            context,
            human,
            tool,
            human,
        ]
    path = tmp_path / "prompts.jsonl"
    path.write_text("\n".join(map(json.dumps, records)))
    return path, text, human


@pytest.mark.parametrize("options", [[], ["--all"]])
def test_plain_and_all_print_complete_human_prompts(prompt_file, monkeypatch, options):
    path, text, _ = prompt_file
    monkeypatch.setenv("SXR_BUDGET", "1")
    monkeypatch.setenv("SXR_LINE_LIMIT", "10")
    result = runner.invoke(app, ["prompts", "--file", str(path), *options])
    assert result.exit_code == 0, result.output
    assert result.stdout.count(text) == 2
    assert "injected fixture" not in result.stdout and "tool fixture" not in result.stdout
    assert "chars]" not in result.stdout


def test_all_lifts_explicit_limits_without_adding_context(prompt_file):
    path, text, _ = prompt_file
    result = runner.invoke(
        app, ["-n", "1", "prompts", "--file", str(path), "--budget", "1", "--all"]
    )
    assert result.exit_code == 0
    assert result.stdout.count(text) == 2
    assert "injected fixture" not in result.stdout and "tool fixture" not in result.stdout


def test_explicit_context_is_separate_from_all(prompt_file):
    path, _, _ = prompt_file
    result = runner.invoke(app, ["prompts", "--file", str(path), "--include-context", "--json"])
    assert result.exit_code == 0, result.output
    assert len(result.stdout.splitlines()) == 4
    assert "injected fixture" in result.stdout and "tool fixture" in result.stdout


def test_explicit_budget_remains_available(prompt_file):
    path, _, human = prompt_file
    args = ["prompts", "--file", str(path), "--budget", "1", "--line-limit", "20", "-n", "1"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0 and "chars]" in result.stdout
    raw = runner.invoke(app, [*args, "--json"])
    assert raw.exit_code == 0 and json.loads(raw.stdout) == human
