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
