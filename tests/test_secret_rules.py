"""Vendored rule compatibility and previously skipped credential formats."""

import re

import pytest

from sxr.secrets.detect import _apply_rule, scan_text
from sxr.secrets.patterns import keyword_index, load_rules
from sxr.secrets.rule_regex import compile_rule
from test_secrets import FAKE_AWS

BODY = "Zq8Xw2Kv9Rt4Yn7Bs3Mf6Hd1Jc5Lp0Wa2Ee"


def test_all_bundled_text_rules_compile():
    rules = load_rules()
    assert len(rules.rules) == 221
    assert rules.skipped == ()


@pytest.mark.parametrize(
    "kind,value",
    [
        ("adobe-client-secret", "p8e-" + BODY[:32]),
        ("alibaba-access-key-id", "LTAI" + BODY[:20]),
        ("authress-service-client-access-key", "sc_abcde.abcd.acc_abcdefghij." + BODY),
        ("doppler-api-token", "dp.pt." + (BODY * 2)[:43]),
        ("duffel-api-token", "duffel_live_" + (BODY * 2)[:43]),
        ("dynatrace-api-token", "dt0c01." + BODY[:24] + "." + (BODY * 2)[:64]),
        ("easypost-api-token", "EZAK" + (BODY * 2)[:54]),
        ("easypost-test-api-token", "EZTK" + (BODY * 2)[:54]),
        ("facebook-page-access-token", "EAAM" + BODY * 4),
        ("flutterwave-encryption-key", "FLWSECK_TEST-" + "aB3dE6fH9A2c"),
        ("flutterwave-public-key", "FLWPUBK_TEST-" + "aB3dE6fH" * 4 + "-X"),
        ("flutterwave-secret-key", "FLWSECK_TEST-" + "aB3dE6fH" * 4 + "-X"),
        ("frameio-api-token", "fio-u-" + (BODY * 2)[:64]),
        ("gocardless-api-token", "gocardless = live_" + (BODY * 2)[:40]),
        ("intra42-client-secret", "s-s4t2ud-" + "abcdef0123456789" * 4),
        ("linear-api-key", "lin_api_" + (BODY * 2)[:40]),
        ("planetscale-api-token", "pscale_tkn_" + BODY),
        ("planetscale-password", "pscale_pw_" + BODY),
        (
            "postman-api-token",
            "PMAK-" + ("abcdef0123456789" * 2)[:24] + "-" + ("abcdef0123456789" * 3)[:34],
        ),
        ("sendgrid-api-token", "SG." + (BODY * 2)[:66]),
        ("sendinblue-api-token", "xkeysib-" + "abcdef0123456789" * 4 + "-" + BODY[:16]),
    ],
)
def test_restored_rules_detect_synthetic_credentials(kind, value):
    assert kind in {f.kind for f in scan_text(value)}


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("header", ["Authorization: Basic", "Authorization: Bearer", "X-API-Key:"])
def test_curl_header_alternative_capture_groups(quote, header):
    text = f"curl -H {quote}{header} {BODY}{quote} https://example.invalid"
    rule = next(r for r in load_rules().rules if r.id == "curl-auth-header")
    findings = _apply_rule(rule, text, 0)
    assert len(findings) == 1
    assert findings[0].value == BODY
    assert BODY in {f.value for f in scan_text(text)}


def test_case_sensitive_prefix_and_scoped_disable_are_preserved():
    rules = {r.id: r.regex for r in load_rules().rules}
    assert rules["linear-api-key"].fullmatch("lin_api_" + "A" * 40)
    assert not rules["linear-api-key"].fullmatch("LIN_API_" + "A" * 40)
    authress = rules["authress-service-client-access-key"]
    assert authress.fullmatch("sc_ABCDE.ABCD.acc_abcdefghij." + BODY)
    assert not authress.fullmatch("sc_ABCDE.ABCD.ACC_abcdefghij." + BODY)


def test_shared_keyword_prefixes_preserve_existing_matches_and_positions():
    combined, by_keyword, _ = keyword_index()
    baseline = re.compile("|".join(re.escape(k) for k in sorted(by_keyword, key=len, reverse=True)))
    text = "ordinary output " + " / ".join(by_keyword) + " lin_api_ api_key -----begin "
    assert [(m.group(), m.span()) for m in combined.finditer(text)] == [
        (m.group(), m.span()) for m in baseline.finditer(text)
    ]


@pytest.mark.parametrize("text", ["é" + FAKE_AWS, FAKE_AWS + "é", "中文" + FAKE_AWS])
def test_go_word_boundaries_beside_unicode_text(text):
    assert FAKE_AWS in {f.value for f in scan_text(text)}


def test_inline_flags_preserve_alternatives_and_enclosing_scope():
    regex = compile_rule(r"(a(?i)b|c)d")
    assert regex.fullmatch("aBd") and regex.fullmatch("Cd")
    assert not regex.fullmatch("aCD") and not regex.fullmatch("CD")
    assert compile_rule(r"[[:alnum:]]+\z").fullmatch("A9")
    assert not compile_rule(r"[[:alnum:]]+\z").fullmatch("A9\n")
