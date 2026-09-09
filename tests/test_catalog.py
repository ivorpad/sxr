"""Discovery reuses typed metadata while preserving scope and older cached indexes."""

import json

import pytest

from sxr.index_store import connect
from test_find import find
from test_providers import CLAUDE_RECORDS, _write_claude, _write_codex


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    return _write_claude(tmp_path, monkeypatch), _write_codex(tmp_path, monkeypatch)


def test_legacy_catalog_migration_preserves_warm_results(corpus, monkeypatch):
    import sxr.catalog as catalog

    expected = find("thing hello", "--any")
    with connect() as index, index.db:
        db = index.db
        db.execute(
            "CREATE TABLE catalog (path TEXT PRIMARY KEY, stamp TEXT, "
            "format INTEGER, metadata TEXT)"
        )
        for row in db.execute("SELECT * FROM catalog_fast").fetchall():
            metadata = dict(
                provider=row["provider"],
                id=row["identity"],
                path=row["path"],
                cwd=row["cwd"],
                started=row["started"],
                kind=row["kind"],
                extra=dict(parent_path=row["parent_path"], project_key=row["project_key"]),
            )
            stamp = [row[key] for key in ("dev", "ino", "size", "mtime", "ctime")]
            db.execute(
                "INSERT INTO catalog VALUES (?,?,?,?)",
                (row["path"], json.dumps(stamp), 2, json.dumps(metadata)),
            )
        db.execute("DROP TABLE catalog_fast")
    monkeypatch.setattr(catalog, "_reference", lambda *a: pytest.fail("reread cached header"))
    assert find("thing hello", "--any") == expected
    with connect() as index:
        assert index.db.execute("SELECT count(*) FROM catalog").fetchone()[0] == 2
        assert index.db.execute("SELECT count(*) FROM catalog_fast").fetchone()[0] == 2


def test_project_filter_precedes_reference_construction(corpus, monkeypatch):
    import sxr.catalog as catalog

    claude, _ = corpus
    other = claude.with_name("another-session.jsonl")
    other.write_text(json.dumps(dict(CLAUDE_RECORDS[0], cwd="/unrelated")))
    find("thing", "--all-projects")
    original = catalog.SessionRef

    def selected(**kwargs):
        assert kwargs["cwd"] != "/unrelated"
        return original(**kwargs)

    monkeypatch.setattr(catalog, "SessionRef", selected)
    assert find("thing")["total"] == 1


def test_legacy_scope_uses_full_claude_path_encoding(corpus):
    from sxr.cli import app
    from sxr.providers.claude_code import flatten_cwd
    from test_find import runner

    claude, _ = corpus
    target = "/some_project/repo.v2"
    source = claude.parent.with_name(flatten_cwd(target)) / "legacy.jsonl"
    source.parent.mkdir()
    record = dict(CLAUDE_RECORDS[0])
    record.pop("cwd")
    source.write_text(json.dumps(record))
    result = runner.invoke(app, ["find", "thing", "--paths", "--path", target])
    assert result.exit_code == 0 and result.stdout.strip() == str(source)
