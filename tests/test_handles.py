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


def test_duplicate_exact_ids_fail_with_distinct_paths(capsys) -> None:
    refs = [SessionRef("codex", "abcd-1234", Path(path)) for path in ("a.jsonl", "b.jsonl")]
    with pytest.raises(SystemExit) as exc:
        resolve("abcd-1234", refs)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "duplicate id" in err and "a.jsonl" in err and "b.jsonl" in err
    assert resolve("@2", refs) == [refs[1]]


def test_codex_short_id_collision_names_recoverable_candidates(capsys) -> None:
    refs = [
        SessionRef("codex", "019f9510-5499-7000-8000-000000000001", Path("a.jsonl")),
        SessionRef("codex", "019f9510-5499-7000-8000-000000000002", Path("b.jsonl")),
    ]
    assert refs[0].short_id == refs[1].short_id
    with pytest.raises(SystemExit) as exc:
        resolve(refs[0].short_id, refs)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    for ref in refs:
        assert ref.id in err
        assert resolve(ref.id, refs) == [ref]


def test_parent_qualified_child_identity() -> None:
    refs = [
        SessionRef("claude", "abcd-1234/agent-5678", Path("child.jsonl")),
        SessionRef("claude", "abcd-1234", Path("parent.jsonl")),
    ]
    assert resolve("abcd-1234", refs) == [refs[1]]
    assert resolve("abcd-1234/agent-56", refs) == [refs[0]]
    assert resolve("ABCD-1234/AGENT-5678", refs) == [refs[0]]


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
