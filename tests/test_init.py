"""sxr init: primer text, the idempotent installer, target resolution, exit codes."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import sxr
from sxr.cli import app
from sxr.onboard import (
    MarkerError,
    check_primer,
    find_block,
    install_primer,
    nearest_agents_md,
    primer,
    user_agents_file,
)

runner = CliRunner()

OPEN = f"<!-- sxr:primer v{sxr.__version__} -->"
CLOSE = "<!-- /sxr:primer -->"
OLD = "<!-- sxr:primer v0.0.1 -->\nstale body\n<!-- /sxr:primer -->\n"


def test_init_emits_the_block_with_the_runtime_version() -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert result.stdout.startswith(f"{OPEN}\n")
    assert result.stdout.endswith(f"{CLOSE}\n")
    assert "sxr grep -c" in result.stdout


def test_version_is_not_baked_into_the_text() -> None:
    assert primer("9.9.9").startswith("<!-- sxr:primer v9.9.9 -->\n")
    assert "9.9.9" not in primer(sxr.__version__)


def test_write_creates_a_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "AGENTS.md"
    result = runner.invoke(app, ["init", "--write", str(target)])
    assert result.exit_code == 0
    assert target.read_text() == primer(sxr.__version__)
    assert "created" in result.stdout and str(target) in result.stdout


def test_write_appends_below_existing_prose(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("# House rules\n\nno tabs.\n")
    assert runner.invoke(app, ["init", "--write", str(target)]).exit_code == 0
    text = target.read_text()
    assert text.startswith("# House rules\n\nno tabs.\n\n")
    assert text.endswith(f"{CLOSE}\n")
    assert text.count(OPEN) == 1


def test_write_appends_a_newline_when_the_file_lacks_one(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("no trailing newline")
    install_primer(target, sxr.__version__)
    assert target.read_text() == f"no trailing newline\n\n{primer(sxr.__version__)}"


def test_write_replaces_an_older_block_and_keeps_its_neighbours(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(f"before\n\n{OLD}\nafter\n")
    assert runner.invoke(app, ["init", "--write", str(target)]).exit_code == 0
    text = target.read_text()
    assert text.startswith("before\n\n")
    assert text.endswith("\nafter\n")
    assert "stale body" not in text and "v0.0.1" not in text
    assert text.count(OPEN) == 1 and text.count(CLOSE) == 1


def test_write_twice_is_byte_identical(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("prose\n")
    assert install_primer(target, sxr.__version__) == "appended"
    once = target.read_bytes()
    assert install_primer(target, sxr.__version__) == "unchanged"
    assert target.read_bytes() == once


def test_write_on_a_created_file_is_also_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    assert install_primer(target, sxr.__version__) == "created"
    once = target.read_bytes()
    assert install_primer(target, sxr.__version__) == "unchanged"
    assert target.read_bytes() == once


@pytest.mark.parametrize(
    "text",
    [
        f"prose\n{OPEN}\nbody\n",
        f"prose\n{CLOSE}\n",
        f"{OPEN}\nbody\n{CLOSE}\n{OPEN}\nbody\n{CLOSE}\n",
        f"{CLOSE}\nbody\n{OPEN}\n",
    ],
)
def test_write_refuses_corrupted_markers_and_leaves_the_file_alone(
    tmp_path: Path, text: str
) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(text)
    result = runner.invoke(app, ["init", "--write", str(target)])
    assert result.exit_code == 2
    assert target.read_text() == text
    assert "marker" in result.stderr


def test_check_corrupted_markers_exits_2(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(f"{OPEN}\nbody\n")
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 2
    assert "fix it by hand" in result.stderr


def test_check_is_quiet_and_exits_0_when_current(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    install_primer(target, sxr.__version__)
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert "up to date" in result.stderr


def test_check_exits_1_when_the_block_is_missing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("prose only\n")
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 1
    assert "no sxr primer block" in result.stderr
    assert "sxr init --write" in result.stderr


def test_check_exits_1_when_the_file_is_absent(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--check", str(tmp_path / "AGENTS.md")])
    assert result.exit_code == 1
    assert "does not exist" in result.stderr


def test_check_names_both_versions_on_drift(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(OLD)
    code, note = check_primer(target, "0.3.0")
    assert code == 1
    assert note.startswith("primer v0.0.1 installed in ")
    assert note.endswith("binary is v0.3.0; run sxr init --write")


def test_write_walks_up_to_the_nearest_agents_md(tmp_path: Path, monkeypatch) -> None:
    top = tmp_path / "AGENTS.md"
    top.write_text("top\n")
    mid = tmp_path / "pkg"
    (mid / "src").mkdir(parents=True)
    (mid / "AGENTS.md").write_text("mid\n")
    monkeypatch.chdir(mid / "src")
    assert runner.invoke(app, ["init", "--write"]).exit_code == 0
    assert OPEN in (mid / "AGENTS.md").read_text()
    assert top.read_text() == "top\n"


def test_write_creates_agents_md_in_cwd_when_the_walk_finds_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("sxr.onboard.nearest_agents_md", lambda _start: None)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--write"]).exit_code == 0
    assert (tmp_path / "AGENTS.md").read_text() == primer(sxr.__version__)


def test_check_exits_1_when_no_agents_md_is_above_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sxr.onboard.nearest_agents_md", lambda _start: None)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--check"])
    assert result.exit_code == 1
    assert "no AGENTS.md found above" in result.stderr


def test_explicit_file_beats_the_walk_up(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "AGENTS.md").write_text("untouched\n")
    explicit = tmp_path / "CLAUDE.md"
    explicit.write_text("target\n")
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--write", str(explicit)]).exit_code == 0
    assert OPEN in explicit.read_text()
    assert (tmp_path / "AGENTS.md").read_text() == "untouched\n"


def test_nearest_agents_md_stops_at_the_first_hit(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (tmp_path / "a" / "AGENTS.md").write_text("")
    assert nearest_agents_md(deep) == (tmp_path / "a" / "AGENTS.md").resolve()


def test_global_target_prefers_agents_then_claude_then_home(tmp_path: Path) -> None:
    assert user_agents_file(tmp_path) == tmp_path / "AGENTS.md"
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("")
    assert user_agents_file(tmp_path) == tmp_path / ".claude" / "CLAUDE.md"
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "AGENTS.md").write_text("")
    assert user_agents_file(tmp_path) == tmp_path / ".agents" / "AGENTS.md"


def test_global_writes_the_user_file_not_the_project_one(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    (home / ".agents").mkdir(parents=True)
    (home / ".agents" / "AGENTS.md").write_text("user rules\n")
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("project rules\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.chdir(project)
    assert runner.invoke(app, ["init", "--write", "--global"]).exit_code == 0
    assert OPEN in (home / ".agents" / "AGENTS.md").read_text()
    assert (project / "AGENTS.md").read_text() == "project rules\n"


def test_write_and_check_are_mutually_exclusive(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    result = runner.invoke(app, ["init", "--write", "--check", str(target)])
    assert result.exit_code == 2
    assert not target.exists()


def test_global_and_an_explicit_file_are_mutually_exclusive(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--write", "--global", str(tmp_path / "AGENTS.md")])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stderr


def test_a_file_argument_alone_refuses_to_guess(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 2
    assert not target.exists()


def test_find_block_reports_span_and_version() -> None:
    text = f"a\n{OLD}b\n"
    span = find_block(text)
    assert span is not None
    start, end, version = span
    assert text[start:end] == OLD
    assert version == "0.0.1"


def test_find_block_raises_on_a_lone_opening_marker() -> None:
    with pytest.raises(MarkerError):
        find_block(f"{OPEN}\nbody\n")
