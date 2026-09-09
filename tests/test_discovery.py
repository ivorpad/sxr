"""Explicit discovery coverage and source-preserving navigation."""

import json
import shlex
import subprocess

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.discovery import matches_path, project_paths
from sxr.providers import claude_code, codex

runner = CliRunner()


def claude(root, cwd, sid, text="needle", agent=None):
    project = root / "projects" / claude_code.flatten_cwd(str(cwd))
    path = project / f"{sid}.jsonl"
    if agent:
        path = project / sid / "subagents" / f"{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "cwd": str(cwd),
                "timestamp": "2026-07-20T10:00:00Z",
                "message": {"content": text},
            }
        )
        + "\n"
    )
    return path


def rollout(root, cwd, sid, text="needle", archived=False):
    directory = root / ("archived_sessions" if archived else "sessions")
    path = directory / f"rollout-{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "type": "session_meta",
            "payload": {"id": sid, "cwd": str(cwd)},
            "timestamp": "2026-07-20T10:00:00Z",
        },
        {"type": "event_msg", "payload": {"type": "user_message", "message": text}},
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_recursive_scope_uses_path_boundaries_and_is_opt_in(tmp_path, monkeypatch, provider):
    root, repo = tmp_path / "profile", tmp_path / "repo"
    writer = claude if provider == "claude" else rollout
    monkeypatch.setenv("CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME", str(root))
    writer(root, repo, "11111111")
    writer(root, repo / "child", "22222222")
    writer(root, tmp_path / "repo-other", "33333333")
    flags = [f"--{provider}", "--path", str(repo)]
    exact = runner.invoke(app, [*flags, "list", "--json"])
    assert exact.exit_code == 0, exact.output
    assert [json.loads(line)["id"] for line in exact.stdout.splitlines()] == ["11111111"]
    for args in (
        [*flags, "--recursive", "list", "--json"],
        [*flags, "list", "--recursive", "--json"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert {json.loads(line)["id"] for line in result.stdout.splitlines()} == {
            "11111111",
            "22222222",
        }


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_recorded_symlink_cwd_matches_physical_path(tmp_path, monkeypatch, provider):
    repo, alias, root = tmp_path / "repo", tmp_path / "alias", tmp_path / "profile"
    repo.mkdir()
    alias.symlink_to(repo, target_is_directory=True)
    writer = claude if provider == "claude" else rollout
    writer(root, alias, "11111111")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME", str(root))
    result = runner.invoke(app, [f"--{provider}", "--path", str(repo), "path", "11111111"])
    assert result.exit_code == 0, result.output
    assert "11111111.jsonl" in result.stdout


def test_multiple_profiles_duplicates_and_unavailable_roots(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    first, second, missing = [tmp_path / name for name in ("first", "second", "missing")]
    original = claude(first, repo, "11111111")
    copied = claude(second, repo, "11111111")
    claude(second, repo, "22222222")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(first))
    default = runner.invoke(app, ["--path", str(repo), "list", "--json"])
    assert [json.loads(line)["id"] for line in default.stdout.splitlines()] == ["11111111"]
    result = runner.invoke(
        app,
        [
            "--path",
            str(repo),
            "--claude-root",
            str(first),
            "list",
            "--claude-root",
            str(second),
            "--claude-root",
            str(missing),
            "--coverage",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    records = {row["id"]: row for row in map(json.loads, result.stdout.splitlines())}
    assert set(records) == {"11111111", "22222222"}
    assert records["11111111"]["sources"] == [str(original), str(copied)]
    assert f"searched: {first / 'projects'}" in result.stderr
    assert f"searched: {second / 'projects'}" in result.stderr
    assert f"unavailable: {missing / 'projects'}" in result.stderr
    assert "1 duplicate copies" in result.stderr
    # Explicit roots replace the selected environment profile.
    replacement = runner.invoke(app, ["--path", str(repo), "--claude-root", str(missing), "list"])
    assert "no sessions found" in replacement.output
    assert str(first / "projects") not in replacement.output


def test_conflicting_profile_copies_reject_exact_id(tmp_path):
    repo = tmp_path / "repo"
    first, second = tmp_path / "first", tmp_path / "second"
    claude(first, repo, "11111111", "one")
    claude(second, repo, "11111111", "two")
    result = runner.invoke(
        app,
        [
            "--path",
            str(repo),
            "--claude-root",
            str(first),
            "--claude-root",
            str(second),
            "show",
            "11111111",
        ],
    )
    assert result.exit_code == 2, result.output
    assert str(first) in result.stderr and str(second) in result.stderr


def test_nested_agent_round_trips_count_locate_and_zoom_from_another_cwd(tmp_path, monkeypatch):
    root, repo = tmp_path / "profile with spaces", tmp_path / "repo"
    claude(root, repo, "11111111", "parent")
    child = claude(root, repo, "11111111", "child-only-needle", agent="agent-a1")
    claude(root, repo, "22222222", "other parent")
    claude(root, repo, "22222222", "other child", agent="agent-a1")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    flags = ["--path", str(repo)]
    absent = runner.invoke(app, [*flags, "grep", "-c", "child-only-needle"])
    assert absent.exit_code == 1
    result = runner.invoke(app, [*flags, "--include-agents", "grep", "-c", "child-only-needle"])
    assert result.exit_code == 0, result.output
    assert "11111111/agent-a1\t1\t1" in result.stdout
    zoom = next(
        line.split("zoom: ", 1)[1] for line in result.stdout.splitlines() if "zoom: " in line
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "wrong-profile"))
    args = shlex.split(zoom)[1:]
    shown = runner.invoke(app, args)
    assert shown.exit_code == 0, shown.output
    assert str(child) in shown.stdout and "#0001" in shown.stdout
    assert "child-only-needle" in shown.stdout
    show_at = args.index("show")
    located = runner.invoke(
        app, [*args[:show_at], "grep", "child-only-needle", "11111111/agent-a1"]
    )
    assert located.exit_code == 0, located.output
    assert "11111111/agent-a1\t#0001" in located.stdout


def test_archive_only_and_duplicate_active_copy(tmp_path, monkeypatch):
    root, repo = tmp_path / "codex", tmp_path / "repo"
    archived = rollout(root, repo, "11111111", archived=True)
    active = rollout(root, repo, "22222222")
    copy = rollout(root, repo, "22222222", archived=True)
    monkeypatch.setenv("CODEX_HOME", str(root))
    assert {ref.id for ref in codex.list_sessions(str(repo))} == {"22222222"}
    refs = codex.list_sessions(str(repo), include_archives=True)
    assert {ref.id for ref in refs} == {"11111111", "22222222"}
    duplicate = next(ref for ref in refs if ref.id == "22222222")
    assert duplicate.path == active
    assert duplicate.extra["provenance"] == [str(active), str(copy)]
    result = runner.invoke(
        app,
        [
            "--codex",
            "--path",
            str(repo),
            "grep",
            "-c",
            "needle",
            "11111111",
            "--archives",
            "--coverage",
        ],
    )
    assert result.exit_code == 0, result.output
    assert str(root / "archived_sessions") in result.stderr
    zoom = next(
        line.split("zoom: ", 1)[1] for line in result.stdout.splitlines() if "zoom: " in line
    )
    args = shlex.split(zoom)
    assert args[:3] == ["sxr", "--file", str(archived)]
    monkeypatch.chdir(tmp_path)
    shown = runner.invoke(app, args[1:])
    assert shown.exit_code == 0, shown.output
    assert str(archived) in shown.stdout


def test_worktree_association_is_opt_in_and_registered(tmp_path):
    repo, sibling = tmp_path / "repo", tmp_path / "sibling"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-qb", "child", str(sibling)], check=True
    )
    assert project_paths(str(repo)) == [repo]
    assert set(project_paths(str(repo), worktrees=True)) == {repo, sibling}
    assert matches_path(str(sibling), project_paths(str(repo), worktrees=True))
    assert not matches_path(str(tmp_path / "repo-other"), [repo], recursive=True)


def test_empty_json_list_keeps_stdout_machine_readable(tmp_path, monkeypatch):
    root = tmp_path / "nondefault-profile"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    result = runner.invoke(app, ["--path", str(tmp_path), "list", "--json"])
    assert result.exit_code == 0 and result.stdout == ""
    assert f"unavailable: {root / 'projects'}" in result.stderr


def test_colliding_short_ids_are_printed_as_distinct_full_ids(tmp_path, monkeypatch):
    root, repo = tmp_path / "profile", tmp_path / "repo"
    claude(root, repo, "11111111-aaaa")
    claude(root, repo, "11111111-bbbb")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    result = runner.invoke(app, ["--path", str(repo), "grep", "-c", "needle"])
    assert result.exit_code == 0, result.output
    assert "11111111-aaaa\t" in result.stdout and "11111111-bbbb\t" in result.stdout


def test_coverage_counts_codex_thread_lineage(tmp_path, monkeypatch):
    root, repo = tmp_path / "codex", tmp_path / "repo"
    path = rollout(root, repo, "11111111")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["payload"]["parent_thread_id"] = "22222222"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    monkeypatch.setenv("CODEX_HOME", str(root))
    result = runner.invoke(app, ["--codex", "--path", str(repo), "list", "--coverage"])
    assert result.exit_code == 0, result.output
    assert "1 agents" in result.stderr
