"""Handle resolution: @N, ranges, prefixes, names, and failure exits."""

from pathlib import Path

import pytest

from sxr.handles import resolve
from sxr.model import SessionRef


def _refs() -> list[SessionRef]:
    return [
        SessionRef("claude", "a029afdd-1111", Path("a.jsonl"), name="some-name"),
        SessionRef("claude", "a02c1f77-2222", Path("b.jsonl"), title="Probe staging"),
        SessionRef("claude", "7ea3b9c1-3333", Path("c.jsonl")),
    ]


def test_default_is_newest() -> None:
    assert resolve(None, _refs())[0].id.startswith("a029")


def test_ordinal_and_range() -> None:
    refs = _refs()
    assert resolve("@2", refs) == [refs[1]]
    assert resolve("@1:@3", refs) == refs


def test_out_of_range_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        resolve("@9", _refs())
    assert exc.value.code == 2


def test_unique_prefix_and_ambiguity() -> None:
    refs = _refs()
    assert resolve("7ea", refs) == [refs[2]]
    with pytest.raises(SystemExit) as exc:
        resolve("a0", refs)
    assert exc.value.code == 2


def test_name_and_title_match() -> None:
    refs = _refs()
    assert resolve("some-name", refs) == [refs[0]]
    assert resolve("staging", refs) == [refs[1]]


def test_unknown_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        resolve("zzz", _refs())
    assert exc.value.code == 2


def test_ambiguous_candidates_are_capped_not_inlined_whole(capsys) -> None:
    bomb = "first message " * 600
    refs = [
        SessionRef("claude", f"cafe{n}111-2222", Path(f"{n}.jsonl"), title=f"probe {bomb}")
        for n in range(8)
    ]
    with pytest.raises(SystemExit) as exc:
        resolve("probe", refs)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert len(err) < 700  # the old error inlined ~8KB of first-message text
    assert err.count('"') == 10  # 5 candidates, no more
    assert "+3 more" in err


def test_missing_and_hint_texts_are_used(capsys) -> None:
    with pytest.raises(SystemExit):
        resolve("nope", _refs(), missing="'nope' is not a session", hint="one pattern per call")
    err = capsys.readouterr().err
    assert err.startswith("error: 'nope' is not a session")
    assert "one pattern per call" not in err  # missing already teaches; no double hint

    with pytest.raises(SystemExit):
        resolve("a0", _refs(), hint="one pattern per call")
    assert "# one pattern per call" in capsys.readouterr().err
