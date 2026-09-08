"""Codex archive conflicts and worktree scope through the CLI."""

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()


def _session(root: Path, sid: str, cwd: Path, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"rollout-{sid}.jsonl"
    records = [
        {"type": "session_meta", "payload": {"id": sid, "cwd": str(cwd)}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": text}},
    ]
    path.write_text("\n".join(json.dumps(record) for record in records))
    return path


def test_conflicting_active_and_archive_ids_are_not_silently_selected(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    project = tmp_path / "project"
    active = _session(tmp_path / "codex" / "sessions", "abcd-1234", project, "active evidence")
    archive = _session(
        tmp_path / "codex" / "archived_sessions", "abcd-1234", project, "archive evidence"
    )
    args = ["--codex", "--path", str(project)]
    exact = runner.invoke(app, [*args, "path", "abcd-1234"])
    assert exact.exit_code == 0 and str(active) in exact.stdout
    ambiguous = runner.invoke(app, [*args, "--archives", "path", "abcd-1234"])
    assert ambiguous.exit_code == 2
    assert "duplicate id" in ambiguous.stderr
    assert str(active) in ambiguous.stderr and str(archive) in ambiguous.stderr
    listing = runner.invoke(app, [*args, "--archives", "--json", "list"])
    assert listing.exit_code == 0
    assert len(listing.stdout.splitlines()) == 2


def test_codex_worktree_scope_includes_registered_sibling(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    project, sibling = tmp_path / "project", tmp_path / "sibling"
    subprocess.run(["git", "init", "-q", str(project)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "worktree", "add", "--detach", str(sibling)],
        check=True,
        capture_output=True,
    )
    _session(tmp_path / "codex" / "sessions", "abcd-1111", project.resolve(), "main evidence")
    _session(tmp_path / "codex" / "sessions", "abcd-2222", sibling.resolve(), "sibling evidence")
    args = ["--codex", "--path", str(project), "--json"]
    exact = runner.invoke(app, [*args, "list"])
    assert exact.exit_code == 0 and len(exact.stdout.splitlines()) == 1
    expanded = runner.invoke(app, [*args, "--worktrees", "list"])
    assert expanded.exit_code == 0
    assert {json.loads(line)["id"] for line in expanded.stdout.splitlines()} == {
        "abcd-1111",
        "abcd-2222",
    }
