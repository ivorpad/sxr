"""Full text and empty selections behave alike in direct and cached read views."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()


@pytest.fixture
def transcript(tmp_path):
    path = tmp_path / "full.jsonl"
    text = "long fixture text\n" * 4000 + "unique ending"
    record = {"type": "user", "message": {"content": text}}
    path.write_text(json.dumps(record))
    return path, record


def test_full_bypasses_budget_but_honors_row_limit(transcript):
    path, record = transcript
    with path.open("a") as stream:
        stream.write("\n" + json.dumps({"type": "user", "message": {"content": "omitted"}}))
    result = runner.invoke(app, ["show", "--file", str(path), "--full", "--budget", "1", "-n", "1"])
    assert result.exit_code == 0
    assert record["message"]["content"] in result.stdout
    assert "omitted" not in result.stdout and "1 more events" in result.stdout
    assert "chars]" not in result.stdout


@pytest.mark.parametrize(
    "selection",
    [
        ["--type", "missing"],
        ["--errors"],
        ["--around", "999"],
        ["--range", "9:12"],
        ["--tail", "0"],
    ],
)
@pytest.mark.parametrize("json_out", [False, True])
@pytest.mark.parametrize("cache", [False, True])
def test_empty_selection_exit_is_consistent(transcript, monkeypatch, selection, json_out, cache):
    path, _ = transcript
    if not cache:
        monkeypatch.setenv("SXR_NO_CACHE", "1")
    args = ["show", "--file", str(path), *selection, *(["--json"] if json_out else [])]
    for _ in range(2):
        result = runner.invoke(app, args)
        assert result.exit_code == 1, result.output
        assert "unique ending" not in result.stdout
        if json_out:
            assert result.stdout == ""


def test_negative_tail_is_usage_error(transcript):
    path, _ = transcript
    result = runner.invoke(app, ["show", "--file", str(path), "--tail", "-1"])
    assert result.exit_code == 2
    assert "tail" in result.output and "Traceback" not in result.output
