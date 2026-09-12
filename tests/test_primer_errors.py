"""Primer filesystem failures return useful diagnostics and preserve existing files."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sxr.cli import app


def test_parent_is_a_file(tmp_path):
    parent = tmp_path / "existing"
    parent.write_text("original")
    target = parent / "AGENTS.md"
    result = CliRunner().invoke(app, ["init", "--write", str(target)])
    assert result.exit_code == 2
    assert str(target) in result.stderr and "Traceback" not in result.output
    assert parent.read_text() == "original"


@pytest.mark.parametrize("option", ["--write", "--check"])
def test_directory_is_not_a_primer_file(tmp_path, option):
    result = CliRunner().invoke(app, ["init", option, str(tmp_path)])
    assert result.exit_code == 2
    assert str(tmp_path) in result.stderr and "Traceback" not in result.output


@pytest.mark.parametrize("option,method", [("--write", "write_text"), ("--check", "read_text")])
def test_denied_io_is_reported_at_the_command_boundary(tmp_path, monkeypatch, option, method):
    target = tmp_path / "AGENTS.md"
    target.write_text("existing instructions")
    original = getattr(Path, method)

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("synthetic access denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, method, denied)
    result = CliRunner().invoke(app, ["init", option, str(target)])
    assert result.exit_code == 2
    assert str(target) in result.stderr and "synthetic access denied" in result.stderr
    assert "Traceback" not in result.output
    assert target.read_bytes() == b"existing instructions"
