"""Authenticated append checkpoints, torn tails and changed source snapshots."""

import hashlib
import json
import os

import pytest

from sxr import index_records


def record(text, provider="claude", newline=True):
    row = (
        {"type": "event_msg", "payload": {"type": "user_message", "message": text}}
        if provider == "codex"
        else {"type": "user", "message": {"content": text}}
    )
    return (json.dumps(row) + ("\n" if newline else "")).encode()


def previous(update):
    return {
        "stamp": json.dumps(update.stamp),
        "digest": update.digest,
        "offset": update.offset,
        "lines": update.lines,
    }


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("terminated", [True, False])
def test_append_decodes_only_suffix_and_replaces_unfinished_tail(
    tmp_path, monkeypatch, provider, terminated
):
    path = tmp_path / "session.jsonl"
    path.write_bytes(record("first", provider) + record("second", provider, terminated))
    initial = index_records.read_update(path, provider, None)
    seen = []
    original = index_records.record_text

    def counted(seq, raw, provider):
        seen.append(seq)
        return original(seq, raw, provider)

    monkeypatch.setattr(index_records, "record_text", counted)
    with path.open("ab") as stream:
        stream.write((b"" if terminated else b"\n") + record("new needle", provider))
    updated = index_records.read_update(path, provider, previous(initial))
    assert updated.append
    assert seen == ([3] if terminated else [2, 3])
    assert updated.digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert updated.offset == path.stat().st_size and updated.lines == 3
    assert "new needle" in updated.documents[-1][0]


def test_torn_json_is_revisited_at_original_coordinate(tmp_path):
    path = tmp_path / "session.jsonl"
    tail = record("completed tail", newline=False)
    path.write_bytes(record("first") + b"not json\n\n" + tail[:17])
    initial = index_records.read_update(path, "claude", None)
    assert initial.lines == 3
    with path.open("ab") as stream:
        stream.write(tail[17:])
    updated = index_records.read_update(path, "claude", previous(initial))
    assert updated.append
    assert updated.documents == [("completed tail", 4, 4, True)]
    assert updated.lines == 3 and updated.offset == initial.offset


@pytest.mark.parametrize("mutation", ["same_size", "grow_rewrite", "truncate", "replace"])
def test_edits_never_masquerade_as_appends(tmp_path, mutation):
    path = tmp_path / "session.jsonl"
    path.write_bytes(record("old needle") + record("padding"))
    initial = index_records.read_update(path, "claude", None)
    stat = path.stat()
    if mutation == "same_size":
        path.write_bytes(path.read_bytes().replace(b"old needle", b"new needle"))
    elif mutation == "grow_rewrite":
        path.write_bytes(record("different prefix") + record("padding") + record("more"))
    elif mutation == "truncate":
        path.write_bytes(record("short"))
    else:
        replacement = path.with_name("replacement")
        replacement.write_bytes(record("new needle") + record("padding"))
        replacement.replace(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    updated = index_records.read_update(path, "claude", previous(initial))
    assert not updated.append
    assert "old needle" not in "\n".join(doc[0] for doc in updated.documents)
    assert updated.digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_changing_file_is_not_committed_as_a_stable_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "session.jsonl"
    path.write_bytes(record("first"))
    original = index_records.record_text
    changed = False

    def racing(seq, raw, provider):
        nonlocal changed
        if not changed:
            changed = True
            with path.open("ab") as stream:
                stream.write(record("arrived during read"))
        return original(seq, raw, provider)

    monkeypatch.setattr(index_records, "record_text", racing)
    assert index_records.read_update(path, "claude", None) is None


def test_document_chunks_keep_whole_event_text(tmp_path, monkeypatch):
    path = tmp_path / "session.jsonl"
    monkeypatch.setattr(index_records, "CHUNK_CHARS", 4)
    text = "a needle that crosses a chunk boundary"
    path.write_bytes(record(text) + record("second"))
    update = index_records.read_update(path, "claude", None)
    assert update.documents == [(text, 1, 1, False), ("second", 2, 2, False)]


def test_repeated_text_is_indexed_once_per_update(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(record("repeated needle") * 10)
    update = index_records.read_update(path, "claude", None)
    assert update.documents == [("repeated needle", 1, 10, False)]
    assert update.lines == 10
