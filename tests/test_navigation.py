"""Follow-up commands remain executable after changing working directory."""

import json
import shlex

from typer.testing import CliRunner

from sxr.cli import app
from sxr.providers.claude_code import flatten_cwd

runner = CliRunner()


def test_relative_home_and_absolute_scopes_produce_same_session(tmp_path, monkeypatch):
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    root = tmp_path / ".claude"
    project = root / "projects" / flatten_cwd(str(repo))
    project.mkdir(parents=True)
    path = project / "aaaabbbb-cccc.jsonl"
    path.write_text(
        json.dumps({"type": "user", "cwd": str(repo), "message": {"content": "needle"}})
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(repo)
    for scope in (".", str(repo), "~/repo with spaces"):
        result = runner.invoke(app, ["--path", scope, "grep", "-c", "needle"])
        assert result.exit_code == 0, result.output
        zoom = next(
            line.split("zoom: ", 1)[1] for line in result.output.splitlines() if "zoom: " in line
        )
        args = shlex.split(zoom)
        assert args[1:4] == ["--claude", "--path", str(repo)]
        assert "aaaabbbb-cccc" in args
        with monkeypatch.context() as other:
            other.chdir(tmp_path)
            shown = runner.invoke(app, args[1:])
            assert shown.exit_code == 0, shown.output
            assert str(path) in shown.output
            assert "#0001" in shown.output
            assert "needle" in shown.output


def test_symlink_scope_resolves_to_recorded_canonical_path(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    root = tmp_path / ".claude"
    project = root / "projects" / flatten_cwd(str(repo))
    project.mkdir(parents=True)
    (project / "aaaabbbb-cccc.jsonl").write_text(
        json.dumps({"type": "user", "cwd": str(repo), "message": {"content": "needle"}})
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    found = runner.invoke(app, ["--path", str(alias), "path"])
    assert found.exit_code == 0, found.output
    assert "aaaabbbb-cccc.jsonl" in found.output


def test_relative_codex_home_reports_absolute_source_provenance(tmp_path, monkeypatch):
    root = tmp_path / "profile"
    sessions = root / "sessions"
    sessions.mkdir(parents=True)
    path = sessions / "rollout-aaaabbbb.jsonl"
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "aaaabbbb", "cwd": str(tmp_path)}})
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", "profile")
    result = runner.invoke(app, ["--codex", "list", "--coverage", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["sources"] == [str(path)]
    assert "1 sources in path scope" in result.stderr


def test_list_view_handles_empty_and_zero_visible_rows(capsys):
    from pathlib import Path

    from sxr.model import SessionRef
    from sxr.views_info import list_view

    assert list_view([], False, None) == 0
    ref = SessionRef("claude", "aaaabbbb", Path("unused.jsonl"))
    assert list_view([ref], False, -1) == 0
    assert "show @N" in capsys.readouterr().out


def test_conflicting_profile_copies_navigate_by_handles_after_time_window(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    first, second = tmp_path / "first profile", tmp_path / "second profile"
    sid = "aaaabbbb-cccc"
    paths = {}
    records = [
        (first, "ffff1111", "2026-07-24T10:00:00Z", "newer excluded"),
        (first, "bbbb1111", "2026-07-21T11:00:00Z", "unique in scope"),
        (first, sid, "2026-07-21T10:00:00Z", "needle-alpha"),
        (second, sid, "2026-07-20T10:00:00Z", "needle-beta"),
        (second, "eeee1111", "2026-07-18T10:00:00Z", "older excluded"),
    ]
    for profile, session, stamp, text in records:
        project = profile / "projects" / flatten_cwd(str(repo))
        project.mkdir(parents=True, exist_ok=True)
        path = project / f"{session}.jsonl"
        path.write_text(
            json.dumps(
                {"type": "user", "cwd": str(repo), "timestamp": stamp, "message": {"content": text}}
            )
        )
        paths[text] = path
    flags = [
        "--claude",
        "--path",
        str(repo),
        "--claude-root",
        str(first),
        "--claude-root",
        str(second),
        "--since",
        "2026-07-20",
        "--before",
        "2026-07-22",
    ]
    monkeypatch.chdir(tmp_path)
    for needle, handle in (("needle-alpha", "@2"), ("needle-beta", "@3")):
        result = runner.invoke(app, [*flags, "grep", "-c", needle])
        assert result.exit_code == 0, result.output
        assert f"{handle}\t1\t1\t" in result.stdout
        zoom = next(
            line.split("zoom: ", 1)[1] for line in result.stdout.splitlines() if "zoom: " in line
        )
        args = shlex.split(zoom)[1:]
        assert args[args.index("show") + 1] == handle
        assert args[: args.index("show")] == flags
        shown = runner.invoke(app, args)
        assert shown.exit_code == 0, shown.output
        assert f"file:     {paths[needle]}" in shown.stdout
        assert "#0001" in shown.stdout and needle in shown.stdout
        located = runner.invoke(app, [*flags, "grep", needle, handle])
        assert located.exit_code == 0, located.output
        assert f"{handle}\t#0001" in located.stdout
    rejected = runner.invoke(app, [*flags, "show", sid])
    assert rejected.exit_code == 2
    assert str(paths["needle-alpha"]) in rejected.stderr
    assert str(paths["needle-beta"]) in rejected.stderr
    # A narrower time window removes the conflict, restoring the full-ID hint.
    unique_flags = [*flags[:-4], "--since", "2026-07-21", "--before", "2026-07-22"]
    unique = runner.invoke(app, [*unique_flags, "grep", "-c", "needle-alpha"])
    assert unique.exit_code == 0, unique.output
    assert f"show {sid} --around 1" in unique.stdout
