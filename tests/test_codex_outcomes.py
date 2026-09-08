"""Sanitized Codex command records retain execution identity and source lines."""

import json
from pathlib import Path

from sxr.providers import codex
from sxr.views_grep import GrepOpts, grep_view
from sxr.views_info import cmds_view, tools_view
from sxr.views_read import ShowOpts, errors, show


def _record(kind: str, **payload) -> dict:
    return {"timestamp": "2026-08-01T12:00:00Z", "type": kind, "payload": payload}


def _command(identity: str, code: int | None, **fields) -> dict:
    return _record(
        "event_msg",
        type="item_completed",
        thread_id="abcd-1234",
        item={
            "type": "CommandExecution",
            "id": identity,
            "command": ["/bin/sh", "-lc", "echo command-needle"],
            "status": "completed",
            "exit_code": code,
            "aggregated_output": "",
            **fields,
        },
    )


def _rollout(tmp_path: Path, monkeypatch, records: list[dict]) -> tuple[Path, list[dict]]:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    path = tmp_path / "sessions" / "rollout-fixture.jsonl"
    path.parent.mkdir()
    records = [_record("session_meta", id="abcd-1234", cwd="/w"), *records]
    path.write_text("\n".join(json.dumps(record) for record in records))
    return path, records


def test_completed_commands_counts_and_native_zoom(tmp_path: Path, monkeypatch, capsys) -> None:
    failed = _command("exec-failed", 2, aggregated_output="failure-needle")
    records = [
        _record(
            "response_item",
            type="custom_tool_call",
            name="exec",
            call_id="outer",
            input="orchestrate work",
        ),
        _command("exec-ok", 0, aggregated_output="success-needle"),
        failed,
        failed,
        _command("exec-retry", 2, aggregated_output="failure-needle"),
        _command("exec-unfinished", None, status="inProgress"),
        _record(
            "response_item",
            type="custom_tool_call_output",
            call_id="outer",
            output=json.dumps({"output": "orchestration done", "exit_code": 0}),
        ),
    ]
    path, raw = _rollout(tmp_path, monkeypatch, records)
    events = codex.parse(path)
    calls = [e for e in events if e.kind == "tool"]
    assert len(calls) == 5
    assert [e.tag for e in calls] == ["ok", "ok", "err", "err", ""]
    assert [e.seq for e in events if e.is_error] == [4, 6]
    assert events[3].raw["source_seqs"] == [4, 5]
    assert events[4].raw["duplicate_of"] == 4
    assert [e.raw["line"] for e in events] == raw
    assert [e.seq for e in events] == list(range(1, len(raw) + 1))
    refs = codex.list_sessions("/w")
    assert refs[0].errors == 2

    assert tools_view(events, True) == 0
    tools = json.loads(capsys.readouterr().out)
    assert tools["calls"] == {"exec": 1, "exec_command": 4}
    assert tools["errors"] == {"exec_command": 2}

    assert errors(refs, codex.parse, True, None) == 0
    assert [
        json.loads(line)["payload"]["item"]["id"] for line in capsys.readouterr().out.splitlines()
    ] == ["exec-failed", "exec-retry"]
    assert cmds_view(refs, codex.parse, True, None) == 0
    assert len(capsys.readouterr().out.splitlines()) == 5
    assert grep_view("failure-needle", refs, codex.parse, GrepOpts(count=True, json_out=True)) == 0
    count = json.loads(capsys.readouterr().out)
    assert (count["matches"], count["first"]) == (2, 4)
    assert show(refs[0], events, ShowOpts(around=count["first"], context=0, json_out=True)) == 0
    assert json.loads(capsys.readouterr().out) == raw[3]


def test_completed_commands_display_command_only(tmp_path: Path, monkeypatch, capsys) -> None:
    _rollout(tmp_path, monkeypatch, [_command("one", 0, aggregated_output="output-only-needle")])
    refs = codex.list_sessions("/w")
    assert cmds_view(refs, codex.parse, False, None, "output-only-needle") == 1
    capsys.readouterr()
    assert cmds_view(refs, codex.parse, False, None, "command-needle") == 0
    rendered = capsys.readouterr().out
    assert "output-only-needle" not in rendered and "command-needle" in rendered


def test_repeated_legacy_outcomes_and_modern_aliases(tmp_path: Path, monkeypatch) -> None:
    call = _record(
        "response_item",
        type="function_call",
        name="exec_command",
        call_id="call-1",
        arguments='{"cmd":"false"}',
    )
    result = _record(
        "response_item",
        type="function_call_output",
        call_id="call-1",
        output=json.dumps({"output": "legacy failure", "metadata": {"exit_code": 1}}),
    )
    records = [
        call,
        call,
        _record(
            "event_msg",
            type="exec_command_end",
            call_id="call-1",
            exit_code=1,
            aggregated_output="legacy failure",
        ),
        result,
        result,
        _command(
            "item-1", 1, call_id="call-1", command="false", aggregated_output="completed failure"
        ),
    ]
    path, raw = _rollout(tmp_path, monkeypatch, records)
    events = codex.parse(path)
    assert len([e for e in events if e.kind == "tool"]) == 1
    failure = next(e for e in events if e.is_error)
    assert failure.seq == 7 and failure.text == "false\ncompleted failure"
    assert failure.raw["source_seqs"] == [2, 3, 4, 5, 6, 7]
    assert [e.raw["line"] for e in events] == raw
    assert codex.list_sessions("/w")[0].errors == 1


def test_legacy_end_sets_call_outcome_without_duplicate_failures(
    tmp_path: Path, monkeypatch
) -> None:
    path, _ = _rollout(
        tmp_path,
        monkeypatch,
        [
            _record(
                "response_item",
                type="function_call",
                name="exec_command",
                call_id="one",
                arguments='{"cmd":"false"}',
            ),
            _record(
                "event_msg",
                type="exec_command_end",
                call_id="one",
                exit_code=1,
                stderr="legacy failure",
            ),
            _record(
                "response_item",
                type="function_call_output",
                call_id="one",
                output=json.dumps({"output": "legacy failure", "metadata": {"exit_code": 1}}),
            ),
        ],
    )
    events = codex.parse(path)
    call = next(e for e in events if e.kind == "tool")
    failures = [e for e in events if e.is_error]
    assert call.tag == "err" and len(failures) == 1
    assert failures[0].tool == "exec_command"
    assert codex.list_sessions("/w")[0].errors == 1


def test_unknown_outcomes_and_started_item_transition(tmp_path: Path, monkeypatch) -> None:
    start = _command("transition", None, status="inProgress")
    start["payload"]["type"] = "item_started"
    path, _ = _rollout(
        tmp_path,
        monkeypatch,
        [
            start,
            _command("transition", 0),
            _command("missing-exit", None),
            _command("failed-status", None, status="failed"),
            _record(
                "response_item",
                type="function_call",
                name="exec_command",
                call_id="unknown",
                arguments='{"cmd":"pending"}',
            ),
            _record(
                "response_item",
                type="function_call_output",
                call_id="unknown",
                output="Session identifier: 123; still running",
            ),
        ],
    )
    calls = [e for e in codex.parse(path) if e.kind == "tool"]
    assert [e.tag for e in calls] == ["ok", "", "err", ""]
    assert [e.seq for e in calls] == [3, 4, 5, 6]
    assert codex.list_sessions("/w")[0].errors == 1


def test_commands_without_identity_are_not_collapsed(tmp_path: Path, monkeypatch) -> None:
    command = _command("", 1)
    path, _ = _rollout(tmp_path, monkeypatch, [command, command])
    events = codex.parse(path)
    assert len([e for e in events if e.kind == "tool"]) == 2
    assert codex.list_sessions("/w")[0].errors == 2
