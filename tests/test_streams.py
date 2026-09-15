"""Results on stdout, omissions and notices on stderr (SXR-CLI-24).

The point of every test here is which stream a line arrived on, so each one reads
stdout and stderr separately and asserts about both: that a cap reported itself
somewhere, and that the report did not land in machine-readable output.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.providers import claude_code

runner = CliRunner()
LONG = " ".join(f"w{i:03d}aaaa" for i in range(60))


def _session(project, tag: str, index: int) -> None:
    """One session with two prompts, two tool calls and a two-block line."""
    stamp = f"2026-09-0{index + 1}T08:%02d:00Z"
    records = [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": stamp % 0,
            "message": {"role": "user", "content": f"cadence one {index}"},
        },
        {
            "type": "assistant",
            "timestamp": stamp % 1,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"{tag}a",
                        "name": "Bash",
                        "input": {"command": f"git status {index}"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": stamp % 2,
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": f"{tag}a", "content": "clean"}],
            },
        },
        # Two tool calls on one physical line: one record under a --json cap.
        {
            "type": "assistant",
            "timestamp": stamp % 3,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"{tag}b",
                        "name": "Read",
                        "input": {"file_path": f"/w/one{index}.txt"},
                    },
                    {
                        "type": "tool_use",
                        "id": f"{tag}c",
                        "name": "Read",
                        "input": {"file_path": f"/w/two{index}.txt"},
                    },
                ],
            },
        },
        {
            "type": "assistant",
            "timestamp": stamp % 4,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": f"cadence {LONG}"}],
            },
        },
    ]
    path = project / f"{tag * 4}0024-0000-4000-8000-00000000000{index}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


@pytest.fixture
def four(tmp_path, monkeypatch):
    """Four Claude sessions in one project, so -n 1 omits three."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "cache"))
    project = tmp_path / ".claude" / "projects" / claude_code.flatten_cwd("/w")
    project.mkdir(parents=True)
    for index, tag in enumerate("abcd"):
        _session(project, tag, index)
    return project


def _run(args):
    """Invoke sxr in the /w scope, returning the result with streams apart."""
    return runner.invoke(app, [*args, "--path", "/w"])


def _lines(text):
    return [line for line in text.splitlines() if line]


def test_json_stdout_stays_parseable_when_a_cap_reports_itself(four) -> None:
    result = _run(["list", "-n", "1", "--json"])
    assert result.exit_code == 0
    # 2>/dev/null must leave valid JSON only: this is the whole contract.
    assert [json.loads(line) for line in _lines(result.stdout)]
    assert len(_lines(result.stdout)) == 1
    assert "# +3 more sessions" in result.stderr
    assert "#" not in result.stdout


def test_list_json_said_nothing_about_three_dropped_sessions(four) -> None:
    capped = _run(["list", "-n", "1", "--json"])
    every = _run(["list", "-n", "0", "--json"])
    assert len(_lines(every.stdout)) == 4
    assert len(_lines(capped.stdout)) == 1
    # The count is the fact that used to be missing, not just any notice.
    assert "shown 1 of 4" in capped.stderr


def test_an_uncapped_list_reports_no_omission(four) -> None:
    for args in (["list", "--json"], ["list", "-n", "0", "--json"]):
        result = _run(args)
        assert len(_lines(result.stdout)) == 4
        assert "more sessions" not in result.stderr


def test_the_text_footer_stays_where_scripts_read_it(four) -> None:
    result = _run(["list", "-n", "1"])
    # Human mode is unchanged by this slice: the footer is still on stdout.
    assert "+3 more" in result.stdout
    assert "more" not in result.stderr


def test_cmds_json_reports_the_records_it_held_back(four) -> None:
    result = _run(["cmds", "-n", "1", "--json"])
    assert result.exit_code == 0
    assert len(_lines(result.stdout)) == 1
    assert [json.loads(line) for line in _lines(result.stdout)]
    assert "more records" in result.stderr
    assert "shown 1 of" in result.stderr


def test_one_line_of_two_tool_calls_counts_as_one_record(four) -> None:
    result = _run(["cmds", "@1", "-n", "2", "--json"])
    records = [json.loads(line) for line in _lines(result.stdout)]
    assert len(records) == 2
    # The second selected record is the line holding two calls, printed once.
    assert sum(1 for r in records if len(r["message"]["content"]) == 2) == 1
    assert "more records" not in result.stderr


def test_an_unsearched_scope_is_disclosed_in_both_modes(four) -> None:
    text = _run(["cmds", "--grep", "git"])
    assert "of 4 sessions searched" in text.stdout
    structured = _run(["cmds", "--grep", "git", "--json"])
    # An agent told nothing here believes it searched every session in scope.
    assert "of 4 sessions searched" in structured.stderr
    assert "--all-sessions" in structured.stderr
    assert [json.loads(line) for line in _lines(structured.stdout)]


def test_coverage_says_when_the_named_path_is_not_here(four) -> None:
    missing = runner.invoke(app, ["list", "--coverage", "--path", "/w/nowhere"])
    assert "path not present on this machine" in missing.stderr
    present = _run(["list", "--coverage"])
    # A real directory with sessions must not be labelled: the note explains an
    # empty result, and saying it otherwise would be false.
    assert "path not present" not in present.stderr


def test_a_real_but_empty_scope_is_not_called_missing(four, tmp_path) -> None:
    empty = tmp_path / "empty-dir"
    empty.mkdir()
    result = runner.invoke(app, ["list", "--coverage", "--path", str(empty)])
    assert "0 sessions" in result.stderr
    assert "path not present" not in result.stderr


def test_raw_records_are_unchanged_by_the_new_notices(four) -> None:
    """D-09: --json stdout stays the original provider records, whole."""
    result = _run(["cmds", "-n", "1", "--json"])
    record = json.loads(_lines(result.stdout)[0])
    assert record["type"] == "assistant"
    assert record["message"]["content"][0]["name"] == "Bash"
    assert "shown" not in record and "omitted" not in record


def test_the_grep_session_projection_is_untouched(four) -> None:
    """D-12: -l --json keeps its documented shape, and no count appears in it."""
    result = _run(["grep", "cadence", "-l", "--json"])
    records = [json.loads(line) for line in _lines(result.stdout)]
    assert records and all(r["type"] == "grep_session" for r in records)
    assert all("matches" not in r for r in records)


def test_exit_codes_and_negative_limits_are_unchanged(four) -> None:
    assert _run(["list", "--json"]).exit_code == 0
    assert _run(["grep", "quernstone", "--json"]).exit_code == 1
    assert _run(["list", "-n", "-1"]).exit_code == 2
    empty = _run(["cmds", "--grep", "quernstone", "--json"])
    assert empty.exit_code == 1
    assert not _lines(empty.stdout)
