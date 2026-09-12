"""show composes its selectors in one order instead of letting one win silently.

Window (--around xor --range), then kind (--type, else the skeleton, else every
kind), then --errors, then --tail, then -n. Combinations that used to discard a
requested window or filter now intersect, and windows that cannot mean anything
are usage errors rather than a quiet empty success.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()
LONG = "a long assistant answer that repeats itself. " * 1200 + "unique ending"


def _claude(root):
    """One Claude transcript holding every kind the pipeline distinguishes."""
    stamp = "2026-08-01T08:00:0"

    def asst(second, block):
        return {
            "type": "assistant",
            "cwd": "/w",
            "timestamp": f"{stamp}{second}Z",
            "message": {"role": "assistant", "content": [block]},
        }

    def result(second, call, content, failed=False):
        block = {"type": "tool_result", "tool_use_id": call, "content": content}
        if failed:
            block["is_error"] = True
        return {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}{second}Z",
            "message": {"role": "user", "content": [block]},
        }

    records = [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": f"{stamp}0Z",
            "message": {"role": "user", "content": "human ask one"},
        },
        asst(1, {"type": "thinking", "thinking": "weighing options"}),
        asst(2, {"type": "text", "text": "short answer"}),
        asst(3, {"type": "tool_use", "name": "Bash", "id": "ok-1", "input": {"command": "true"}}),
        result(4, "ok-1", "fine"),
        asst(5, {"type": "tool_use", "name": "Bash", "id": "bad-1", "input": {"command": "false"}}),
        result(6, "bad-1", "exploded on purpose", failed=True),
        {"type": "system", "cwd": "/w", "timestamp": f"{stamp}7Z", "content": "a meta record"},
        asst(8, {"type": "text", "text": LONG}),
    ]
    path = root / "cccc1111-2222-3333-4444-555566667777.jsonl"
    path.write_text("\n".join(map(json.dumps, records)))
    return path


def _codex(root):
    """One Codex rollout with the same kind coverage, through the other parser."""
    stamp = "2026-08-01T08:00:0"

    def item(second, payload):
        return {"type": "response_item", "timestamp": f"{stamp}{second}Z", "payload": payload}

    def shell(second, call, command):
        return item(
            second,
            {
                "type": "function_call",
                "call_id": call,
                "name": "shell",
                "arguments": json.dumps({"command": ["bash", "-lc", command]}),
            },
        )

    def output(second, call, text, code):
        return item(
            second,
            {
                "type": "function_call_output",
                "call_id": call,
                "output": json.dumps({"output": text, "metadata": {"exit_code": code}}),
            },
        )

    def message(second, role, text, kinds=None):
        payload = {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": text}],
        }
        if kinds is not None:
            payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
        return item(second, payload)

    records = [
        {
            "type": "session_meta",
            "timestamp": f"{stamp}0Z",
            "payload": {"id": "019f9520-5499-7000-8000-00000000cccc", "cwd": "/w"},
        },
        message(0, "user", "human ask one", ["user.text"]),
        item(1, {"type": "reasoning", "summary": [{"type": "summary_text", "text": "weighing"}]}),
        message(2, "assistant", "short answer"),
        shell(3, "ok-1", "true"),
        output(4, "ok-1", "fine", 0),
        shell(5, "bad-1", "false"),
        output(6, "bad-1", "exploded on purpose", 1),
        {"type": "turn_context", "timestamp": f"{stamp}7Z", "payload": {"cwd": "/w"}},
        message(8, "assistant", LONG),
    ]
    day = root / "sessions" / "2026" / "08" / "01"
    day.mkdir(parents=True)
    path = day / "rollout-2026-08-01T08-00-00-019f9520.jsonl"
    path.write_text("\n".join(map(json.dumps, records)))
    return path


@pytest.fixture(params=["claude", "codex"])
def session(request, tmp_path, monkeypatch):
    """One session of one provider under a temporary root, plus its CLI flag."""
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "cache"))
    if request.param == "claude":
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
        root = tmp_path / ".claude" / "projects" / "-w"
        root.mkdir(parents=True)
        _claude(root)
        return ["--claude"]
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    _codex(tmp_path / ".codex")
    return ["--codex"]


def _run(session, *args):
    return runner.invoke(app, ["show", *session, "--path", "/w", *args])


def _rows(stdout):
    return [line for line in stdout.splitlines() if line.startswith("#0")]


def _seqs(stdout):
    """The physical record numbers a view printed, in order."""
    return [int(row[1:5]) for row in _rows(stdout)]


def _errors_only(rows):
    return rows and all("is_error" in row or "-> err" in row for row in rows)


def test_full_and_errors_keeps_only_error_records_untrimmed(session):
    """--full used to disable the error filter; now it only lifts kind and trim."""
    result = _run(session, "--full", "--errors")
    assert result.exit_code == 0
    rows = _rows(result.stdout)
    assert _errors_only(rows), rows
    assert "exploded on purpose" in result.stdout
    assert "chars]" not in result.stdout and "unique ending" not in result.stdout


def test_errors_alone_still_reaches_every_kind(session):
    """--errors names error results, which the default skeleton would have hidden."""
    rows = _rows(_run(session, "--errors").stdout)
    assert _errors_only(rows), rows
    assert any("result" in row for row in rows), rows


def test_type_intersects_a_window_instead_of_replacing_it(session):
    """--type used to discard --around outright."""
    every = _seqs(_run(session, "--type", "tool").stdout)
    assert len(every) == 2, every
    inside = _run(session, "--type", "tool", "--around", str(every[-1]), "--context", "0")
    assert inside.exit_code == 0
    assert _seqs(inside.stdout) == every[-1:]
    assert "false" in inside.stdout and "true" not in inside.stdout


def test_type_intersects_a_range(session):
    """--range narrows --type the same way --around does."""
    every = _seqs(_run(session, "--type", "result").stdout)
    assert len(every) == 2, every
    result = _run(session, "--type", "result", "--range", f"1:{every[0]}")
    assert _seqs(result.stdout) == every[:1]
    assert "fine" in result.stdout and "exploded" not in result.stdout


def test_errors_narrows_a_window(session):
    """A window used to discard --errors."""
    result = _run(session, "--around", "7", "--context", "3", "--errors")
    assert result.exit_code == 0
    assert _errors_only(_rows(result.stdout)), result.stdout


def test_a_window_without_errors_stays_empty_rather_than_widening(session):
    """Intersecting is real: a window holding no error exits 1, it does not fall back."""
    result = _run(session, "--range", "1:5", "--errors")
    assert result.exit_code == 1
    assert _rows(result.stdout) == []
    assert "--range 1:5 and --errors" in result.stderr


def test_full_still_narrows_to_an_explicit_kind(session):
    """--full means every kind, and --type is still allowed to pick one of them."""
    rows = _rows(_run(session, "--full", "--type", "thinking").stdout)
    assert len(rows) == 1 and "think" in rows[0], rows


def test_tail_applies_after_the_other_stages(session):
    """--tail keeps the last of what survived, not the last of the transcript."""
    every = _rows(_run(session, "--errors").stdout)
    tailed = _rows(_run(session, "--errors", "--tail", "1").stdout)
    assert len(every) > 1 and tailed == every[-1:]


def test_a_window_shows_every_kind_it_contains(session):
    """A zoom is for reading; it must not apply the skeleton's kind filter."""
    rows = _rows(_run(session, "--around", "5", "--context", "1").stdout)
    assert any("result" in row for row in rows), rows


def test_skeleton_still_hides_thinking_and_results_by_default(session):
    """The default reading view is unchanged, and says which flag reveals each kind."""
    result = _run(session)
    assert result.exit_code == 0
    rows = _rows(result.stdout)
    assert not any("think" in row or "result " in row for row in rows), rows
    assert "(--thinking)" in result.stdout and "(--tool-results)" in result.stdout


@pytest.mark.parametrize("flag", ["--tools", "--tool-results"])
def test_both_result_spellings_select_the_same_records(session, flag):
    """--tools keeps working; --tool-results is the name that says what it does."""
    rows = _rows(_run(session, flag).stdout)
    assert any("result" in row for row in rows), rows
    assert rows == _rows(_run(session, "--tool-results").stdout)


@pytest.mark.parametrize(
    "selection",
    [
        ["--around", "0"],
        ["--around", "-3"],
        ["--around", "5", "--context", "-1"],
        ["--context", "3"],
        ["--range", "6:3"],
        ["--range", "0:4"],
        ["--range", "4:0"],
        ["--range", "junk"],
        ["--around", "5", "--range", "1:3"],
        ["--budget", "-1"],
        ["--line-limit", "-5"],
        ["--tail", "-1"],
    ],
)
def test_meaningless_selections_are_usage_errors(session, selection):
    """Each of these used to succeed quietly, or silently pick a winner."""
    result = _run(session, *selection)
    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    assert _rows(result.stdout) == []


def test_conflicting_windows_name_both_flags(session):
    """The error has to say which two flags conflict, not just that one failed."""
    result = _run(session, "--around", "5", "--range", "1:3")
    assert "--around" in result.stderr and "--range" in result.stderr


def test_context_is_rejected_before_discovery(session, monkeypatch):
    """Usage errors must not depend on finding any session first."""

    def refuse(*args, **kwargs):
        raise AssertionError("discovery ran before the flags were validated")

    monkeypatch.setattr("sxr.flags.sessions", refuse)
    assert _run(session, "--context", "3").exit_code == 2


def test_range_still_accepts_the_grep_habit(session):
    """A-B keeps meaning A:B."""
    assert _rows(_run(session, "--range", "3-6").stdout) == _rows(
        _run(session, "--range", "3:6").stdout
    )


def test_tail_zero_selects_nothing_and_exits_one(session):
    """SXR-AUD-011: --tail 0 is a valid request for no records."""
    result = _run(session, "--tail", "0")
    assert result.exit_code == 1
    assert _rows(result.stdout) == []
    assert "--tail 0" in result.stderr


def test_an_empty_selection_says_which_selectors_emptied_it(session):
    """An unknown kind is the easy mistake; the notice has to be actionable."""
    result = _run(session, "--type", "nosuchkind")
    assert result.exit_code == 1
    assert "--type nosuchkind" in result.stderr and "sxr stats" in result.stderr


def test_empty_notices_never_reach_json_stdout(session):
    """--json stdout is a record contract: it stays empty or stays parseable."""
    result = _run(session, "--type", "nosuchkind", "--json")
    assert result.exit_code == 1
    assert result.stdout == "" and "nosuchkind" in result.stderr


def test_json_prints_whole_physical_records_once(session):
    """Every --json line is one complete source record, and no record repeats."""
    result = _run(session, "--full", "--errors", "--json")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines and len(lines) == len(set(lines))
    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_json_selection_matches_the_text_selection(session):
    """The pipeline decides; the format only changes how the result is printed."""
    text = _rows(_run(session, "--full", "--errors").stdout)
    raw = [
        line for line in _run(session, "--full", "--errors", "--json").stdout.splitlines() if line
    ]
    assert len(text) == len(raw) > 0


@pytest.mark.parametrize(
    "selection",
    [
        ["--full", "--errors"],
        ["--type", "tool", "--around", "6", "--context", "2"],
        ["--range", "1:8", "--errors"],
        ["--errors", "--tail", "1"],
        ["--type", "result", "--range", "1:5"],
    ],
)
def test_cached_and_uncached_selections_agree(session, monkeypatch, selection):
    """The cache reuses the same pipeline over event metadata, so it must match."""
    warm = _run(session, *selection)
    again = _run(session, *selection)
    monkeypatch.setenv("SXR_NO_CACHE", "1")
    cold = _run(session, *selection)
    assert warm.stdout == again.stdout == cold.stdout
    assert warm.exit_code == again.exit_code == cold.exit_code


def test_row_limit_applies_after_selection(session):
    """-n is the last stage: it caps rows without changing which ones qualified."""
    every = _rows(_run(session, "--full").stdout)
    capped = _run(session, "--full", "-n", "2")
    assert len(every) > 2
    assert _rows(capped.stdout) == every[:2]
    assert f"{len(every) - 2} more events" in capped.stdout


def test_budget_zero_and_line_limit_zero_mean_no_trimming(session):
    """0 stays the explicit "never trim" value now that negatives are rejected."""
    result = _run(session, "--budget", "0")
    assert result.exit_code == 0
    assert "unique ending" in result.stdout and "chars]" not in result.stdout
    assert "chars]" not in _run(session, "--budget", "1", "--line-limit", "0").stdout


def test_help_prints_the_implemented_order(session):
    """The documented precedence is part of the contract, so help must carry it."""
    out = runner.invoke(app, ["show", "--help"]).stdout
    flat = " ".join(out.split())
    assert "window (--around or --range, never both)" in flat
    assert "then --errors, then --tail, then -n" in flat
    assert "--tool-results" in flat and "--tools" in flat
