"""CLI wiring: grep aliases, hidden teaching flags, and usage exits."""

from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()


def test_after_before_teach_symmetric_context() -> None:
    for flag in ("-A", "-B"):
        result = runner.invoke(app, ["grep", "needle", flag, "3"])
        assert result.exit_code == 2
        assert "no -A/-B; context is symmetric: -C 3 prints 3 events each side." in result.output


def test_missing_pattern_exits_2() -> None:
    result = runner.invoke(app, ["grep"])
    assert result.exit_code == 2
    assert "missing pattern" in result.output


def test_bad_regex_exits_2_not_1() -> None:
    result = runner.invoke(app, ["grep", "foo("])
    assert result.exit_code == 2
    assert "bad regex 'foo('" in result.output


def test_grep_help_documents_the_new_flags() -> None:
    result = runner.invoke(app, ["grep", "--help"])
    assert result.exit_code == 0
    for expected in ("--ignore-case", "-i", "--files-with-matches", "-l", "--regexp", "--sort"):
        assert expected in result.output
    assert "-A" not in result.output  # teaching-only, never advertised


def test_sort_value_is_checked() -> None:
    result = runner.invoke(app, ["grep", "needle", "-c", "--sort", "density"])
    assert result.exit_code == 2
    assert "--sort takes matches or started" in result.output
