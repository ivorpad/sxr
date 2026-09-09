"""Cached seeks must agree with full canonical parsing after source mutations."""

import json
import os
from dataclasses import asdict

import pytest

from sxr.file_selection import reference
from sxr.index_store import clear, connect, index_path
from sxr.read_cache import read_window
from sxr.views_read import ShowOpts, _selected, show
from test_codex_outcomes import _command, _record, _rollout
from test_providers import _write_claude, _write_codex


@pytest.fixture(params=[_write_claude, _write_codex])
def source(request, tmp_path, monkeypatch):
    path = request.param(tmp_path, monkeypatch)
    # Several Claude events may share the physical line and its source JSON.
    if request.param is _write_claude:
        records = path.read_text().splitlines()
        record = json.loads(records[1])
        record["message"]["content"].insert(0, {"type": "text", "text": "multi-block"})
        records[1] = json.dumps(record)
        path.write_text("\n".join(records))
    return path


def _read(path, opts):
    provider, ref = reference(path)
    events, total = read_window(ref, provider, opts)
    return ref, events, total


@pytest.mark.parametrize(
    "opts",
    [
        ShowOpts(around=2, context=0),
        ShowOpts(range_="2:4"),
        ShowOpts(type_="tool"),
        ShowOpts(tail=2),
        ShowOpts(tail=0),
        ShowOpts(tail=-1),
        ShowOpts(tail=2, full=True),
        ShowOpts(tail=2, errors=True),
        ShowOpts(type_="result", tail=1),
        ShowOpts(around=999, context=0),
        ShowOpts(type_="unknown"),
        ShowOpts(range_="1-3", type_="text"),
        ShowOpts(range_="1:3", tail=1),
    ],
)
def test_cold_and_warm_match_full_parser(source, opts, monkeypatch, capsys):
    provider, direct_ref = reference(source)
    direct = direct_ref.read(provider.parse)
    expected, _ = _selected(direct, opts)
    for _ in range(2):
        ref, events, total = _read(source, opts)
        selected, _ = _selected(events, opts)
        assert [asdict(e) for e in selected] == [asdict(e) for e in expected]
        assert total == len(direct)
        for json_out in (False, True):
            opts.json_out = json_out
            show(direct_ref, direct, opts)
            baseline = capsys.readouterr().out
            show(ref, events, opts, total_events=total)
            assert capsys.readouterr().out == baseline
    if opts.tail is None or opts.tail >= 0:
        monkeypatch.setattr(provider, "parse", lambda p: pytest.fail("warm read parsed full file"))
        _read(source, opts)


def test_codex_aliases_and_distant_results(tmp_path, monkeypatch):
    call = _record(
        "response_item",
        type="function_call",
        name="exec_command",
        call_id="one",
        arguments='{"cmd":"false"}',
    )
    filler = [_record("event_msg", type="agent_message", message="filler") for _ in range(50)]
    path, _ = _rollout(
        tmp_path,
        monkeypatch,
        [
            call,
            call,
            *filler,
            _command("item", 1, call_id="one", command="false", aggregated_output="failure"),
        ],
    )
    opts = ShowOpts(range_="1:3")
    provider, ref = reference(path)
    expected = ref.read(provider.parse)
    _read(path, opts)
    _, events, _ = _read(path, opts)
    assert [asdict(e) for e in events] == [asdict(e) for e in expected[:3]]
    assert events[1].kind == "duplicate.tool"
    assert events[1].raw["duplicate_of"] == 54


@pytest.mark.parametrize("mutation", ["append", "truncate", "replace", "same_mtime", "torn"])
def test_source_mutation_invalidates_old_annotations(source, mutation):
    opts = ShowOpts(full=True, tail=100)
    _read(source, opts)
    old = source.stat()
    contents = source.read_bytes()
    if mutation == "append":
        source.write_bytes(contents + b'\n{"type":"assistant","message":{"content":"added"}}')
    elif mutation == "truncate":
        source.write_bytes(contents.splitlines()[0] + b"\n")
    elif mutation == "replace":
        other = source.with_suffix(".new")
        other.write_bytes(
            contents.replace(b"boom", b"BANG").replace(b"do the thing", b"new request")
        )
        other.replace(source)
    elif mutation == "same_mtime":
        source.write_bytes(
            contents.replace(b"boom", b"BANG").replace(b"do the thing", b"new request!")
        )
        os.utime(source, ns=(old.st_atime_ns, old.st_mtime_ns))
    else:
        source.write_bytes(contents + b'\n{"type":')
        _read(source, opts)
        with source.open("ab") as stream:
            stream.write(b'"assistant","message":{"content":"completed"}}')
    provider, ref = reference(source)
    expected = ref.read(provider.parse)
    for _ in range(2):
        _, events, total = _read(source, opts)
        assert [asdict(e) for e in events] == [asdict(e) for e in _selected(expected, opts)[0]]
        assert total == len(expected)


def test_appended_claude_result_changes_earlier_call(tmp_path, monkeypatch):
    path = _write_claude(tmp_path, monkeypatch)
    records = path.read_text().splitlines()
    path.write_text("\n".join(records[:2]))
    opts = ShowOpts(around=2, context=0)
    _read(path, opts)
    assert _read(path, opts)[1][0].tag == ""
    with path.open("a") as stream:
        stream.write("\n" + records[2])
    _read(path, opts)
    assert _read(path, opts)[1][0].tag == "err"


@pytest.mark.parametrize(
    "failure", ["corrupt", "missing_row", "patch", "locked", "unavailable", "disabled"]
)
def test_cache_failures_fall_back(source, failure, monkeypatch):
    opts = ShowOpts(around=2, context=0)
    _read(source, opts)
    provider, ref = reference(source)
    expected = _selected(ref.read(provider.parse), opts)[0]
    db = None
    if failure == "corrupt":
        index_path().write_bytes(b"broken database")
    elif failure in ("missing_row", "patch"):
        with connect() as index, index.db:
            if failure == "missing_row":
                index.db.execute("DELETE FROM read_events WHERE ordinal=1")
            else:
                index.db.execute("UPDATE read_events SET patch='broken' WHERE ordinal=1")
    elif failure == "locked":
        import sqlite3

        db = sqlite3.connect(index_path())
        db.execute("BEGIN EXCLUSIVE")
    elif failure == "unavailable":
        monkeypatch.setenv("SXR_CACHE_DIR", str(source))
    else:
        monkeypatch.setenv("SXR_NO_CACHE", "1")
    try:
        _, events, _ = _read(source, opts)
        assert [asdict(e) for e in _selected(events, opts)[0]] == [asdict(e) for e in expected]
    finally:
        if db:
            db.close()


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_newline_framing_and_clear(source, newline):
    source.write_bytes(newline.join(source.read_bytes().splitlines()) + newline)
    opts = ShowOpts(range_="2:4")
    _read(source, opts)
    provider, ref = reference(source)
    expected = _selected(ref.read(provider.parse), opts)[0]
    assert [asdict(e) for e in _read(source, opts)[1]] == [asdict(e) for e in expected]
    clear()
    assert not index_path().exists()


def test_warm_zoom_decodes_only_selected_physical_records(source, monkeypatch):
    opts = ShowOpts(around=2, context=0)
    _read(source, opts)
    provider, _ = reference(source)
    name = "_record_events" if hasattr(provider, "_record_events") else "_record_event"
    original = getattr(provider, name)
    seen = []

    def decode(seq, record):
        seen.append(seq)
        return original(seq, record)

    monkeypatch.setattr(provider, name, decode)
    _read(source, opts)
    assert seen == [2]


def test_mutation_during_seek_falls_back(source, monkeypatch):
    import sxr.read_cache as cache

    opts = ShowOpts(around=2, context=0)
    _read(source, opts)
    original = cache.load_events

    def changed(path, provider, rows):
        events = original(path, provider, rows)
        path.write_bytes(
            path.read_bytes().replace(b"just test", b"just lint").replace(b'\\"ls\\"', b'\\"pwd\\"')
        )
        return events

    monkeypatch.setattr(cache, "load_events", changed)
    _, events, _ = _read(source, opts)
    provider, ref = reference(source)
    expected = _selected(ref.read(provider.parse), opts)[0]
    assert [asdict(e) for e in _selected(events, opts)[0]] == [asdict(e) for e in expected]


def test_mutation_during_build_does_not_publish_snapshot(source, monkeypatch):
    import sxr.read_positions as positions

    opts = ShowOpts(around=2, context=0)
    original = positions._positions

    def changed(path):
        rows = original(path)
        with path.open("ab") as stream:
            stream.write(b"\n")
        return rows

    monkeypatch.setattr(positions, "_positions", changed)
    _read(source, opts)
    with connect() as index:
        assert index.db.execute("SELECT count(*) FROM read_files").fetchone()[0] == 0


def test_blank_torn_and_invalid_utf8_preserve_source_coordinates(source):
    raw = source.read_bytes().splitlines()
    raw.insert(1, b"")
    raw.insert(2, b"broken")
    raw.append(b'{"type":"assistant","message":{"content":"bad byte \xff"}}')
    raw.append(b'{"type":')
    source.write_bytes(b"\n".join(raw))
    opts = ShowOpts(full=True, tail=100)
    _read(source, opts)
    provider, ref = reference(source)
    expected = ref.read(provider.parse)
    assert [asdict(e) for e in _read(source, opts)[1]] == [asdict(e) for e in expected]
