"""Audits cover stored tool values once and agree with the structured cleaner."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.secrets.records import clean_line, scan_line

PASSWORD = "SyntheticAuditValue_2026!"


@pytest.mark.parametrize(
    "value",
    [
        {"content": f'password = "{PASSWORD}"'},
        {"password": PASSWORD + " spaces"},
        {"arguments": json.dumps({"password": PASSWORD + " spaces"})},
        {"output": "wrapper " + json.dumps({"password": PASSWORD})},
    ],
)
def test_hidden_tool_values_agree_with_cleaner(tmp_path, monkeypatch, value):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    record = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "w",
                    "name": "Write",
                    "input": {"file_path": "/tmp/config", **value},
                },
                {"type": "text", "text": "done"},
            ]
        },
    }
    raw = json.dumps(record).encode()
    assert len(scan_line(raw)) == clean_line(raw)[1] == 1
    path = tmp_path / "session.jsonl"
    path.write_bytes(b"\n\n" + raw + b"\n")
    result = CliRunner().invoke(app, ["secrets", "--json", "--file", str(path)])
    assert result.exit_code == 0, result.output
    row = json.loads(result.stdout)
    assert row["hits"] == 1 and row["first"].endswith(":3")
    assert PASSWORD not in result.output
    assert path.read_bytes() == b"\n\n" + raw + b"\n"


@pytest.mark.parametrize("json_out", [False, True])
def test_limited_worklist_preserves_totals_and_fingerprints(tmp_path, monkeypatch, json_out):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    path = tmp_path / "secrets.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"content": "fixture"},
                "password": PASSWORD,
                "nested": {"password": PASSWORD + "2"},
            }
        )
    )
    args = ["secrets", "--file", str(path), *(["--json"] if json_out else [])]
    runner = CliRunner()
    full = runner.invoke(app, [*args, "-n", "0"])
    limited = runner.invoke(app, [*args, "-n", "1"])
    assert full.exit_code == limited.exit_code == 0
    assert "showing 1 of 2 distinct secrets; 1 more" in limited.output
    assert PASSWORD not in full.output + limited.output
    if json_out:
        assert json.loads(limited.stdout) == json.loads(full.stdout.splitlines()[0])
    else:
        assert "2 distinct secrets (0 certain)" in limited.stdout
