"""Grep behavior: caps, exit codes, the -c table, footers, aliases, errors."""

from pathlib import Path

import pytest

from sxr.model import Event, SessionRef
from sxr.views_grep import GrepOpts, compile_pattern, grep_view, pick_pattern, scope


def _ref(
    short: str = "aaaa1111", started: str = "2026-07-20T10:00:00Z", title: str = ""
) -> SessionRef:
    return SessionRef(
        "claude", f"{short}-2222", Path(f"{short}.jsonl"), started=started, title=title
    )


def _events(*texts: str) -> list[Event]:
    return [Event(i, "", "asst", "text", text) for i, text in enumerate(texts, start=1)]


def _parse(mapping: dict[Path, list[Event]]):
    return lambda path: mapping[path]


def test_limit_caps_match_rows_and_reports_the_total(capsys) -> None:
    ref = _ref()
    events = _events(*[f"needle {i}" for i in range(20)])
    assert grep_view("needle", [ref], _parse({ref.path: events}), GrepOpts(limit=3)) == 0
    out = capsys.readouterr().out
    assert out.count("needle") == 3
    assert "# 20 matches, showing first 3" in out
    assert "-n 0 for all" in out


def test_limit_zero_prints_everything(capsys) -> None:
    ref = _ref()
    events = _events(*[f"needle {i}" for i in range(20)])
    assert grep_view("needle", [ref], _parse({ref.path: events}), GrepOpts(limit=0)) == 0
    out = capsys.readouterr().out
    assert out.count("needle") == 20
    assert "showing first" not in out


def test_char_budget_caps_rows_without_a_limit(capsys) -> None:
    ref = _ref()
    events = _events(*["needle " + "x" * 400 for _ in range(10)])
    opts = GrepOpts(budget=1000)
    assert grep_view("needle", [ref], _parse({ref.path: events}), opts) == 0
    out = capsys.readouterr().out
    assert 0 < out.count("needle") < 10
    assert "# 10 matches, showing first" in out


def test_budget_zero_never_caps(capsys) -> None:
    ref = _ref()
    events = _events(*["needle " + "x" * 400 for _ in range(10)])
    assert grep_view("needle", [ref], _parse({ref.path: events}), GrepOpts(budget=0)) == 0
    assert "showing first" not in capsys.readouterr().out


def test_bad_regex_exits_2_with_the_literal_fix(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        compile_pattern("foo(")
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "bad regex 'foo('" in err
    assert "unterminated subpattern" in err
    assert "-F 'foo('" in err


def test_count_table_ranks_prunes_and_names_the_zoom(capsys) -> None:
    hot = _ref("hot00000", "2026-07-20T10:00:00Z", "hot session")
    old = _ref("old00000", "2026-06-01T10:00:00Z", "old session")
    cold = _ref("cold0000", "2026-07-25T10:00:00Z", "cold session")
    events = {
        hot.path: _events("nope", "needle", "needle", "needle"),
        old.path: _events("needle", "nope"),
        cold.path: _events("nothing here"),
    }
    assert grep_view("needle", [hot, old, cold], _parse(events), GrepOpts(count=True)) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "# session\tmatches\tfirst\tstarted\ttitle"
    assert lines[1] == "hot00000\t3\t2\t2026-07-20\thot session"
    assert lines[2] == "old00000\t1\t1\t2026-06-01\told session"
    assert "cold0000" not in out
    assert "# 2 of 3 sessions match; zoom: sxr show hot00000 --around 2" in out
    assert "--sort started" in out


def test_count_sort_started_puts_the_oldest_first(capsys) -> None:
    hot = _ref("hot00000", "2026-07-20T10:00:00Z", "hot session")
    old = _ref("old00000", "2026-06-01T10:00:00Z", "old session")
    events = {
        hot.path: _events("needle", "needle"),
        old.path: _events("needle"),
    }
    opts = GrepOpts(count=True, sort="started")
    assert grep_view("needle", [hot, old], _parse(events), opts) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith("old00000")
    assert "zoom: sxr show old00000 --around 1" in lines[3]


def test_count_all_restores_zero_rows(capsys) -> None:
    hit = _ref("hit00000")
    zero = _ref("zero0000")
    events = {hit.path: _events("needle"), zero.path: _events("nope")}
    opts = GrepOpts(count=True, include_all=True)
    assert grep_view("needle", [hit, zero], _parse(events), opts) == 0
    out = capsys.readouterr().out
    assert "zero0000\t0\t\t" in out


def test_count_limit_caps_rows(capsys) -> None:
    refs = [_ref(f"sess{i:04d}") for i in range(5)]
    events = {ref.path: _events("needle") for ref in refs}
    opts = GrepOpts(count=True, limit=2)
    assert grep_view("needle", refs, _parse(events), opts) == 0
    out = capsys.readouterr().out
    assert out.count("needle") == 0
    assert len([line for line in out.splitlines() if line.startswith("sess")]) == 2
    assert "# +3 matching sessions hidden (raise -n)" in out


def test_zero_matches_exits_1_with_broaden_hint(capsys) -> None:
    refs = [_ref(f"sess{i:04d}") for i in range(3)]
    events = {ref.path: _events("nope") for ref in refs}
    for opts in (GrepOpts(count=True), GrepOpts()):
        assert grep_view("needle", refs, _parse(events), opts) == 1
        err = capsys.readouterr().err
        assert "no matches for 'needle' in 3 sessions" in err
        assert "# smart-case regex; -F for literal; --codex / --path <dir> widen scope" in err


def test_capitals_warning_names_the_flag(capsys) -> None:
    ref = _ref()
    events = _events("Needle here")
    assert grep_view("Needle", [ref], _parse({ref.path: events}), GrepOpts()) == 0
    assert "# pattern has capitals" in capsys.readouterr().out


def test_ignore_case_matches_any_case_and_drops_the_warning(capsys) -> None:
    ref = _ref()
    events = _events("NEEDLE here")
    opts = GrepOpts(ignore_case=True)
    assert grep_view("Needle", [ref], _parse({ref.path: events}), opts) == 0
    out = capsys.readouterr().out
    assert "NEEDLE here" in out
    assert "pattern has capitals" not in out


def test_metachar_warning_unless_fixed(capsys) -> None:
    ref = _ref()
    events = _events("gui/$(id -u) ran")
    assert grep_view("gui/$(id -u)", [ref], _parse({ref.path: events}), GrepOpts(fixed=True)) == 0
    out = capsys.readouterr().out
    assert "gui/$(id -u) ran" in out
    assert "regex metachars" not in out
    # the same pattern as a regex silently matches nothing: warn, don't shrug
    assert grep_view("gui/$(id -u)", [ref], _parse({ref.path: events}), GrepOpts()) == 1
    assert "# pattern has regex metachars; -F matches it literally" in capsys.readouterr().err


def test_ids_only_prints_one_id_per_matching_session(capsys) -> None:
    hit = _ref("hit00000")
    zero = _ref("zero0000")
    events = {hit.path: _events("needle", "needle"), zero.path: _events("nope")}
    assert grep_view("needle", [hit, zero], _parse(events), GrepOpts(ids_only=True)) == 0
    assert capsys.readouterr().out == "hit00000\n"


def test_bad_sort_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        grep_view("needle", [_ref()], _parse({}), GrepOpts(sort="density"))
    assert exc.value.code == 2
    assert "--sort takes matches or started" in capsys.readouterr().err


def test_pick_pattern_shifts_a_positional_when_e_is_used() -> None:
    assert pick_pattern("needle", None, None) == ("needle", None)
    assert pick_pattern("needle", "@2", None) == ("needle", "@2")
    assert pick_pattern(None, None, "-needle") == ("-needle", None)
    assert pick_pattern("@2", None, "needle") == ("needle", "@2")


def test_missing_pattern_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        pick_pattern(None, None, None)
    assert exc.value.code == 2
    assert "missing pattern" in capsys.readouterr().err


def test_second_positional_that_is_no_session_teaches_the_regex(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        scope("hostname", "OVH", [_ref()])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "'hostname' is not a session (@N, id prefix, or name)" in err
    assert 'try "OVH.*hostname" or "OVH|hostname"' in err


def test_context_windows_stay_under_the_row_cap(capsys) -> None:
    ref = _ref()
    events = _events("before", "needle one", "after", "needle two", "tail")
    opts = GrepOpts(context=1, limit=1)
    assert grep_view("needle", [ref], _parse({ref.path: events}), opts) == 0
    out = capsys.readouterr().out
    assert "> aaaa1111 #0002" in out
    assert "needle two" not in out
    assert "# 2 matches, showing first 1" in out
