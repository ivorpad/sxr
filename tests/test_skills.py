"""Skill lookup preserves aliases, scope, and freshness without reading instruction bodies."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.skills_cli import main
from sxr.skills_store import map_path

runner = CliRunner()


@pytest.fixture(autouse=True)
def skill_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))


def skill(root, name="notify"):
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: notify\n---\nDo not execute this test instruction.\n")
    return path


def lookup(*arguments, code=0):
    result = runner.invoke(app, ["skills", *map(str, arguments), "--json"])
    assert result.exit_code == code, result.output
    return json.loads(result.stdout)


def test_default_roots_merge_symlinks_and_match_names(tmp_path):
    original = skill(tmp_path / ".agents/skills")
    alias = tmp_path / ".claude/skills/send-alert"
    alias.parent.mkdir(parents=True)
    alias.symlink_to(original.parent, target_is_directory=True)
    data = lookup("notify")
    assert data["complete"] and data["total"] == 1
    assert data["skills"][0]["path"] == str(original)
    assert data["skills"][0]["aliases"] == sorted([str(original), str(alias / "SKILL.md")])
    assert lookup("send-alert", "--exact")["skills"] == data["skills"]
    assert lookup("NOTIFY", "--exact")["skills"] == data["skills"]
    assert map_path().stat().st_mode & 0o777 == 0o600


def test_paths_aliases_and_both_parsers(tmp_path, capsys):
    original = skill(tmp_path / ".agents/skills")
    alias = tmp_path / ".claude/skills/notify"
    alias.parent.mkdir(parents=True)
    alias.symlink_to(original.parent, target_is_directory=True)
    assert main(["notify", "--paths"]) == 0
    assert capsys.readouterr().out.strip() == str(original)
    result = runner.invoke(app, ["skills", "notify", "--paths", "--aliases"])
    assert result.exit_code == 0
    assert set(result.stdout.splitlines()) == {str(original), str(alias / "SKILL.md")}
    assert main(["notify", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == lookup("notify")


def test_warm_lookup_does_not_walk_or_read_skills(tmp_path, monkeypatch):
    import sxr.skills_catalog as catalog

    source = skill(tmp_path / ".agents/skills")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path != source, "read skill instruction body"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    expected = lookup("notify")
    before = map_path().stat().st_mtime_ns
    skill(tmp_path / "Developer/new-install", "new-skill")
    monkeypatch.setattr(catalog, "scan", lambda *args: pytest.fail("walked skill tree"))
    import sxr.skills_store as store

    monkeypatch.setattr(store, "scan", lambda *args: pytest.fail("walked skill tree"))
    assert lookup("notify") == expected
    assert map_path().stat().st_mtime_ns == before


def test_reindex_discovers_new_locations_removals_and_symlink_retargeting(tmp_path):
    root = tmp_path / ".agents/skills"
    source = skill(root)
    assert lookup("notify")["total"] == 1
    second = skill(tmp_path / ".codex/skills", "notify-codex")
    assert lookup("notify")["total"] == 1
    lookup("--index")
    assert lookup("notify")["total"] == 2
    source.unlink()
    assert not lookup("notify", code=2)["complete"]
    lookup("--index")
    assert lookup("notify")["skills"][0]["path"] == str(second)
    second.parent.rename(second.parent.with_name("renamed"))
    lookup("--index")
    assert lookup("renamed")["total"] == 1
    assert lookup("notify", code=1)["total"] == 0
    target = skill(tmp_path / "external", "target")
    source.symlink_to(target)
    lookup("--index")
    assert lookup("notify")["skills"][0]["path"] == str(target)
    target.unlink()
    lookup("--index")
    assert lookup("notify", code=1)["total"] == 0


def test_custom_roots_persist_only_when_indexing(tmp_path):
    first = skill(tmp_path / "first")
    second = skill(tmp_path / "second")
    third = skill(tmp_path / "third")
    data = lookup("--index", "--root", first.parent.parent, "--root", second.parent.parent)
    assert data["total"] == 2
    assert lookup("notify")["skills"] == data["skills"]
    assert lookup("notify", "--root", third.parent.parent)["skills"][0]["path"] == str(third)
    assert lookup("notify")["skills"] == data["skills"]
    default = skill(tmp_path / ".agents/skills")
    paths = {record["path"] for record in lookup("--index", "--defaults")["skills"]}
    assert paths == {str(path) for path in (first, second, third, default)}


def test_exact_qualified_queries_and_limits(tmp_path):
    first = skill(tmp_path / ".agents/skills")
    second = skill(tmp_path / ".codex/plugins/cache/demo/1.0/skills", "notify-more")
    assert lookup("notify", "--exact")["total"] == 1
    data = lookup("notify", "-n", "1")
    assert data["total"] == 2 and len(data["skills"]) == 1
    assert data["skills"][0]["path"] == str(first)
    assert lookup("demo:notify-more")["skills"][0]["path"] == str(second)


def test_bounded_output_keeps_full_index(tmp_path):
    for number in range(25):
        skill(tmp_path / ".agents/skills", f"example-{number}")
    result = runner.invoke(app, ["skills", "--index"])
    assert result.exit_code == 0 and not result.stdout
    assert "discovered 25 skills" in result.stderr
    data = lookup()
    assert data["total"] == 25 and len(data["skills"]) == 20
    assert len(lookup("-n", "0")["skills"]) == 25
    result = runner.invoke(app, ["skills", "--paths"])
    assert result.exit_code == 0 and len(result.stdout.splitlines()) == 25


def test_cycles_missing_roots_and_partial_coverage(tmp_path):
    root = tmp_path / "external"
    source = skill(root)
    (root / "loop").symlink_to(root, target_is_directory=True)
    data = lookup("--root", root, "--root", tmp_path / "missing", code=2)
    assert data["total"] == 1 and data["skills"][0]["path"] == str(source)
    assert not data["complete"] and len(data["errors"]) == 1
    assert data["cycles_skipped"] == 1
    assert lookup("--root", root)["complete"]


@pytest.mark.parametrize("body", ["broken json", '{"version":99}', '{"version":1,"skills":[0]}'])
def test_corrupt_map_is_rebuilt(tmp_path, body):
    skill(tmp_path / ".agents/skills")
    lookup("notify")
    map_path().write_text(body)
    assert lookup("notify")["total"] == 1


def test_index_under_scanned_root_does_not_invalidate_itself(tmp_path):
    skill(tmp_path / "skills")
    assert lookup("--index", "--root", tmp_path)["complete"]
    assert lookup("notify")["complete"]


def test_discovery_needs_only_skill_filename_in_any_directory(tmp_path):
    sources = {
        skill(tmp_path / "Developer/project/extensions", "release-helper"),
        skill(tmp_path / "Downloads/unpacked", "example"),
        skill(tmp_path / ".hidden/arbitrary", "hidden-skill"),
        skill(tmp_path / "some-tool/node_modules/bundled", "dependency-skill"),
    }
    (tmp_path / "SKILL.txt").write_text("not a skill")
    data = lookup("--index")
    assert data["complete"] and data["indexed_at"]
    assert {record["path"] for record in data["skills"]} == {str(path) for path in sources}
    latest = skill(tmp_path / "new/location/without-known-parent", "brand-new")
    assert lookup("brand-new", code=1)["total"] == 0
    lookup("--index")
    assert lookup("brand-new")["skills"][0]["path"] == str(latest)


def test_each_physical_directory_is_walked_once(tmp_path, monkeypatch):
    import sxr.skills_catalog as catalog

    original = skill(tmp_path / "Developer/extensions")
    for name in ("first", "second"):
        (tmp_path / name).symlink_to(original.parent.parent, target_is_directory=True)
    seen = set()
    scandir = catalog.os.scandir

    def once(path):
        physical = Path(path).resolve()
        assert physical not in seen, f"Walked {physical} again through a symlink"
        seen.add(physical)
        return scandir(path)

    monkeypatch.setattr(catalog.os, "scandir", once)
    data = lookup("--index")
    assert data["total"] == 1
    assert set(data["skills"][0]["aliases"]) == {
        str(original),
        str(tmp_path / "first/notify/SKILL.md"),
        str(tmp_path / "second/notify/SKILL.md"),
    }


def test_old_default_map_migrates_to_home_discovery(tmp_path):
    source = skill(tmp_path / "Developer/new-place")
    map_path().parent.mkdir(parents=True, exist_ok=True)
    map_path().write_text(
        json.dumps(
            dict(
                version=1,
                custom=False,
                roots=[str(tmp_path / ".agents/skills")],
                watched={},
                skills=[],
                errors=[],
                coverage=[],
            )
        )
    )
    assert lookup("notify")["skills"][0]["path"] == str(source)
    assert json.loads(map_path().read_text())["version"] == 2


def test_changed_alias_is_not_printed_from_old_snapshot(tmp_path):
    first = skill(tmp_path / "Developer", "first")
    second = skill(tmp_path / "Developer", "second")
    alias = tmp_path / "notify"
    alias.symlink_to(first.parent, target_is_directory=True)
    lookup("--index")
    alias.unlink()
    alias.symlink_to(second.parent, target_is_directory=True)
    data = lookup("notify", code=2)
    assert not data["complete"]
    assert str(alias / "SKILL.md") not in data["skills"][0]["aliases"]
    lookup("--index")
    assert lookup("notify")["skills"][0]["path"] == str(second)


def test_discovery_retries_interrupted_reads_and_reports_permissions(tmp_path, monkeypatch):
    import sxr.skills_catalog as catalog

    source = skill(tmp_path / "Developer")
    protected = tmp_path / "protected"
    protected.mkdir()
    scandir = catalog.os.scandir
    interrupted = False

    def flaky(path):
        nonlocal interrupted
        if Path(path) == protected:
            raise PermissionError(13, "Permission denied", path)
        if Path(path) == source.parent and not interrupted:
            interrupted = True
            raise InterruptedError(4, "Interrupted system call", path)
        return scandir(path)

    monkeypatch.setattr(catalog.os, "scandir", flaky)
    data = lookup("--index", code=2)
    assert interrupted and data["total"] == 1
    assert len(data["errors"]) == 1 and "Permission denied" in data["errors"][0]
    assert data["skills"][0]["path"] == str(source)


def test_uncached_lookup_and_clear(tmp_path, monkeypatch):
    skill(tmp_path / ".agents/skills")
    monkeypatch.setenv("SXR_NO_CACHE", "1")
    assert lookup("notify")["total"] == 1
    assert not map_path().exists()
    monkeypatch.delenv("SXR_NO_CACHE")
    lookup("notify")
    result = runner.invoke(app, ["skills", "--clear"])
    assert result.exit_code == 0 and not map_path().exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--limit", "-1"],
        ["--exact"],
        ["--aliases"],
        ["--defaults"],
        ["notify", "--clear"],
        ["--index", "--defaults", "--root", "/tmp"],
    ],
)
def test_bad_skill_flags_are_usage_errors(arguments):
    result = runner.invoke(app, ["skills", *arguments])
    assert result.exit_code == 2 and "error:" in result.output
