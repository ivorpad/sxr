"""Regression cases for timestamp boundaries and faithful retrieval evidence."""

import json
import sqlite3
from pathlib import Path

import pytest

from sxr.find_query import _excerpt
from sxr.handles import window
from sxr.model import SessionRef
from sxr.providers import claude_code
from sxr.views_info import tools_view
from sxr.views_read import errors


@pytest.mark.parametrize(
    "start,bound",
    [
        ("2026-08-01T12:00:00.123Z", "2026-08-01T12:00:00.123001Z"),
        ("2026-08-01T13:00:00+02:00", "2026-08-01T12:00:00Z"),
        ("2026-08-01T12:00:00", "2026-08-01T12:00:00.000001Z"),
    ],
)
def test_windows_compare_instants(start, bound):
    ref = SessionRef("claude", "fixture", Path("fixture.jsonl"), started=start)
    assert window([ref], before=bound) == [ref]
    assert window([ref], since=bound) == []
    assert window([ref], since="@1") == [ref]
    assert window([ref], before="@1") == []


def test_unknown_start_is_excluded_from_bounded_windows():
    refs = [SessionRef("claude", "fixture", Path("fixture.jsonl"), started="unknown")]
    assert window(refs) == refs
    assert window(refs, before="2026-09-01") == []


@pytest.mark.parametrize(
    "query,matching",
    [
        ("cafe", "café"),
        ("cafe", "cafe\u0301"),
        ("alpha_beta", "alpha-beta"),
        ("strasse", "STRASSE"),
        ("cafe rendezvous", "café rendezvous"),
    ],
)
def test_normalized_excerpt_uses_source_offsets(query, matching):
    text = ("ßİ prefix " * 180) + matching + " ending"
    with sqlite3.connect(":memory:") as db:
        excerpt = _excerpt(db, text, [query])
    assert matching in excerpt
    assert excerpt.removeprefix("…").removesuffix("…") in text
    assert len(excerpt) <= 602


def test_api_errors_preserve_raw_record_and_do_not_mark_tool_calls(tmp_path, capsys):
    record = {
        "type": "assistant",
        "isApiErrorMessage": True,
        "message": {
            "content": [
                {"type": "text", "text": "API error"},
                {"type": "text", "text": "retry detail"},
                {"type": "tool_use", "id": "call", "name": "Bash", "input": {"command": "true"}},
            ]
        },
    }
    path = tmp_path / "api.jsonl"
    path.write_text(json.dumps(record))
    events = claude_code.parse(path)
    assert [e.is_error for e in events] == [True, True, False]
    assert events[-1].tag == ""
    ref = claude_code._summarize(path)
    assert ref.errors == 1
    assert errors([ref], claude_code.parse, True, None) == 0
    assert json.loads(capsys.readouterr().out) == record


def test_skill_counts_use_the_owning_block(tmp_path, capsys):
    blocks = [
        {"type": "tool_use", "id": str(n), "name": name, "input": inputs}
        for n, (name, inputs) in enumerate(
            [
                ("Skill", {"skill": "notify"}),
                ("Skill", {"skill": "review"}),
                ("Bash", {"command": "echo fixture"}),
                ("Skill", {"skill": "notify"}),
            ]
        )
    ]
    path = tmp_path / "skills.jsonl"
    path.write_text(json.dumps({"type": "assistant", "message": {"content": blocks}}))
    assert tools_view(claude_code.parse(path), True) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["calls"] == {"Skill": 3, "Bash": 1}
    assert row["skill_inputs"] == {"notify": 2, "review": 1}
