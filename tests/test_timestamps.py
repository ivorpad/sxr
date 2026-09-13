"""One timestamp parser for sorting, filtering and display (SXR-CLI-08).

Three defects, all from reading recorded timestamps as text instead of moments:

* `day()` returned `ts[:19] + "Z"`, so `2026-09-10T09:00:00+02:00` displayed as
  `09:00:00Z` when the moment it names is `07:00:00Z`. `clock()` sliced the same
  way, and `grep -c`'s date column and `find`'s used `ts[:10]`.
* Session ordering compared the strings, so an offset-bearing session sorted by
  its digits rather than its instant -- which decides `@N`.
* `grep -c --sort started` compared the strings too.

Window filtering (`--since`/`--before`) already compared UTC instants before this
slice, so the tests here assert it did not move: a literal bound keeps exactly the
sessions it kept before. What does move is a bound written `--since @N`, because
`@N` names a different session once the order is right, and that is asserted as
the deliberate consequence it is rather than left to be discovered.

The fixture records the same moment twice in different offsets, and one session
just after local midnight east of Greenwich whose UTC day is the previous one.
"""

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.util import clock, date_of, day, instant, order_key

CWD = "/w"
NEEDLE = "chronology"

# key, claude id, codex id, recorded start, UTC instant it names
CORPUS = [
    (
        "S1",
        "aaaaaaa1-0000-4000-8000-00000000000a",
        "01999991-aaaa-7000-8000-00000000000a",
        "2026-09-10T09:00:00+02:00",
        "2026-09-10T07:00:00Z",
    ),
    (
        "S2",
        "bbbbbbb2-0000-4000-8000-00000000000b",
        "01999992-bbbb-7000-8000-00000000000b",
        "2026-09-10T07:00:00Z",
        "2026-09-10T07:00:00Z",
    ),
    (
        "S3",
        "ccccccc3-0000-4000-8000-00000000000c",
        "01999993-cccc-7000-8000-00000000000c",
        "2026-09-10T08:00:00Z",
        "2026-09-10T08:00:00Z",
    ),
    (
        "S4",
        "ddddddd4-0000-4000-8000-00000000000d",
        "01999994-dddd-7000-8000-00000000000d",
        "2026-09-11T00:30:00+02:00",
        "2026-09-10T22:30:00Z",
    ),
]


def _claude(root, key, ident, start):
    project = root / "projects" / "-w"
    project.mkdir(parents=True, exist_ok=True)
    body = [
        dict(
            type="user", timestamp=start, cwd=CWD, message=dict(role="user", content=f"open {key}")
        ),
        dict(
            type="assistant",
            timestamp=start,
            cwd=CWD,
            message=dict(
                role="assistant",
                content=[dict(type="text", text=f"{NEEDLE} {key}")],
            ),
        ),
    ]
    (project / f"{ident}.jsonl").write_text("\n".join(json.dumps(r) for r in body) + "\n")


def _codex(root, key, ident, start):
    directory = root / "sessions" / start[:4] / start[5:7] / start[8:10]
    directory.mkdir(parents=True, exist_ok=True)

    body = [
        dict(
            timestamp=start, type="session_meta", payload=dict(id=ident, cwd=CWD, timestamp=start)
        ),
        # A Codex human turn is event_msg/user_message, and that record is what
        # supplies the session title; a response_item with role "user" does not.
        dict(
            timestamp=start,
            type="event_msg",
            payload=dict(type="user_message", message=f"open {key}"),
        ),
        dict(
            timestamp=start,
            type="response_item",
            payload=dict(
                type="message",
                role="assistant",
                content=[dict(type="output_text", text=f"{NEEDLE} {key}")],
            ),
        ),
    ]
    name = f"rollout-{start[:10]}T00-00-00-{ident}.jsonl"
    (directory / name).write_text("\n".join(json.dumps(r) for r in body) + "\n")


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """Four sessions on one provider, whose string and instant orders differ."""
    root = tmp_path / request.param
    for key, claude_id, codex_id, start, _utc in CORPUS:
        if request.param == "claude":
            _claude(root, key, claude_id, start)
        else:
            _codex(root, key, codex_id, start)
    monkeypatch.setenv(
        "CLAUDE_CONFIG_DIR" if request.param == "claude" else "CODEX_HOME", str(root)
    )
    return request.param


def _run(corpus, *args):
    prefix = ["--codex"] if corpus == "codex" else []
    return CliRunner().invoke(app, [*prefix, *args, "--path", CWD])


def _listed(result):
    """The session keys of a listing, in printed order."""
    order = []
    for line in result.stdout.splitlines():
        if line.startswith("@"):
            short = line.split("\t")[1]
            order += [
                key for key, c, x, _s, _u in CORPUS if c.startswith(short) or x.startswith(short)
            ]
    return order


# The parser itself.


def test_an_offset_is_applied_not_discarded():
    assert instant("2026-09-10T09:00:00+02:00") == datetime(2026, 9, 10, 7, tzinfo=UTC)


def test_a_zoneless_timestamp_is_read_as_utc_the_way_providers_record_it():
    assert instant("2026-09-10T09:00:00") == datetime(2026, 9, 10, 9, tzinfo=UTC)


def test_a_space_separated_timestamp_is_still_a_timestamp():
    assert instant("2026-09-10 09:00:00Z") == datetime(2026, 9, 10, 9, tzinfo=UTC)


def test_day_prints_the_moment_the_record_names():
    assert day("2026-09-10T09:00:00+02:00") == "2026-09-10T07:00:00Z"
    assert day("2026-09-11T00:30:00+02:00") == "2026-09-10T22:30:00Z"


def test_day_keeps_returning_empty_for_a_timestamp_it_cannot_read():
    assert day("") == ""
    assert day("whenever") == ""


def test_clock_is_utc_not_the_recorded_wall_time():
    assert clock("2026-09-10T09:05:00+02:00") == "07:05:00"
    assert clock("2026-09-10T09:05:00Z") == "09:05:00"
    assert clock("nonsense") == "--:--:--"


def test_date_of_is_the_utc_day_whose_window_contains_the_session():
    # ts[:10] would say 2026-09-11, which --since 2026-09-11 does not select.
    assert date_of("2026-09-11T00:30:00+02:00") == "2026-09-10"
    assert date_of("") == ""


def test_order_key_puts_an_unreadable_timestamp_before_every_real_one():
    assert order_key("") < order_key("1970-01-02T00:00:00Z")


def test_order_key_ranks_by_instant_where_string_order_disagrees():
    early, late = "2026-09-10T09:00:00+02:00", "2026-09-10T08:00:00Z"
    assert early > late  # as text
    assert order_key(early) < order_key(late)  # as moments


# Ordering, and the @N handles it decides.


def test_sessions_are_listed_newest_instant_first(corpus):
    result = _run(corpus, "list")
    assert result.exit_code == 0
    # S4 22:30, S3 08:00, then S1 and S2 which record the same moment.
    assert _listed(result)[:2] == ["S4", "S3"]
    assert set(_listed(result)[2:]) == {"S1", "S2"}


def test_sessions_recording_the_same_instant_are_adjacent(corpus):
    order = _listed(_run(corpus, "list"))
    assert abs(order.index("S1") - order.index("S2")) == 1


def test_sessions_recording_the_same_instant_display_the_same_started(corpus):
    rows = {}
    for line in _run(corpus, "list").stdout.splitlines():
        if line.startswith("@"):
            cells = line.split("\t")
            rows[cells[-1]] = cells[2]
    assert rows["open S1"] == rows["open S2"] == "2026-09-10T07:00:00Z"


def test_a_start_after_local_midnight_displays_its_utc_day(corpus):
    started = {
        line.split("\t")[-1]: line.split("\t")[2]
        for line in _run(corpus, "list").stdout.splitlines()
        if line.startswith("@")
    }
    assert started["open S4"] == "2026-09-10T22:30:00Z"


def test_list_json_metadata_carries_the_converted_instant(corpus):
    result = _run(corpus, "list", "--json")
    starts = {
        json.loads(line)["title"]: json.loads(line)["started"]
        for line in result.stdout.splitlines()
    }
    assert starts["open S1"] == starts["open S2"] == "2026-09-10T07:00:00Z"
    assert starts["open S4"] == "2026-09-10T22:30:00Z"


def test_handle_one_is_the_newest_by_instant(corpus):
    assert "S4" in _run(corpus, "show", "@1", "--tail", "1").stdout


def test_row_limits_take_the_newest_instants(corpus):
    assert _listed(_run(corpus, "list", "-n", "2")) == ["S4", "S3"]


# grep -c: the ordering and the date column.


def test_count_sort_started_orders_by_instant(corpus):
    rows = [
        line
        for line in _run(corpus, "grep", NEEDLE, "-c", "--sort", "started").stdout.splitlines()
        if not line.startswith("#")
    ]
    dates = [line.split("\t")[3] for line in rows if "\t" in line]
    assert dates == sorted(dates)
    titles = [line.split("\t")[-1] for line in rows if "\t" in line]
    assert titles[-1] == "open S4"  # 22:30Z is the newest, though its digits say the 11th


def test_count_date_column_is_the_utc_day(corpus):
    rows = _run(corpus, "grep", NEEDLE, "-c").stdout.splitlines()
    dates = {line.split("\t")[-1]: line.split("\t")[3] for line in rows if line.count("\t") >= 4}
    assert dates["open S4"] == "2026-09-10"


def test_count_json_started_is_the_utc_day(corpus):
    result = _run(corpus, "grep", NEEDLE, "-c", "--json")
    rows = {
        json.loads(line)["title"]: json.loads(line)["started"]
        for line in result.stdout.splitlines()
    }
    assert rows["open S4"] == "2026-09-10"


# What must not move: raw records, and literal window bounds.


def test_raw_json_keeps_the_source_timestamp_verbatim(corpus):
    result = _run(corpus, "show", "@1", "--json")
    stamps = {record.get("timestamp") for record in map(json.loads, result.stdout.splitlines())}
    assert "2026-09-11T00:30:00+02:00" in stamps
    assert "2026-09-10T22:30:00Z" not in stamps


@pytest.mark.parametrize(
    ("bound", "expected"),
    [
        (["--since", "2026-09-10"], {"S1", "S2", "S3", "S4"}),
        (["--before", "2026-09-11"], {"S1", "S2", "S3", "S4"}),
        (["--since", "2026-09-10", "--before", "2026-09-11"], {"S1", "S2", "S3", "S4"}),
        (["--since", "2026-09-11"], set()),
        (["--since", "2026-09-10T07:30:00Z"], {"S3", "S4"}),
        (["--before", "2026-09-10T07:30:00Z"], {"S1", "S2"}),
        (["--since", "2026-09-10T09:30:00+02:00"], {"S3", "S4"}),
    ],
)
def test_a_literal_window_bound_keeps_the_sessions_it_always_kept(corpus, bound, expected):
    # These sets are the measured pre-slice behavior: window filtering already
    # compared instants, so unifying the parser must not move any of them.
    assert set(_listed(_run(corpus, "list", *bound))) == expected


def test_the_session_a_window_keeps_is_the_one_whose_displayed_day_it_names(corpus):
    # Before this slice, S4 displayed 2026-09-11 while only the 10th's window
    # contained it. The two now agree.
    kept = _run(corpus, "list", "--since", "2026-09-10", "--before", "2026-09-11")
    assert "open S4" in kept.stdout
    assert "2026-09-10T22:30:00Z" in kept.stdout
    assert _listed(_run(corpus, "list", "--since", "2026-09-11")) == []


def test_a_handle_bound_follows_the_corrected_numbering(corpus):
    # @2 is now S3 at 08:00Z, not S1 at 07:00Z, so the bound is an hour later and
    # keeps two sessions rather than four. This is the renumbering, not the window.
    assert set(_listed(_run(corpus, "list", "--since", "@2"))) == {"S3", "S4"}
    assert set(_listed(_run(corpus, "list", "--before", "@2"))) == {"S1", "S2"}


def test_an_empty_window_still_exits_zero_for_a_listing(corpus):
    result = _run(corpus, "list", "--since", "2026-09-11")
    assert result.exit_code == 0  # SXR-AUD-017
    assert "kept none of 4 sessions" in result.stderr


def test_an_unreadable_window_bound_is_still_a_usage_error(corpus):
    assert _run(corpus, "list", "--since", "not-a-date").exit_code == 2
