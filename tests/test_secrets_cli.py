"""Default secret audits and nested cleaning share provider and scope flags."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.file_selection import reference
from test_providers import _write_claude, _write_codex
from test_secrets import FAKE_AWS

runner = CliRunner()


@pytest.fixture(params=[_write_claude, _write_codex])
def transcript(request, tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    path = request.param(tmp_path, monkeypatch)
    provider, ref = reference(path)
    record = (
        {"type": "event_msg", "payload": {"type": "user_message", "message": FAKE_AWS}}
        if ref.provider == "codex"
        else {"type": "user", "cwd": "/w", "message": {"content": FAKE_AWS}}
    )
    record["timestamp"] = "2026-07-24T17:00:00Z"
    with path.open("a") as stream:
        stream.write("\n" + json.dumps(record) + "\n")
    return path, provider, ref


@pytest.mark.parametrize("position", ["root", "group", "command"])
def test_clean_flag_positions_and_apply(transcript, position):
    path, _, ref = transcript
    scope = [f"--{ref.provider}", "--path", "/w", "--before", "2026-08-01"]
    commands = {
        "root": [*scope, "secrets", "clean", ref.id],
        "group": ["secrets", *scope, "clean", ref.id],
        "command": ["secrets", "clean", ref.id, *scope],
    }
    args = commands[position]
    original = path.read_bytes()
    preview = runner.invoke(app, args)
    assert preview.exit_code == 0, preview.output
    assert "DRY RUN" in preview.stdout and "sxr secrets clean --apply" in preview.stdout
    assert path.read_bytes() == original
    assert FAKE_AWS not in preview.output
    applied = runner.invoke(app, [*args, "--apply"])
    assert applied.exit_code == 0, applied.output
    assert FAKE_AWS.encode() not in path.read_bytes()
    assert runner.invoke(app, args).exit_code == 1


@pytest.mark.parametrize("selector", [[], ["@1"], ["audit", "@1"]])
def test_existing_audit_forms_still_work(transcript, selector):
    path, _, _ = transcript
    original = path.read_bytes()
    result = runner.invoke(app, ["--file", str(path), "secrets", *selector, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["kind"] == "aws-access-token"
    assert FAKE_AWS not in result.output
    assert path.read_bytes() == original


def test_help_places_clean_under_secrets():
    root = runner.invoke(app, ["--help"])
    group = runner.invoke(app, ["secrets", "--help"])
    leaf = runner.invoke(app, ["secrets", "clean", "--help"])
    assert root.exit_code == group.exit_code == leaf.exit_code == 0
    assert "clean" in group.stdout and "--apply" in leaf.stdout
    old = runner.invoke(app, ["clean"])
    assert old.exit_code == 2 and "No such command" in old.output


def test_clean_does_not_load_full_session_summaries(transcript, monkeypatch):
    path, provider, _ = transcript
    monkeypatch.setattr(provider, "parse", lambda *a: pytest.fail("full transcript parse"))
    monkeypatch.setattr(provider, "_summarize", lambda *a, **kw: pytest.fail("full summary"))
    result = runner.invoke(app, ["secrets", "clean", "--file", str(path)])
    assert result.exit_code == 0, result.output


def test_conflicting_provider_flags_remain_errors(transcript):
    path, _, _ = transcript
    result = runner.invoke(app, ["--codex", "secrets", "--claude", "clean", "--file", str(path)])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output
