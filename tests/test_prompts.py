"""Human prompt selection from Codex transcripts with content provenance."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()


def _message(text, kinds=None):
    payload = {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }
    if kinds is not None:
        payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
    return {"type": "response_item", "payload": payload}


def _rollout(tmp_path, records):
    path = tmp_path / "rollout.jsonl"
    meta = {"type": "session_meta", "payload": {"id": "codex-prompts", "cwd": "/w"}}
    path.write_text("\n".join(json.dumps(record) for record in [meta, *records]))
    return path


@pytest.mark.parametrize("include_all", [False, True])
@pytest.mark.parametrize("json_out", [False, True])
def test_codex_prompts_excludes_injected_records(tmp_path, include_all, json_out):
    instructions = _message("# AGENTS.md instructions\nInjected rules", ["agents_md.instructions"])
    environment = _message(
        "<environment_context>/w</environment_context>", ["environments.environment_context"]
    )
    goal = _message("Internal goal reminder", ["goal.internal_context"])
    # A human can paste instruction-looking text. Provenance decides, not its wording.
    first = _message("# AGENTS.md instructions\nPlease explain this file", ["user.text"])
    second = _message("why does prompts include injected context?", ["user.text"])
    tool = {
        "type": "response_item",
        "payload": {"type": "function_call_output", "call_id": "call-1", "output": "Tool output"},
    }
    records = [instructions, environment, first, tool, goal, second]
    path = _rollout(tmp_path, records)
    args = ["prompts", "--codex", "--file", str(path)]
    if include_all:
        args.append("--all")
    if json_out:
        args.append("--json")
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    if json_out:
        assert [json.loads(line) for line in result.stdout.splitlines()] == (
            records if include_all else [first, second]
        )
    else:
        assert "Please explain this file" in result.stdout
        assert "why does prompts include injected context?" in result.stdout
        for text in (
            "Injected rules",
            "<environment_context>",
            "Internal goal reminder",
            "Tool output",
        ):
            assert (text in result.stdout) == include_all


def test_codex_prompts_keeps_unlabelled_legacy_messages(tmp_path):
    records = [_message("legacy human prompt")]
    path = _rollout(tmp_path, records)
    result = runner.invoke(app, ["prompts", "--file", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == records[0]


def test_codex_prompts_with_only_injected_context_is_empty(tmp_path):
    path = _rollout(tmp_path, [_message("Injected rules", ["agents_md.instructions"])])
    result = runner.invoke(app, ["prompts", "--file", str(path), "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""


@pytest.mark.parametrize("include_all", [False, True])
def test_codex_legacy_user_events_are_not_duplicated(tmp_path, include_all):
    human = {"type": "event_msg", "payload": {"type": "user_message", "message": "hello"}}
    records = [
        _message("<environment_context>injected</environment_context>"),
        _message("hello"),
        human,
    ]
    path = _rollout(tmp_path, records)
    args = ["prompts", "--file", str(path), "--json"]
    if include_all:
        args.append("--all")
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert [json.loads(line) for line in result.stdout.splitlines()] == (
        records if include_all else [human]
    )


def test_codex_prompts_keeps_user_attachments(tmp_path):
    record = _message("", ["user.image"])
    record["payload"]["content"] = [{"type": "input_image", "image_url": "fixture.png"}]
    path = _rollout(tmp_path, [record])
    result = runner.invoke(app, ["prompts", "--file", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == record


@pytest.mark.parametrize("include_all", [False, True])
@pytest.mark.parametrize("as_blocks", [False, True])
def test_claude_prompts_excludes_marked_metadata_and_summaries(tmp_path, include_all, as_blocks):
    records = []
    for text, flags in [
        ("human request", {}),
        ("Injected rules", {"isMeta": True}),
        ("Previous conversation summary", {"isCompactSummary": True}),
    ]:
        content = [{"type": "text", "text": text}] if as_blocks else text
        records.append(
            {"type": "user", "cwd": "/w", "message": {"role": "user", "content": content}, **flags}
        )
    path = tmp_path / "claude.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records))
    args = ["prompts", "--file", str(path), "--json"]
    if include_all:
        args.append("--all")
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert [json.loads(line) for line in result.stdout.splitlines()] == (
        records if include_all else records[:1]
    )
