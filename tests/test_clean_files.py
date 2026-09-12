"""Cleaning writes only changed files and checks each physical source independently."""

import io
import json
import os
from datetime import UTC, datetime

import pytest

from sxr.model import SessionRef
from sxr.secrets import clean
from sxr.secrets.files import CHUNK, _reverse_lines, last_timestamp
from test_secrets import FAKE_AWS


@pytest.fixture(autouse=True)
def salt(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))


def _write(path, text=FAKE_AWS, timestamp="2026-01-01T00:00:00Z"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"timestamp": timestamp, "text": text}) + "\n")
    return path


def test_clean_file_creates_no_temporary_copy(tmp_path, monkeypatch):
    path = _write(tmp_path / "clean.jsonl", "ordinary text")
    before = path.stat()
    monkeypatch.setattr(clean.tempfile, "NamedTemporaryFile", lambda **kw: pytest.fail("temp copy"))
    assert not clean._clean_file(path, True).error
    after = path.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


def test_first_change_copies_prefix_and_preserves_permissions(tmp_path):
    path = tmp_path / "dirty.jsonl"
    prefix = (b'{ "text": "ordinary" }\r\n' * 50000) + b"not JSON\n"
    raw = json.dumps({"text": FAKE_AWS}).encode()
    path.write_bytes(prefix + raw + b'\n{"suffix":true}')
    path.chmod(0o640)
    result = clean._clean_file(path, True)
    assert result.replacements == 1 and not result.error
    after = path.read_bytes()
    assert after.startswith(prefix) and after.endswith(b'\n{"suffix":true}')
    assert FAKE_AWS.encode() not in after
    assert path.stat().st_mode & 0o777 == 0o640
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dirty.jsonl", "salt"]


def test_partial_temporary_file_is_removed_after_failure(tmp_path, monkeypatch):
    path = _write(tmp_path / "dirty.jsonl")
    original = path.read_bytes()

    def fail(*args):
        raise OSError("test replacement failure")

    monkeypatch.setattr(clean.os, "replace", fail)
    result = clean._clean_file(path, True)
    assert result.error
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dirty.jsonl", "salt"]


def test_failed_temporary_cleanup_is_reported_without_a_traceback(tmp_path, monkeypatch):
    path = _write(tmp_path / "dirty.jsonl")
    original = path.read_bytes()
    unlink = clean.Path.unlink

    def fail_replace(*args):
        raise OSError("test replacement failure")

    def fail_unlink(self, **kwargs):
        raise PermissionError("test cleanup failure")

    monkeypatch.setattr(clean.os, "replace", fail_replace)
    monkeypatch.setattr(clean.Path, "unlink", fail_unlink)
    result = clean._clean_file(path, True)
    assert "test replacement failure" in result.error
    assert "cannot remove temporary file" in result.error
    assert path.read_bytes() == original
    for remaining in tmp_path.iterdir():
        if remaining.name not in {"dirty.jsonl", "salt"}:
            unlink(remaining)


def test_same_size_change_with_restored_mtime_is_rejected(tmp_path, monkeypatch):
    path = _write(tmp_path / "dirty.jsonl")
    stamp = path.stat()
    original = clean._clean_line

    def change(raw):
        result = original(raw)
        path.write_bytes(path.read_bytes().replace(b"text", b"note"))
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        return result

    monkeypatch.setattr(clean, "_clean_line", change)
    result = clean._clean_file(path, True)
    assert "changed while cleaning" in result.error
    assert FAKE_AWS.encode() in path.read_bytes()


def test_all_provenance_copies_are_cleaned_once(tmp_path, monkeypatch):
    first = _write(tmp_path / "one.jsonl")
    second = _write(tmp_path / "two.jsonl")
    ref = SessionRef("codex", "one", first, extra={"provenance": [str(first), str(second)]})
    calls = []
    original = clean._clean_file

    def counted(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(clean, "_clean_file", counted)
    assert clean.clean_view([ref, ref], lambda r: [r.path], True) == 0
    assert calls == [first, second]
    assert all(FAKE_AWS.encode() not in path.read_bytes() for path in calls)


def test_nested_child_activity_is_checked_per_file(tmp_path):
    parent = _write(tmp_path / "parent.jsonl")
    live = _write(tmp_path / "parent/subagents/live.jsonl", timestamp=datetime.now(UTC).isoformat())
    nested = _write(tmp_path / "parent/fork/subagents/deeper/old.jsonl")
    ref = SessionRef("claude", "parent", parent)
    assert clean.clean_view([ref], lambda r: [r.path, live], True) == 0
    assert FAKE_AWS.encode() in live.read_bytes()
    assert all(FAKE_AWS.encode() not in p.read_bytes() for p in (parent, nested))


def test_explicit_file_keeps_copies_and_children_out_of_scope(tmp_path):
    parent = _write(tmp_path / "parent.jsonl")
    child = _write(tmp_path / "parent/subagents/child.jsonl")
    copy = _write(tmp_path / "copy.jsonl")
    ref = SessionRef(
        "claude", "parent", parent, extra={"explicit_file": True, "provenance": [str(copy)]}
    )
    assert clean.clean_view([ref], lambda r: [r.path, child], True) == 0
    assert FAKE_AWS.encode() not in parent.read_bytes()
    assert all(FAKE_AWS.encode() in p.read_bytes() for p in (child, copy))


def test_missing_file_reports_incomplete_cleaning(tmp_path, capsys):
    ref = SessionRef("codex", "missing", tmp_path / "missing.jsonl")
    assert clean.clean_view([ref], lambda r: [r.path], False) == 2
    assert "incomplete" in capsys.readouterr().err


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n"])
def test_reverse_lines_handles_large_records_and_line_endings(ending):
    data = b"first\n" + b"x" * (CHUNK * 3) + b"\nlast" + ending
    assert list(_reverse_lines(io.BytesIO(data))) == list(reversed(data.split(b"\n")))


def test_activity_skips_unstamped_or_malformed_tail_records(tmp_path):
    path = _write(tmp_path / "tail.jsonl")
    with path.open("ab") as stream:
        stream.write(b'{"type":"note"}\nnot json\n{"unfinished"')
    assert last_timestamp(path) == "2026-01-01T00:00:00Z"


@pytest.mark.parametrize("explicit", [False, True])
def test_symlink_cleans_the_target_and_preserves_the_link(tmp_path, explicit):
    target = _write(tmp_path / "target.jsonl")
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(target)
    ref = SessionRef("codex", "alias", alias, extra={"explicit_file": explicit})
    assert clean.clean_view([ref], lambda r: [r.path], True) == 0
    assert alias.is_symlink() and alias.resolve() == target
    assert FAKE_AWS.encode() not in target.read_bytes()


def test_aliases_of_the_same_file_are_cleaned_once(tmp_path, monkeypatch):
    target = _write(tmp_path / "target.jsonl")
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(target)
    ref = SessionRef("codex", "target", target, extra={"provenance": [str(alias)]})
    calls = []
    original = clean._clean_file

    def counted(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(clean, "_clean_file", counted)
    assert clean.clean_view([ref], lambda r: [r.path], True) == 0
    assert calls == [target]


def test_append_during_temporary_file_chmod_is_preserved(tmp_path, monkeypatch):
    path = _write(tmp_path / "dirty.jsonl")
    original = path.read_bytes()
    appended = b'{"text":"newly appended record"}\n'
    chmod = clean.os.chmod

    def concurrent_append(*args, **kwargs):
        with path.open("ab") as stream:
            stream.write(appended)
        chmod(*args, **kwargs)

    monkeypatch.setattr(clean.os, "chmod", concurrent_append)
    result = clean._clean_file(path, True)
    assert "changed while cleaning" in result.error
    assert path.read_bytes() == original + appended
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dirty.jsonl", "salt"]


def test_activity_decode_failure_reports_error_and_continues_cleaning(
    tmp_path, monkeypatch, capsys
):
    broken = _write(tmp_path / "huge-number.jsonl")
    with broken.open("ab") as stream:
        stream.write(b'{"number":' + b"1" * 5000 + b"}\n")
    original = broken.read_bytes()
    valid = _write(tmp_path / "valid.jsonl")
    refs = [SessionRef("codex", path.stem, path) for path in (broken, valid)]
    clears = []
    monkeypatch.setattr(clean, "clear", lambda: clears.append(True))
    assert clean.clean_view(refs, lambda r: [r.path], True) == 2
    output = capsys.readouterr()
    assert "ValueError" in output.err and "incomplete" in output.err
    assert "Traceback" not in output.err and FAKE_AWS not in output.err
    assert broken.read_bytes() == original
    assert FAKE_AWS.encode() not in valid.read_bytes()
    assert len(clears) == 2
