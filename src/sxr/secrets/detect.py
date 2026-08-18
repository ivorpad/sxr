"""Tiered secret detection over text; returns spans, never prints.

Three severities, calibrated by the 2026-08 corpus ablation:
  certain   provider-specific gitleaks rules (plus JWT structural check)
  probable  generic gitleaks rules, URL userinfo creds, password assignments
  candidate high-entropy tokens; opt-in, review material only

An ML pass (StarPII) lost that ablation on every tier, so detection here is
deliberately deterministic: patterns, structure, and entropy only.
"""

import base64
import json
import math
import re
from collections import Counter
from dataclasses import dataclass

from sxr.secrets.patterns import GENERIC_RULE_IDS, Rule, keyword_index, load_rules

SEVERITIES = ("certain", "probable", "candidate")

URL_CRED = re.compile(
    r"\b[a-zA-Z][a-zA-Z0-9+.-]{1,15}://([^/\s:@'\"]{1,64}):([^@\s'\"]{3,64})@[A-Za-z0-9.\[-]"
)
ASSIGN = re.compile(
    r"(?i)\b(password|passwd|pwd|pgpassword|mysql_pwd)\b['\"]?\s*[:=]\s*['\"]?"
    r"([^\s'\",;&|]{4,64})"
)
PLACEHOLDER = re.compile(
    r"(?i)^(\$|\$\{|<|%|\{\{|\*+$|x+$|password$|passwd$|secret$|changeme|example|your[_-]|"
    r"hunter2$|redacted|placeholder|none$|null$|true$|false$|\.\.\.|\[sxr:redacted)"
)
CANDIDATE = re.compile(r"[A-Za-z0-9_\-+/=]{20,}")
HEXISH = re.compile(r"[0-9a-fA-F-]+\Z")


@dataclass
class Finding:
    """One detected secret span; value stays in memory for fingerprinting."""

    kind: str
    severity: str
    start: int
    end: int
    value: str


def shannon(value: str) -> float:
    """Bits per character; gitleaks-style threshold input."""
    if not value:
        return 0.0
    counts = Counter(value)
    n = len(value)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def _jwt_ok(value: str) -> bool:
    """Does the first segment decode to a JSON header with an alg?"""
    head = value.split(".", 1)[0]
    try:
        obj = json.loads(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
    except (ValueError, TypeError):
        return False
    return isinstance(obj, dict) and "alg" in obj


def _allowed(rule: Rule, ruleset, secret: str, match: str) -> bool:
    """Should this match be discarded per rule or global allowlists?"""
    low = secret.lower()
    for stop in rule.allow_stopwords + ruleset.allow_stopwords:
        if stop in low:
            return True
    return any(
        rx.search(secret) or rx.search(match) for rx in rule.allow_regexes + ruleset.allow_regexes
    )


SMALL_TEXT = 2048
WINDOW_BEFORE = 128
WINDOW_AFTER = 4096  # generous: a 4096-bit RSA private key body is ~3.2k chars


def _apply_rule(rule: Rule, text: str, offset: int) -> list[Finding]:
    """One rule over one text fragment; offsets shifted back to the whole text."""
    ruleset = load_rules()
    found = []
    for m in rule.regex.finditer(text):
        group = rule.secret_group or (1 if m.lastindex else 0)
        secret = m.group(group) or ""
        if not secret or (rule.entropy and shannon(secret) < rule.entropy):
            continue
        if _allowed(rule, ruleset, secret, m.group(0)):
            continue
        if rule.id == "jwt" and not _jwt_ok(secret):
            continue
        severity = "probable" if rule.id in GENERIC_RULE_IDS else "certain"
        found.append(
            Finding(rule.id, severity, offset + m.start(group), offset + m.end(group), secret)
        )
    return found


def _rule_findings(text: str, low: str) -> list[Finding]:
    """gitleaks rules, each scanning only windows around its own keyword hits.

    Small texts skip the windowing. A rule with no keywords always scans
    whole; merged windows never overlap, so no duplicate findings. The
    trade-off is a secret starting more than WINDOW_AFTER chars past its
    keyword goes unseen; the window is sized so that does not happen to
    any real credential shape in the ruleset.
    """
    combined, by_keyword, bare = keyword_index()
    found = []
    if len(text) <= SMALL_TEXT:
        triggered: dict[int, Rule] = {id(r): r for r in bare}
        for hit in set(combined.findall(low)):
            triggered.update((id(r), r) for r in by_keyword[hit])
        for rule in triggered.values():
            found += _apply_rule(rule, text, 0)
        return found
    windows: dict[int, list[list[int]]] = {}
    rules: dict[int, Rule] = {}
    for m in combined.finditer(low):
        lo, hi = max(0, m.start() - WINDOW_BEFORE), min(len(text), m.end() + WINDOW_AFTER)
        for rule in by_keyword[m.group(0)]:
            rules[id(rule)] = rule
            spans = windows.setdefault(id(rule), [])
            if spans and lo <= spans[-1][1]:
                spans[-1][1] = max(hi, spans[-1][1])
            else:
                spans.append([lo, hi])
    for rule in bare:
        rules[id(rule)] = rule
        windows[id(rule)] = [[0, len(text)]]
    for rid, spans in windows.items():
        for lo, hi in spans:
            found += _apply_rule(rules[rid], text[lo:hi], lo)
    return found


def _structural_findings(text: str) -> list[Finding]:
    """URL userinfo passwords and password assignments; placeholders skipped."""
    found = []
    for m in URL_CRED.finditer(text):
        if not PLACEHOLDER.match(m.group(2)):
            found.append(Finding("url-credential", "probable", m.start(2), m.end(2), m.group(2)))
    for m in ASSIGN.finditer(text):
        if not PLACEHOLDER.match(m.group(2)):
            found.append(
                Finding("password-assignment", "probable", m.start(2), m.end(2), m.group(2))
            )
    return found


def _candidate_findings(text: str) -> list[Finding]:
    """High-entropy tokens for review: letters+digits, non-hex, entropy >= 3.4."""
    found = []
    for m in CANDIDATE.finditer(text):
        val = m.group(0)
        if HEXISH.fullmatch(val) or not re.search(r"[A-Za-z]", val) or not re.search(r"\d", val):
            continue
        if shannon(val) >= 3.4:
            found.append(Finding("entropy-token", "candidate", m.start(), m.end(), val))
    return found


def scan_text(text: str, candidates: bool = False) -> list[Finding]:
    """All findings in one text, best severity winning overlapping spans."""
    if len(text) < 8:
        return []
    low = text.lower()
    found = _rule_findings(text, low) + _structural_findings(text)
    if candidates:
        found += _candidate_findings(text)
    found.sort(key=lambda f: (SEVERITIES.index(f.severity), f.start, f.start - f.end))
    kept: list[Finding] = []
    for f in found:
        if not any(f.start < k.end and f.end > k.start for k in kept):
            kept.append(f)
    kept.sort(key=lambda f: f.start)
    return kept
