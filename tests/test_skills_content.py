"""Content groups retain scoped locations and split when instruction files change."""

import hashlib
import json
import os

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


def skill(root, name="notify", body=b"Send a test notification.\n"):
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def lookup(*arguments, code=0):
    result = runner.invoke(app, ["skills", *map(str, arguments), "--json"])
    assert result.exit_code == code, result.output
    return json.loads(result.stdout)


def test_identical_instructions_group_without_losing_locations_or_assets(tmp_path):
    first = skill(tmp_path / ".agents/skills")
    second = skill(tmp_path / "backup/project/.agents/skills")
    (first.parent / "run.py").write_text("print('first')")
    (second.parent / "run.py").write_text("print('second')")
    data = lookup("notify")
    assert (data["total"], data["unique"], data["files"]) == (1, 1, 2)
    record = data["skills"][0]
    assert record["path"] == str(first) and record["copies"] == 2
    assert record["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert {location["path"] for location in record["locations"]} == {str(first), str(second)}
    assert "signature" not in record
    expanded = lookup("notify", "--copies")
    assert (expanded["total"], expanded["unique"], expanded["files"]) == (2, 1, 2)
    assert all(record["copies"] == 2 for record in expanded["skills"])
    result = runner.invoke(app, ["skills", "notify", "--paths"])
    assert result.stdout.strip() == str(first)
    result = runner.invoke(app, ["skills", "notify", "--paths", "--copies"])
    assert set(result.stdout.splitlines()) == {str(first), str(second)}
    assert first.read_bytes() == second.read_bytes()
    assert (first.parent / "run.py").read_text() != (second.parent / "run.py").read_text()


def test_content_versions_and_aliases_stay_separate(tmp_path):
    first = skill(tmp_path / "one")
    second = skill(tmp_path / "two", body=b"Different instructions.\n")
    alias = tmp_path / "alias"
    alias.symlink_to(first.parent, target_is_directory=True)
    data = lookup("notify")
    assert data["unique"] == 2 and data["files"] == 2
    assert {item["path"] for item in data["skills"]} == {str(first), str(second)}
    assert all(item["copies"] == 1 for item in data["skills"])
    result = runner.invoke(app, ["skills", "notify", "--paths", "--copies", "--aliases"])
    assert set(result.stdout.splitlines()) == {str(first), str(second), str(alias / "SKILL.md")}


def test_scope_and_renamed_copies_match_before_grouping(tmp_path):
    first = skill(tmp_path / "active")
    second = skill(tmp_path / "backup", name="alert")
    assert lookup()["unique"] == 1
    data = lookup("alert", "--exact")
    assert data["files"] == 1 and data["skills"][0]["path"] == str(second)
    assert lookup("active:notify")["skills"][0]["path"] == str(first)
    assert lookup("backup:alert")["skills"][0]["path"] == str(second)
    assert lookup("backup:notify", code=1)["total"] == 0


def test_changed_copy_splits_before_limiting_and_reindex_reuses_unchanged_hash(
    tmp_path, monkeypatch
):
    import sxr.skills_content as content

    first = skill(tmp_path / "one")
    second = skill(tmp_path / "two")
    assert lookup("notify")["total"] == 1
    before = first.stat()
    first.write_bytes(b"Changed instructions.\n")
    os.utime(first, ns=(before.st_atime_ns, before.st_mtime_ns))
    changed = lookup("notify", "-n", "1", code=2)
    assert not changed["complete"] and changed["total"] == 2
    assert len(changed["skills"]) == 1
    hashed_paths = []
    digest = content.hashlib.file_digest

    def track(stream, *args):
        hashed_paths.append(os.fstat(stream.fileno()).st_ino)
        return digest(stream, *args)

    monkeypatch.setattr(content.hashlib, "file_digest", track)
    assert lookup("--index")["unique"] == 2
    assert hashed_paths == [first.stat().st_ino]
    assert lookup("notify")["unique"] == 2
    assert second.stat().st_ino not in hashed_paths


def test_deleted_representative_falls_back_to_surviving_copy(tmp_path):
    first = skill(tmp_path / "one")
    second = skill(tmp_path / "two")
    assert lookup("notify")["skills"][0]["path"] == str(first)
    first.unlink()
    data = lookup("notify", code=2)
    assert data["skills"][0]["path"] == str(second)
    assert data["skills"][0]["copies"] == 1
    assert lookup("--index")["complete"]


def test_version_two_migrates_hashes_without_rediscovery(tmp_path, monkeypatch):
    import sxr.skills_store as store

    skill(tmp_path / "one")
    skill(tmp_path / "two")
    lookup("--index")
    data = json.loads(map_path().read_text())
    data["version"] = 2
    for record in data["skills"]:
        record.pop("sha256")
        record.pop("signature")
    map_path().write_text(json.dumps(data))
    monkeypatch.setattr(store, "scan", lambda *a: pytest.fail("walked during hash migration"))
    assert lookup("notify")["unique"] == 1
    updated = json.loads(map_path().read_text())
    assert updated["version"] == 3 and updated["indexed_at"] == data["indexed_at"]


def test_unreadable_content_is_not_merged_with_readable_files(tmp_path, monkeypatch):
    import sxr.skills_content as content

    first = skill(tmp_path / "one")
    skill(tmp_path / "two")
    identify = content.identify

    def protected(record, previous=None):
        if record["path"] == str(first):
            raise PermissionError(13, "Permission denied", record["path"])
        return identify(record, previous)

    monkeypatch.setattr(content, "identify", protected)
    data = lookup("--index", code=2)
    assert data["files"] == 1 and data["unique"] == 1 and not data["complete"]
    stored = json.loads(map_path().read_text())["skills"]
    assert len(stored) == 2 and next(r for r in stored if r["path"] == str(first))["sha256"] is None


def test_changed_while_hashing_reports_incomplete(tmp_path, monkeypatch):
    import sxr.skills_content as content

    source = skill(tmp_path / "one")
    digest = content.hashlib.file_digest

    def changing(stream, *args):
        result = digest(stream, *args)
        with source.open("ab") as output:
            output.write(b"changed\n")
        return result

    monkeypatch.setattr(content.hashlib, "file_digest", changing)
    data = lookup("--index", code=2)
    assert not data["complete"] and data["files"] == 0
    assert any("changed while hashing" in error for error in data["errors"])


def test_file_that_changes_once_while_reading_is_retried(tmp_path, monkeypatch):
    import sxr.skills_content as content

    source = skill(tmp_path / "one")
    digest = content.hashlib.file_digest
    calls = 0

    def hydrated(stream, *args):
        nonlocal calls
        calls += 1
        result = digest(stream, *args)
        if calls == 1:
            source.write_bytes(b"Hydrated instructions.\n")
        return result

    monkeypatch.setattr(content.hashlib, "file_digest", hydrated)
    data = lookup("--index")
    assert data["complete"] and calls == 2
    assert data["skills"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.parametrize("field,value", [("sha256", "wrong"), ("signature", None)])
def test_corrupt_hash_metadata_rebuilds_the_map(tmp_path, field, value):
    source = skill(tmp_path / "one")
    lookup("--index")
    data = json.loads(map_path().read_text())
    data["skills"][0][field] = value
    map_path().write_text(json.dumps(data))
    assert (
        lookup("notify")["skills"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    )
