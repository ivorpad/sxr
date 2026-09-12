"""Credential redaction across JSON representations, preserving surrounding records."""

import json

import pytest

from sxr.secrets.clean import _clean_line
from sxr.secrets.fingerprint import _salt
from test_secrets import FAKE_AWS


@pytest.fixture(autouse=True)
def private_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_SALT_FILE", str(tmp_path / "salt"))
    _salt.cache_clear()


@pytest.mark.parametrize("encoding", ["plain", "prefix", "all"])
def test_encoded_credentials_are_removed_without_reformatting_other_values(encoding):
    token = FAKE_AWS
    if encoding == "prefix":
        token = r"\u0041" + token[1:]
    elif encoding == "all":
        token = "".join(f"\\u{ord(c):04x}" for c in token)
    raw = ('{ "note" : "key ' + token + '", "safe": "\\u00e9", "n":1e+02 }\r\n').encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 1
    assert FAKE_AWS not in json.loads(rewritten)["note"]
    assert rewritten.startswith(b'{ "note" : "key [sxr:redacted:')
    assert rewritten.endswith(b'", "safe": "\\u00e9", "n":1e+02 }\r\n')
    assert _clean_line(rewritten)[1] == 0


def test_duplicate_members_and_nested_arrays_retain_all_values():
    raw = ('{"note":"' + FAKE_AWS + '","note":"safe","items":[["' + FAKE_AWS + '"]]}').encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 2
    assert FAKE_AWS.encode() not in rewritten
    assert rewritten.count(b'"note":') == 2
    assert rewritten.endswith(b'"]]}')
    assert json.loads(rewritten)["note"] == "safe"


@pytest.mark.parametrize("key", ["password", "PGPASSWORD", "api_key"])
def test_structured_credential_fields(key):
    value = "Zq8Xw2Kv9Rt4Yn7Bs3Mf6Hd1Jc5Lp0Wa2Ee"
    rewritten, count, _ = _clean_line(json.dumps({key: value}).encode())
    assert count == 1
    assert value not in json.loads(rewritten)[key]


@pytest.mark.parametrize("value", ['spaces and "quotes" / slashes', "long-" * 30, "abc\ud800def"])
def test_entire_structured_password_is_redacted(value):
    raw = json.dumps({"password": value}).encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 1
    assert json.loads(rewritten)["password"].startswith("[sxr:redacted:")
    assert json.loads(rewritten)["password"].endswith("]")


def test_long_multiline_private_key_is_removed():
    value = "-----BEGIN PRIVATE KEY-----\n" + "aB3dE6gH9JkL0mN2\n" * 400
    value += "-----END PRIVATE KEY-----"
    rewritten, count, _ = _clean_line(json.dumps({"text": value}).encode())
    assert count == 1
    assert "PRIVATE KEY" not in json.loads(rewritten)["text"]


def test_replacements_do_not_change_property_names():
    raw = json.dumps({FAKE_AWS: "key " + FAKE_AWS}).encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 1
    assert FAKE_AWS in json.loads(rewritten)
    assert FAKE_AWS not in json.loads(rewritten)[FAKE_AWS]


def test_credential_value_does_not_rewrite_matching_protocol_metadata():
    raw = b'{"password":"user", "role":"user", "content":"another user"}'
    rewritten, count, _ = _clean_line(raw)
    record = json.loads(rewritten)
    assert count == 1
    assert record["role"] == "user" and record["content"] == "another user"
    assert record["password"].startswith("[sxr:redacted:")


def test_earlier_duplicate_member_cannot_hide_a_credential():
    raw = ('{"text":"' + FAKE_AWS + '","text":"safe"}').encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 1
    assert FAKE_AWS.encode() not in rewritten
    assert rewritten.count(b'"text":') == 2


def test_overlapping_values_are_replaced_once_longest_first():
    short = "UniquePass7"
    long = short + "Suffix8"
    raw = json.dumps({"first": "password = " + short, "second": "password = " + long}).encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 2
    assert short not in rewritten.decode() and "Suffix8" not in rewritten.decode()
    assert rewritten.count(b"[sxr:redacted:") == 2


@pytest.mark.parametrize("value", ["${DB_PASSWORD}", "<password>", "[sxr:redacted:kind:12345678]"])
def test_structured_placeholders_stay_unchanged(value):
    raw = json.dumps({"password": value}).encode()
    assert _clean_line(raw) == (raw, 0, [])


@pytest.mark.parametrize("wrappers", range(4))
def test_serialized_json_redacts_entire_password_through_string_wrappers(wrappers):
    password = 'several synthetic words with "quotes" and / slashes'
    arguments = json.dumps({"password": password, "note": "keep this"})
    for _ in range(wrappers):
        arguments = json.dumps(arguments)
    raw = json.dumps({"arguments": arguments}).encode()
    rewritten, count, _ = _clean_line(raw)
    assert count == 1
    value = json.loads(rewritten)["arguments"]
    for _ in range(wrappers):
        value = json.loads(value)
    decoded = json.loads(value)
    assert decoded["password"].startswith("[sxr:redacted:")
    assert decoded["password"].endswith("]")
    assert "synthetic" not in decoded["password"]
    assert decoded["note"] == "keep this"
    assert _clean_line(rewritten)[1] == 0


def test_output_containing_several_json_fragments_and_plain_credentials():
    encoded_key = r"\u0041" + FAKE_AWS[1:]
    output = (
        'prefix [not JSON] {"key":"'
        + encoded_key
        + '","key":"safe"} then [{"password":"words with spaces"}] suffix '
        + FAKE_AWS
    )
    rewritten, count, _ = _clean_line(json.dumps({"output": output}).encode())
    decoded = json.loads(rewritten)["output"]
    assert count == 3
    assert FAKE_AWS not in decoded and encoded_key not in decoded
    assert "words with spaces" not in decoded
    assert decoded.startswith("prefix [not JSON] ")
    assert decoded.count('"key":') == 2 and '"key":"safe"' in decoded
    assert " then " in decoded and " suffix " in decoded
    assert _clean_line(rewritten)[1] == 0


@pytest.mark.parametrize("prefix,suffix", [("é", ""), ("", "中文"), ("İ" * 3000, "")])
def test_unicode_context_does_not_hide_or_shift_credential_spans(prefix, suffix):
    raw = json.dumps({"text": prefix + FAKE_AWS + suffix}).encode()
    rewritten, count, _ = _clean_line(raw)
    decoded = json.loads(rewritten)["text"]
    assert count == 1 and FAKE_AWS not in decoded
    assert decoded.startswith(prefix + "[sxr:redacted:")
    assert decoded.endswith("]" + suffix)


def test_plain_private_key_enclosing_json_is_redacted_in_full():
    key = "-----BEGIN PRIVATE KEY-----\n" + "aB3dE6gH" * 10
    key += '\n{"password":"nested value"}\n-----END PRIVATE KEY-----'
    rewritten, count, _ = _clean_line(json.dumps({"text": key}).encode())
    decoded = json.loads(rewritten)["text"]
    assert count == 1
    assert decoded.startswith("[sxr:redacted:private-key:") and decoded.endswith("]")
