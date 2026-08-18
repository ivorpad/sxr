"""sxr clean: dry run by default, validated atomic rewrite, live-session skip."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sxr.model import SessionRef
from sxr.secrets.clean import clean_view
from sxr.secrets.fingerprint import _salt, fingerprint
from test_secrets import FAKE_AWS

BAD_UTF8 = b'{"type":"x","note":"\xff\xfe broken"}\n'


@pytest.fixture(autouse=True)
def _tmp_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    _salt.cache_clear()


def _record(text: str) -> str:
    rec = {
        "type": "user",
        "timestamp": "2026-07-20T08:00:00.000Z",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    return json.dumps(rec)


@pytest.fixture
def corpus(tmp_path: Path):
    """One dirty session, one clean, one live; returns (refs, session_paths)."""
    dirty = tmp_path / "dirty.jsonl"
    dirty.write_bytes(
        (
            _record(f"my key is {FAKE_AWS} twice {FAKE_AWS}")
            + "\n"
            + _record("nothing here")
            + "\nnot json at all\n"
        ).encode()
        + BAD_UTF8
    )
    clean_f = tmp_path / "clean.jsonl"
    clean_f.write_text(_record("hola") + "\n")
    live = tmp_path / "live.jsonl"
    live.write_text(_record(f"fresh paste {FAKE_AWS}") + "\n")
    now = datetime.now(UTC).isoformat()
    refs = [
        SessionRef("claude", "dddd1111-2222", dirty, ended="2026-07-20T08:00:00.000Z"),
        SessionRef("claude", "cccc1111-2222", clean_f, ended="2026-07-20T08:00:00.000Z"),
        SessionRef("claude", "eeee1111-2222", live, ended=now),
    ]
    return refs, lambda ref: [ref.path]


def test_dry_run_reports_but_writes_nothing(corpus, capsys) -> None:
    refs, paths = corpus
    before = refs[0].path.read_bytes()
    assert clean_view(refs, paths, apply=False) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "nothing written" in out
    assert "dddd1111\tdirty.jsonl\t1\t2\taws-access-token(1)" in out
    assert "skipped 1 (live) session" in out
    assert refs[0].path.read_bytes() == before


def test_apply_rewrites_only_the_dirty_line(corpus, capsys) -> None:
    refs, paths = corpus
    original = refs[0].path.read_bytes().split(b"\n")
    assert clean_view(refs, paths, apply=True) == 0
    assert "cleaned 2 secret occurrences" in capsys.readouterr().out
    data = refs[0].path.read_bytes()
    lines = data.split(b"\n")
    mark = f"[sxr:redacted:aws-access-token:{fingerprint(FAKE_AWS)}]".encode()
    assert FAKE_AWS.encode() not in data
    assert lines[0].count(mark) == 2
    assert json.loads(lines[0])  # changed line still parses
    assert lines[1:] == original[1:]  # every other line byte-identical
    assert refs[2].path.read_bytes().find(FAKE_AWS.encode()) >= 0  # live untouched


def test_apply_is_idempotent(corpus, capsys) -> None:
    refs, paths = corpus
    assert clean_view(refs, paths, apply=True) == 0
    capsys.readouterr()
    assert clean_view(refs, paths, apply=True) == 1
    assert "nothing to clean" in capsys.readouterr().out


def test_clean_scope_exits_1(corpus, capsys) -> None:
    refs, paths = corpus
    assert clean_view([refs[1]], paths, apply=True) == 1
    assert "nothing to clean" in capsys.readouterr().out


def test_racing_writer_skips_the_file(corpus, capsys, monkeypatch) -> None:
    import sxr.secrets.clean as mod

    refs, paths = corpus
    real_stat = Path.stat

    def racing_stat(self, **kw):
        st = real_stat(self, **kw)
        if self.name == "dirty.jsonl" and racing_stat.calls > 0:
            racing_stat.calls += 1
            return real_stat(self.parent / "clean.jsonl", **kw)  # different size/mtime
        racing_stat.calls += 1
        return st

    racing_stat.calls = 0
    monkeypatch.setattr(mod.Path, "stat", racing_stat)
    before = refs[0].path.read_bytes()
    assert clean_view([refs[0]], paths, apply=True) == 1
    assert "changed while cleaning; skipped" in capsys.readouterr().err
    assert refs[0].path.read_bytes() == before
