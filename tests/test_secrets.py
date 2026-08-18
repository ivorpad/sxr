"""Secret detection and the masked audit view. All secrets here are synthetic."""

import base64
import json
from pathlib import Path

import pytest

from sxr.model import Event, SessionRef
from sxr.secrets import fingerprint, marker, scan_text
from sxr.secrets.detect import shannon
from sxr.secrets.fingerprint import _salt
from sxr.secrets.patterns import load_rules
from sxr.views_secrets import secrets_view

# Synthetic values shaped like real credentials; none are live.
# aws: AKIA + 16 base32 chars; github: ghp_ + 36 alnum; anthropic: 93 chars + AA.
FAKE_AWS = "AKIAQ2R7T5W3P6M4J6KX"
FAKE_GH = "ghp_" + "Zq8Xw2Kv9Rt4Yn7Bs3Mf6Hd1Jc5Lp0Wa2Ee" + "Q"
FAKE_ANTHROPIC = "sk-ant-api03-" + "Zq8Xw2Kv9Rt4Yn7Bs3Mf6Hd1Jc5Lp0W" * 3 + "AA"


@pytest.fixture(autouse=True)
def _tmp_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    _salt.cache_clear()


def _jwt() -> str:
    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return (
        f"{seg({'alg': 'HS256', 'typ': 'JWT'})}.{seg({'sub': 'tester'})}.c2lnbmF0dXJlLXNpZ25hdHVyZQ"
    )


def kinds(text: str, candidates: bool = False) -> list[str]:
    return [f.kind for f in scan_text(text, candidates)]


def test_ruleset_loads_and_mostly_compiles() -> None:
    ruleset = load_rules()
    assert len(ruleset.rules) > 150
    assert len(ruleset.skipped) < 30
    assert any(r.id == "anthropic-api-key" for r in ruleset.rules)


def test_provider_keys_are_certain() -> None:
    findings = scan_text(f"export AWS_KEY={FAKE_AWS} and token {FAKE_GH}")
    assert {(f.kind, f.severity) for f in findings} >= {
        ("aws-access-token", "certain"),
        ("github-pat", "certain"),
    }


def test_anthropic_key_span_is_exact() -> None:
    text = f'ANTHROPIC_API_KEY="{FAKE_ANTHROPIC}"\n'
    (f,) = scan_text(text)
    assert f.kind == "anthropic-api-key"
    assert text[f.start : f.end] == FAKE_ANTHROPIC


def test_aws_doc_example_is_allowlisted() -> None:
    assert scan_text("key AKIAIOSFODNN7EXAMPLE here") == []


def test_jwt_requires_decodable_header() -> None:
    assert kinds(f"token {_jwt()} ok") == ["jwt"]
    assert kinds("token eyJunkJunkJunkJunkJunkJunk.eyJunkJunkJunkJunkJunkJunk.sig-part-junk") == []


def test_url_credential_and_placeholder() -> None:
    findings = scan_text("db postgres://app:S3cretW0rd@host:5432/x")
    assert [(f.kind, f.severity) for f in findings] == [("url-credential", "probable")]
    assert findings[0].value == "S3cretW0rd"
    assert scan_text("postgres://user:<password>@host/db") == []


def test_password_assignment_skips_placeholders_and_markers() -> None:
    assert kinds("password = hunter2verySecret9") == ["password-assignment"]
    assert scan_text("password = ${DB_PASSWORD}") == []
    assert scan_text("password = [sxr:redacted:password-assignment:aabbccdd]") == []


def test_candidates_are_opt_in_and_exclude_hex() -> None:
    token = "Zq8Xw2Kv9Rt4Yn7Bs3Mf6Hd1Jc5L"
    sha = "3f2a9c1b8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a"
    text = f"blob {token} commit {sha}"
    assert kinds(text) == []
    assert kinds(text, candidates=True) == ["entropy-token"]


def test_overlaps_keep_best_severity() -> None:
    text = f"password = {FAKE_GH}"
    (f,) = scan_text(text)
    assert f.severity == "certain"


def test_shannon_bounds() -> None:
    assert shannon("aaaa") == 0.0
    assert shannon("abcd") == 2.0


def test_fingerprint_is_stable_and_salted(tmp_path, monkeypatch) -> None:
    a1, a2, b = fingerprint("value-a"), fingerprint("value-a"), fingerprint("value-b")
    assert a1 == a2 != b and len(a1) == 8
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt2"))
    _salt.cache_clear()
    assert fingerprint("value-a") != a1


def test_marker_format() -> None:
    m = marker("aws-access-token", FAKE_AWS)
    assert m == f"[sxr:redacted:aws-access-token:{fingerprint(FAKE_AWS)}]"


def _refs_and_parse():
    refs = [SessionRef("claude", f"sess{n}111-2222", Path(f"{n}.jsonl")) for n in (1, 2)]
    events = {
        "1.jsonl": [
            Event(4, "", "user", "text", f"my key is {FAKE_AWS}"),
            Event(9, "", "asst", "text", f"you pasted {FAKE_AWS}"),
        ],
        "2.jsonl": [Event(2, "", "user", "text", f"db postgres://app:S3cretW0rd@h/x {FAKE_AWS}")],
    }
    return refs, lambda p: events[str(p)]


def test_secrets_view_masks_values_and_aggregates(capsys) -> None:
    refs, parse = _refs_and_parse()
    assert secrets_view(refs, parse, False, False, None) == 0
    out = capsys.readouterr().out
    assert FAKE_AWS not in out and "S3cretW0rd" not in out
    aws_row = next(line for line in out.splitlines() if line.startswith("aws-access-token"))
    cells = aws_row.split("\t")
    assert cells[1] == "certain" and cells[3] == "2" and cells[4] == "3"
    assert cells[5] == "sess1111:4"
    assert "2 distinct secrets (1 certain)" in out


def test_secrets_view_json_is_masked_too(capsys) -> None:
    refs, parse = _refs_and_parse()
    assert secrets_view(refs, parse, False, True, None) == 0
    out = capsys.readouterr().out
    assert FAKE_AWS not in out and "S3cretW0rd" not in out
    rows = [json.loads(line) for line in out.splitlines()]
    assert {r["kind"] for r in rows} == {"aws-access-token", "url-credential"}


def test_secrets_view_clean_scope_exits_1(capsys) -> None:
    refs = [SessionRef("claude", "cccc1111-2222", Path("c.jsonl"))]
    assert (
        secrets_view(refs, lambda _: [Event(1, "", "user", "text", "hola")], False, False, None)
        == 1
    )
    assert "no secrets detected" in capsys.readouterr().err
