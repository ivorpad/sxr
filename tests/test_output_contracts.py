"""Row limits preserve raw records, scope totals and masked cleaning output."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.find_cli import main as find_main
from sxr.skills_cli import main as skills_main
from test_providers import _write_claude

runner = CliRunner()
PASSWORD = "SyntheticOutputContract2026!"


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    path = _write_claude(tmp_path, monkeypatch)
    records = [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "first " * 2000},
                    {"type": "text", "text": "second block"},
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash", "id": "a", "input": {"command": "false"}},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "id": "b",
                        "input": {"file_path": "/tmp/x"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "a", "is_error": True, "content": "one"},
                    {"type": "tool_result", "tool_use_id": "b", "is_error": True, "content": "two"},
                ]
            },
        },
        {"type": "user", "message": {"content": "last prompt"}},
        {"type": "assistant", "isApiErrorMessage": True, "message": {"content": "API error"}},
    ]
    path.write_text("\n".join(map(json.dumps, records)))
    other = path.with_name("bbbb2222.jsonl")
    other.write_bytes(path.read_bytes())
    return path, other, records


@pytest.mark.parametrize(
    "command,record_index,total", [("show", 0, 4), ("prompts", 0, 2), ("errors", 2, 2)]
)
@pytest.mark.parametrize("position", ["root", "command"])
def test_json_limits_complete_distinct_records(corpus, command, record_index, total, position):
    path, _, records = corpus
    command_args = [command, "--file", str(path), "--json"]
    args = ["-n", "1", *command_args] if position == "root" else [*command_args, "-n", "1"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == records[record_index]
    assert f"shown 1 of {total}" in result.stderr
    unlimited = runner.invoke(app, [*command_args, "-n", "0"])
    assert len(unlimited.stdout.splitlines()) == total


@pytest.mark.parametrize("command", ["errors", "stats", "path"])
@pytest.mark.parametrize("json_out", [False, True])
def test_limits_span_selected_sessions(corpus, command, json_out):
    args = [command, "@1:@2", "--path", "/w", "-n", "1", *(["--json"] if json_out else [])]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    rows = result.stdout.splitlines()
    if command == "errors" and not json_out:
        rows = [row for row in rows if row.startswith("#0")]
    else:
        rows = [row for row in rows if row and not row.startswith("#")]
    assert len(rows) == 1
    assert "more" in result.output
    if json_out:
        parsed = json.loads(result.stdout)
        if command == "stats":
            assert "provider" in parsed and "records.text" in parsed


def test_tool_row_limit_keeps_full_json_aggregate(corpus):
    path, _, _ = corpus
    args = ["tools", "--file", str(path), "-n", "1"]
    result = runner.invoke(app, args)
    rows = [r for r in result.stdout.splitlines() if not r.startswith("#")]
    assert len(rows) == 1 and "1 more tools" in result.stdout
    data = json.loads(runner.invoke(app, [*args, "--json"]).stdout)
    assert data["calls"] == {"Bash": 1, "Read": 1}


@pytest.mark.parametrize("position", ["root", "group", "command"])
def test_clean_limit_caps_reporting_without_narrowing_apply(corpus, position):
    path, other, _ = corpus
    for file in (path, other):
        file.write_text(
            json.dumps(
                {"type": "user", "cwd": "/w", "message": {"content": f"password = {PASSWORD}"}}
            )
        )
    flags = ["--json", "-n", "1"]
    args = {
        "root": [*flags, "secrets", "clean"],
        "group": ["secrets", *flags, "clean"],
        "command": ["secrets", "clean", *flags],
    }[position] + ["--path", "/w"]
    preview = runner.invoke(app, args)
    assert preview.exit_code == 0, preview.output
    assert json.loads(preview.stdout)["applied"] is False
    assert "2 occurrences across 2 files" in preview.stderr and "1 more file rows" in preview.stderr
    assert all(PASSWORD in file.read_text() for file in (path, other))
    applied = runner.invoke(app, [*args, "--apply"])
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.stdout)["applied"] is True
    assert all(PASSWORD not in file.read_text() for file in (path, other))
    assert PASSWORD not in applied.output + preview.output


@pytest.mark.parametrize(
    "command",
    [
        [],
        ["list"],
        ["show"],
        ["prompts"],
        ["errors"],
        ["tools"],
        ["stats"],
        ["cmds"],
        ["path"],
        ["secrets"],
        ["secrets", "clean"],
        ["find", "needle"],
        ["skills"],
    ],
)
@pytest.mark.parametrize("position", ["root", "command"])
def test_negative_limits_rejected_before_discovery(command, position):
    args = ["-n", "-1", *command] if position == "root" else [*command, "-n", "-1"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output
    assert "limit" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("entry", [find_main, skills_main])
def test_fast_entry_points_reject_negative_limits(entry):
    with pytest.raises(SystemExit) as exc:
        entry(["-n", "-1"])
    assert exc.value.code == 2
