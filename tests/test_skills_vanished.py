"""Removed files must not poison an unrelated lookup through a saved index error."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.skills_store import map_path

runner = CliRunner()


@pytest.fixture(autouse=True)
def skill_home(tmp_path, monkeypatch):
    for key, suffix in (
        ("HOME", ""),
        ("CODEX_HOME", ".codex"),
        ("CLAUDE_CONFIG_DIR", ".claude"),
        ("XDG_CONFIG_HOME", ".config"),
    ):
        monkeypatch.setenv(key, str(tmp_path / suffix))


def fixture(tmp_path):
    paths = [tmp_path / name / "SKILL.md" for name in ("notify", "unrelated")]
    for path in paths:
        path.parent.mkdir()
        path.write_text(path.parent.name)
    result = runner.invoke(app, ["skills", "--index"])
    assert result.exit_code == 0, result.output
    return paths


def notify():
    result = runner.invoke(app, ["skills", "notify", "--json"])
    assert result.exit_code == 0 and not result.stderr, result.output
    data = json.loads(result.stdout)
    assert data["complete"] and data["total"] == 1 and not data["errors"]
    return data


def test_old_map_migration_skips_deleted_unrelated_files(tmp_path, monkeypatch):
    import sxr.skills_store as store

    kept, removed = fixture(tmp_path)
    data = json.loads(map_path().read_text())
    data["version"] = 2
    for record in data["skills"]:
        record.pop("sha256")
        record.pop("signature")
    map_path().write_text(json.dumps(data))
    removed.unlink()
    monkeypatch.setattr(store, "scan", lambda *a: pytest.fail("rescanned instead of migrating"))
    assert notify()["skills"][0]["path"] == str(kept)
    stored = json.loads(map_path().read_text())
    assert len(stored["skills"]) == 1 and not stored["errors"]


def test_file_disappearing_after_discovery_is_skipped(tmp_path, monkeypatch):
    import sxr.skills_content as content

    kept, removed = fixture(tmp_path)
    identify = content.identify

    def disappear(record, previous=None):
        if record["path"] == str(removed):
            removed.unlink(missing_ok=True)
        return identify(record, previous)

    monkeypatch.setattr(content, "identify", disappear)
    result = runner.invoke(app, ["skills", "--index", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["complete"] and data["files"] == 1
    assert notify()["skills"][0]["path"] == str(kept)


def test_poisoned_version_three_map_repairs_without_rescan(tmp_path, monkeypatch):
    import sxr.skills_store as store

    kept, removed = fixture(tmp_path)
    data = json.loads(map_path().read_text())
    for record in data["skills"]:
        if record["path"] == str(removed):
            record.update(sha256=None, signature=None)
    data["errors"] = [f"{removed}: No such file or directory"]
    map_path().write_text(json.dumps(data))
    removed.unlink()
    monkeypatch.setattr(store, "scan", lambda *a: pytest.fail("rescanned to repair old error"))
    assert notify()["skills"][0]["path"] == str(kept)
    result = runner.invoke(app, ["skills", "notify"])
    assert result.exit_code == 0 and not result.stderr


def test_permission_errors_are_retained_and_summarized(tmp_path, monkeypatch):
    import sxr.skills_content as content

    _, protected = fixture(tmp_path)
    data = json.loads(map_path().read_text())
    for record in data["skills"]:
        if record["path"] == str(protected):
            record.update(sha256=None, signature=None)
    data["errors"] = [f"{protected}: Permission denied"]
    map_path().write_text(json.dumps(data))
    original = content.os.stat

    def denied(path, *args, **kwargs):
        if Path(path) == protected:
            raise PermissionError(13, "Permission denied", str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(content.os, "stat", denied)
    result = runner.invoke(app, ["skills", "notify"])
    assert result.exit_code == 2
    assert result.stderr.count("\n") == 1 and "1 discovery errors" in result.stderr
    assert str(protected) not in result.stderr
    result = runner.invoke(app, ["skills", "notify", "--json"])
    assert result.exit_code == 2
    info = json.loads(result.stdout)
    assert not info["complete"] and info["errors"] == data["errors"]
