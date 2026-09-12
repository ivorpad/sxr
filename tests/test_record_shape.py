"""Both providers and their caches skip non-object records without moving coordinates."""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.file_selection import reference
from test_providers import _write_claude, _write_codex


@pytest.mark.parametrize("writer", [_write_claude, _write_codex])
def test_non_object_records_preserve_later_evidence(tmp_path, monkeypatch, writer):
    path = writer(tmp_path, monkeypatch)
    provider, ref = reference(path)
    first = json.loads(path.read_text().splitlines()[0])
    last = (
        {"type": "event_msg", "payload": {"type": "user_message", "message": "later needle"}}
        if ref.provider == "codex"
        else {"type": "user", "message": {"content": "later needle"}}
    )
    rows = [first, 42, [], None, "scalar", True, last]
    original = "\n".join(map(json.dumps, rows)) + "\n{torn"
    path.write_text(original)
    events = provider.parse(path)
    assert [event.seq for event in events] == [1, 7]
    assert events[-1].raw["line"] == last
    runner = CliRunner()
    for args in (
        ["show", "--around", "7", "--context", "0", "--json"],
        ["grep", "later", "--json"],
    ):
        for _ in range(2):
            result = runner.invoke(app, [*args, "--file", str(path)])
            assert result.exit_code == 0, result.output
            assert json.loads(result.stdout) == last
        monkeypatch.setenv("SXR_NO_CACHE", "1")
        direct = runner.invoke(app, [*args, "--file", str(path)])
        assert direct.exit_code == 0 and direct.stdout == result.stdout
        monkeypatch.delenv("SXR_NO_CACHE")
    ranked = runner.invoke(app, ["find", "later", "--file", str(path), "--json"])
    assert ranked.exit_code == 0, ranked.output
    assert json.loads(ranked.stdout)["results"][0]["evidence"][0]["seq"] == 7
    assert path.read_text() == original
