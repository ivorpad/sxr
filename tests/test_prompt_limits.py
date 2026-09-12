"""Row and character limits of the prompts view, and their precedence.

The transcripts here are synthetic but shaped like real ones: Claude isMeta and
isCompactSummary records, Codex content_item_kinds labels observed in rollouts
(agents_md.instructions, hooks.additional_context, generic.turn_aborted,
user.text), tool results, unlabelled legacy messages and a Codex compaction
boundary carrying replacement_history.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()

LONG = "human request\n" * 4000 + "human ending"
LEGACY = "legacy human ask"
REPLAYED = "replayed history text"
CONTEXT_TEXTS = ("Injected rules", "hook context", "aborted notice", "tool output")


def _claude(path):
    """A Claude session with two human prompts and four context records."""

    def user(content, **flags):
        return {
            "type": "user",
            "cwd": "/w",
            "message": {"role": "user", "content": content},
            **flags,
        }

    records = [
        user("Injected rules", isMeta=True),
        user("hook context", isMeta=True),
        user("aborted notice", isCompactSummary=True),
        user(LEGACY),
        user(LONG),
        user([{"type": "tool_result", "tool_use_id": "t1", "content": "tool output"}]),
        {"type": "assistant", "cwd": "/w", "message": {"role": "assistant", "content": "reply"}},
    ]
    path.write_text("\n".join(map(json.dumps, records)))
    return records


def _codex(path):
    """A Codex rollout with the same two human prompts and four context records."""

    def message(text, kinds=None):
        payload = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        }
        if kinds is not None:
            payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
        return {"type": "response_item", "payload": payload}

    records = [
        {"type": "session_meta", "payload": {"id": "limits-fixture", "cwd": "/w"}},
        message("Injected rules", ["agents_md.instructions"]),
        message("hook context", ["hooks.additional_context"]),
        message("aborted notice", ["generic.turn_aborted"]),
        message(LEGACY),
        message(LONG, ["user.text"]),
        {
            "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": "t1", "output": "tool output"},
        },
        {
            "type": "compacted",
            "payload": {
                "message": "compaction boundary",
                "replacement_history": [message(REPLAYED, ["user.text"])],
            },
        },
    ]
    path.write_text("\n".join(map(json.dumps, records)))
    return records


@pytest.fixture(params=["claude", "codex"])
def session(request, tmp_path):
    path = tmp_path / f"{request.param}.jsonl"
    (_claude if request.param == "claude" else _codex)(path)
    return path


def run(session, *args, env=None, monkeypatch=None):
    """Invoke prompts against one synthetic file, optionally with env defaults."""
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    return runner.invoke(app, ["prompts", "--file", str(session), *args])


def test_plain_prints_complete_prompts_under_environment_budget(session, monkeypatch):
    result = run(session, env={"SXR_BUDGET": "1", "SXR_LINE_LIMIT": "5"}, monkeypatch=monkeypatch)
    assert result.exit_code == 0, result.output
    assert LONG in result.stdout and LEGACY in result.stdout
    assert "chars]" not in result.stdout
    for text in CONTEXT_TEXTS:
        assert text not in result.stdout
    assert "2 of 2 human prompts shown" in result.stdout
    assert "4 other user-role records hidden" in result.stdout


def test_line_limit_alone_requests_compact(session):
    result = run(session, "--line-limit", "20")
    assert result.exit_code == 0, result.output
    assert LONG not in result.stdout
    assert "chars]" in result.stdout
    assert "--all, --budget 0, or --json" in result.stdout


def test_budget_zero_wins_over_line_limit(session):
    result = run(session, "--budget", "0", "--line-limit", "20")
    assert result.exit_code == 0, result.output
    assert LONG in result.stdout and "chars]" not in result.stdout


@pytest.mark.parametrize("option", [["--budget", "-1"], ["--line-limit", "-5"]])
def test_negative_character_limits_never_truncate(session, option):
    result = run(session, *option)
    assert result.exit_code == 0, result.output
    assert LONG in result.stdout and "chars]" not in result.stdout


@pytest.mark.parametrize("position", ["root", "command"])
def test_negative_row_limit_is_a_usage_error(session, position):
    command = ["prompts", "--file", str(session)]
    args = ["-n", "-1", *command] if position == "root" else [*command, "-n", "-1"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2


def test_environment_line_limit_applies_only_to_compact_output(session, monkeypatch):
    monkeypatch.setenv("SXR_LINE_LIMIT", "5")
    result = run(session, "--budget", "1")
    assert result.exit_code == 0, result.output
    assert "trimmed to 5-char lines" in result.stdout


def test_row_limit_placement_is_equivalent(session):
    command = ["prompts", "--file", str(session)]
    root = runner.invoke(app, ["-n", "1", *command])
    local = runner.invoke(app, [*command, "-n", "1"])
    assert (root.exit_code, root.stdout, root.stderr) == (
        local.exit_code,
        local.stdout,
        local.stderr,
    )
    assert "1 of 2 human prompts shown" in root.stdout
    assert "-n 0/--all for all" in root.stdout


@pytest.mark.parametrize("position", ["root", "command"])
def test_all_overrides_explicit_limits(session, position):
    command = ["prompts", "--file", str(session), "--budget", "1", "--all"]
    args = ["-n", "1", *command] if position == "root" else [*command, "-n", "1"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert result.stdout.count(LONG) == 1 and LEGACY in result.stdout
    assert "chars]" not in result.stdout
    for text in CONTEXT_TEXTS:
        assert text not in result.stdout


def test_zero_row_limit_is_unlimited(session):
    result = run(session, "-n", "0")
    assert result.exit_code == 0, result.output
    assert "2 of 2 human prompts shown" in result.stdout


def test_all_lifts_the_json_row_limit(session):
    limited = run(session, "--json", "-n", "1")
    lifted = run(session, "--json", "-n", "1", "--all")
    assert (limited.exit_code, lifted.exit_code) == (0, 0)
    assert len(limited.stdout.splitlines()) == 1
    assert "shown 1 of 2" in limited.stderr
    assert len(lifted.stdout.splitlines()) == 2
    assert REPLAYED not in lifted.stdout


def test_include_context_adds_labelled_records_only(session):
    result = run(session, "--include-context")
    assert result.exit_code == 0, result.output
    for text in (LONG, LEGACY, *CONTEXT_TEXTS):
        assert text in result.stdout
    assert "6 of 6 user records shown" in result.stdout
    assert "hidden" not in result.stdout
    assert "reply" not in result.stdout
    assert REPLAYED not in result.stdout


def test_include_context_json_limits_distinct_physical_records(session):
    result = run(session, "--include-context", "--json", "-n", "2")
    assert result.exit_code == 0, result.output
    assert len(result.stdout.splitlines()) == 2
    assert "shown 2 of 6" in result.stderr


def test_compaction_boundary_is_not_replayed(tmp_path):
    path = tmp_path / "codex.jsonl"
    _codex(path)
    result = runner.invoke(
        app, ["prompts", "--file", str(path), "--include-context", "--all", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert REPLAYED not in result.stdout
    assert "compaction boundary" not in result.stdout


def test_legacy_unlabelled_records_stay_human(session):
    result = run(session, "--json")
    assert result.exit_code == 0, result.output
    texts = json.dumps([json.loads(line) for line in result.stdout.splitlines()])
    assert LEGACY in texts
