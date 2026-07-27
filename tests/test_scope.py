"""Time scoping: the (live) label and the --since/--before session window."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sxr import util
from sxr.cli import app
from sxr.handles import window
from sxr.model import Event, SessionRef
from sxr.util import is_live
from sxr.views_grep import GrepOpts, grep_view
from sxr.views_info import list_view

runner = CliRunner()

NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
FRESH = "2026-07-27T11:55:00.000Z"  # 5 min old: inside the 10 min window
STALE = "2026-07-27T09:00:00.000Z"  # 3 h old: outside it


@pytest.fixture
def frozen(monkeypatch) -> datetime:
    """Freeze the clock the live label reads, so the label is deterministic."""
    monkeypatch.setattr(util, "now_utc", lambda: NOW)
    return NOW


def _ref(short: str, started: str, ended: str = "", title: str = "t") -> SessionRef:
    return SessionRef(
        "claude",
        f"{short}-2222",
        Path(f"{short}.jsonl"),
        started=started,
        ended=ended,
        title=title,
    )


def _events(*texts: str) -> list[Event]:
    return [Event(i, "", "asst", "text", text) for i, text in enumerate(texts, start=1)]


# --- the (live) label ---------------------------------------------------


def test_is_live_only_inside_the_window(frozen) -> None:
    assert is_live(FRESH)
    assert not is_live(STALE)
    assert not is_live("")  # a session with no timestamps is never live
    assert not is_live("whenever")
    assert is_live("2026-07-27T11:55:00")  # no zone: read as UTC, like the records
    assert is_live("2026-07-27T21:57:00+10:00")  # 11:57Z, offsets respected


def test_window_edges_are_ten_minutes(frozen) -> None:
    assert is_live("2026-07-27T11:50:01.000Z")
    assert not is_live("2026-07-27T11:49:59.000Z")
    assert is_live("2026-07-27T12:05:00.000Z")  # clock skew ahead still counts


def test_list_view_marks_live_rows_and_names_the_fix(frozen, capsys) -> None:
    refs = [_ref("live0000", FRESH, FRESH, "running now"), _ref("old00000", STALE, STALE, "done")]
    assert list_view(refs, False, None, "/w") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[2].endswith("\t(live) running now")
    assert lines[3].endswith("\tdone")
    assert "# (live) = written in the last 10 min, your own session included" in "\n".join(lines)
    assert "scope it out with --before today" in "\n".join(lines)


def test_list_view_says_nothing_when_no_row_is_live(frozen, capsys) -> None:
    assert list_view([_ref("old00000", STALE, STALE)], False, None, "/w") == 0
    assert "(live)" not in capsys.readouterr().out


def test_list_json_carries_a_live_boolean(frozen, capsys) -> None:
    refs = [_ref("live0000", FRESH, FRESH), _ref("old00000", STALE, STALE)]
    assert list_view(refs, True, None, "/w") == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["live"] for row in rows] == [True, False]


def test_count_table_marks_the_live_row(frozen, capsys) -> None:
    live = _ref("live0000", FRESH, FRESH, "running now")
    old = _ref("old00000", STALE, STALE, "done")
    parse = {live.path: _events("needle", "needle"), old.path: _events("needle")}.__getitem__
    assert grep_view("needle", [live, old], parse, GrepOpts(count=True)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "live0000\t2\t1\t2026-07-27\t(live) running now"
    assert lines[2] == "old00000\t1\t1\t2026-07-27\tdone"
    assert "# (live) = written in the last 10 min" in "\n".join(lines)


def test_count_json_keeps_the_title_clean(frozen, capsys) -> None:
    live = _ref("live0000", FRESH, FRESH, "running now")
    parse = {live.path: _events("needle")}.__getitem__
    assert grep_view("needle", [live], parse, GrepOpts(count=True, json_out=True)) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["live"] is True
    assert row["title"] == "running now"  # the marker is a display cell, not data


# --- --since / --before -------------------------------------------------


def _scope() -> list[SessionRef]:
    return [
        _ref("newest00", "2026-07-27T09:30:00.000Z"),
        _ref("middle00", "2026-07-26T14:30:00.000Z"),
        _ref("oldest00", "2026-07-20T08:00:00.000Z"),
    ]


def _ids(refs: list[SessionRef]) -> list[str]:
    return [ref.short_id for ref in refs]


def test_no_bounds_returns_the_scope_untouched() -> None:
    refs = _scope()
    assert window(refs) is refs


def test_since_includes_the_whole_named_day() -> None:
    assert _ids(window(_scope(), since="2026-07-26")) == ["newest00", "middle00"]
    assert _ids(window(_scope(), since="2026-07-27")) == ["newest00"]


def test_before_excludes_the_whole_named_day() -> None:
    # midnight bound: --before today drops today's sessions, the caller's own
    assert _ids(window(_scope(), before="2026-07-27")) == ["middle00", "oldest00"]
    assert _ids(window(_scope(), before="2026-07-26")) == ["oldest00"]


def test_both_bounds_are_a_half_open_interval() -> None:
    kept = window(_scope(), since="2026-07-26", before="2026-07-27")
    assert _ids(kept) == ["middle00"]


def test_iso_datetimes_cut_inside_a_day() -> None:
    assert _ids(window(_scope(), since="2026-07-26T14:30:00")) == ["newest00", "middle00"]
    assert _ids(window(_scope(), since="2026-07-26T14:30:01")) == ["newest00"]
    assert _ids(window(_scope(), before="2026-07-26T14:30:00Z")) == ["oldest00"]
    assert _ids(window(_scope(), since="2026-07-27T00:00:00+10:00")) == ["newest00", "middle00"]


def test_today_reads_the_frozen_clock(frozen) -> None:
    assert _ids(window(_scope(), before="today")) == ["middle00", "oldest00"]
    assert _ids(window(_scope(), since="today")) == ["newest00"]


def test_a_handle_bounds_by_that_sessions_start() -> None:
    assert _ids(window(_scope(), before="@2")) == ["oldest00"]
    assert _ids(window(_scope(), since="@2")) == ["newest00", "middle00"]


def test_a_bad_handle_still_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        window(_scope(), before="@9")
    assert exc.value.code == 2
    assert "@9 out of range" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["yesterday", "07/26/2026", "20260726", "2026-13-45", "last week"])
def test_bad_dates_exit_2_with_the_accepted_forms(bad: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        window(_scope(), since=bad)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert f"bad --since value '{bad}'" in err
    assert "YYYY-MM-DD, today, an ISO datetime (2026-07-26T14:30:00Z), or @N" in err


def test_an_empty_window_says_what_it_dropped(capsys) -> None:
    assert window(_scope(), since="2026-07-28") == []
    assert "# --since 2026-07-28 kept none of 3 sessions in scope" in capsys.readouterr().err


def test_an_empty_scope_stays_quiet(capsys) -> None:
    assert window([], since="2026-07-28") == []
    assert capsys.readouterr().err == ""


# --- CLI wiring ---------------------------------------------------------


def _record(ts: str, text: str) -> dict:
    return {
        "type": "user",
        "timestamp": ts,
        "cwd": "/w",
        "message": {"role": "user", "content": text},
    }


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch) -> Path:
    """Three sessions for /w: two on 2026-07-26, one being written 'now'."""
    from sxr.providers import claude_code

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    project = tmp_path / ".claude" / "projects" / claude_code.flatten_cwd("/w")
    project.mkdir(parents=True)
    days = {
        "aaaa1111-2222": ["2026-07-20T08:00:00.000Z", "2026-07-20T08:05:00.000Z"],
        "bbbb1111-2222": ["2026-07-26T14:00:00.000Z", "2026-07-26T14:30:00.000Z"],
        "cccc1111-2222": ["2026-07-27T11:50:00.000Z", FRESH],
    }
    for sid, stamps in days.items():
        records = [_record(ts, "needle in the transcript") for ts in stamps]
        (project / f"{sid}.jsonl").write_text("\n".join(json.dumps(r) for r in records))
    return project


def test_bare_list_labels_the_live_session(corpus, frozen) -> None:
    result = runner.invoke(app, ["--path", "/w"])
    assert result.exit_code == 0
    assert "(live)" in result.output
    assert result.output.count("(live)") == 2  # one row, one footer


def test_before_today_scopes_the_live_session_out(corpus, frozen) -> None:
    result = runner.invoke(app, ["grep", "-c", "needle", "--path", "/w", "--before", "today"])
    assert result.exit_code == 0
    assert "cccc1111" not in result.output
    assert "(live)" not in result.output
    assert "# 2 of 2 sessions match" in result.output


def test_since_narrows_grep_and_renumbers_handles(corpus, frozen) -> None:
    result = runner.invoke(app, ["--path", "/w", "--since", "2026-07-26", "list"])
    assert result.exit_code == 0
    assert "aaaa1111" not in result.output
    # @N numbers the narrowed scope, so a windowed handle means what it shows
    assert "@1\tcccc1111" in result.output and "@2\tbbbb1111" in result.output


def test_cmds_grep_honors_the_window(corpus) -> None:
    result = runner.invoke(app, ["cmds", "--grep", "x", "--path", "/w", "--since", "2026-07-28"])
    assert result.exit_code == 1
    assert "kept none of 3 sessions in scope" in result.output


def test_bad_since_exits_2_through_the_cli(corpus) -> None:
    result = runner.invoke(app, ["grep", "needle", "--path", "/w", "--since", "yesterday"])
    assert result.exit_code == 2
    assert "bad --since value 'yesterday'" in result.output
    assert "YYYY-MM-DD, today" in result.output


def test_grep_help_documents_the_window_flags() -> None:
    result = runner.invoke(app, ["grep", "--help"])
    assert result.exit_code == 0
    assert "--since" in result.output and "--before" in result.output
    assert "--before-context" not in result.output  # the hidden -B alias stays hidden
