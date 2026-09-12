"""Find credentials in JSON string values and rewrite only their source tokens."""

import json
import re
from dataclasses import dataclass

from sxr.secrets.detect import PLACEHOLDER, Finding, scan_text
from sxr.secrets.fingerprint import marker

DECODER = json.JSONDecoder()
KEY_SEPARATOR = re.compile(r"\s*:")
JSON_START = re.compile(r"[\[{]")
PASSWORD_FIELDS = frozenset({"password", "passwd", "pwd", "pgpassword", "mysql_pwd"})


@dataclass
class StringValue:
    """A decoded value and its quoted source span, with an adjacent property name."""

    start: int
    end: int
    text: str
    key: str = ""


@dataclass
class Replacement:
    """A source span replaced once, possibly containing several nested credentials."""

    start: int
    end: int
    text: str
    findings: list[Finding]


def _values(line):
    """Walk validated JSON tokens, retaining duplicate members and original offsets."""
    index, key, key_end = 0, "", 0
    while (start := line.find('"', index)) >= 0:
        text, end = DECODER.raw_decode(line, start)
        index = end
        if KEY_SEPARATOR.match(line, end):
            key, key_end = text, end
            continue
        context = key if key and line[key_end:start].strip() == ":" else ""
        yield StringValue(start, end, text, context)
        key = ""


def _findings(value, candidates=False):
    """Yield credential spans within this value, retaining structured field context."""
    if value.key.lower() in PASSWORD_FIELDS:
        if value.text and not PLACEHOLDER.match(value.text):
            yield Finding("password-assignment", "probable", 0, len(value.text), value.text)
        return
    if len(value.text) < 8:
        return
    prefix = f"{value.key} = " if value.key else ""
    for finding in scan_text(prefix + value.text, candidates):
        if finding.start >= len(prefix):
            yield Finding(
                finding.kind,
                finding.severity,
                finding.start - len(prefix),
                finding.end - len(prefix),
                finding.value,
            )


def _json_fragments(text):
    """Locate serialized objects/arrays in tool arguments or output, including wrappers."""
    if text.lstrip().startswith('"'):
        try:
            if isinstance(json.loads(text), str):
                yield 0, len(text)
                return
        except json.JSONDecodeError:
            pass
    index = 0
    while match := JSON_START.search(text, index):
        start = match.start()
        try:
            _, end = DECODER.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        yield start, end
        index = end


def _redact_value(value, candidates=False, redact=True):
    """Prefer structured redaction to partial plaintext matches inside serialized JSON."""
    changes = []
    if value.key.lower() not in PASSWORD_FIELDS:
        for start, end in _json_fragments(value.text):
            text, findings = _clean_json(value.text[start:end], candidates, redact)
            changes.append(Replacement(start, end, text, findings))
    for finding in _findings(value, candidates):
        start, end = finding.start, finding.end
        if any(change.start <= start and end <= change.end for change in changes):
            continue
        # A credential enclosing JSON, such as a private-key body, wins in full.
        changes = [change for change in changes if end <= change.start or start >= change.end]
        text = marker(finding.kind, finding.value) if redact else finding.value
        changes.append(Replacement(start, end, text, [finding]))
    parts, findings, offset = [], [], 0
    for change in sorted(changes, key=lambda c: c.start):
        parts.extend((value.text[offset : change.start], change.text))
        offset = change.end
        findings.extend(change.findings)
    parts.append(value.text[offset:])
    return "".join(parts), findings


def _clean_json(line, candidates=False, redact=True):
    """Redact a JSON document without discarding duplicate fields or reformatting tokens."""
    json.loads(line)
    parts, findings, offset = [], [], 0
    for value in _values(line):
        changed, found = _redact_value(value, candidates, redact)
        if not found:
            continue
        findings.extend(found)
        parts.extend((line[offset : value.start], json.dumps(changed, ensure_ascii=True)))
        offset = value.end
    if not findings:
        return line, []
    parts.append(line[offset:])
    updated = "".join(parts)
    json.loads(updated)
    return updated, findings


def scan_line(raw: bytes, candidates: bool = False) -> list[Finding]:
    """Audit decoded stored values using the cleaner's structured span selection."""
    try:
        return _clean_json(raw.decode("utf-8"), candidates, redact=False)[1]
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []


def clean_line(raw: bytes) -> tuple[bytes, int, list[str]]:
    """Redact decoded values while preserving keys, other tokens and line endings.

    Invalid UTF-8 or JSON passes through unchanged. Substitutions use detected
    spans in the original decoded strings, so they cannot rewrite a marker,
    change an unrelated field, or leave a longer value's suffix exposed.
    """
    try:
        line = raw.decode("utf-8")
        updated, findings = _clean_json(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw, 0, []
    return (
        updated.encode("utf-8"),
        len(findings),
        list(dict.fromkeys(f.kind for f in findings)),
    )
