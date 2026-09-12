"""Vendored gitleaks ruleset (MIT, github.com/gitleaks/gitleaks) for Python re.

gitleaks.toml ships verbatim from upstream; updating coverage means
replacing that file, not editing regexes here. Go regex syntax is translated
before compilation; unsupported rules stop the scan instead of losing coverage.
This module only loads and compiles: each Rule carries its keywords,
entropy threshold, secretGroup, and allowlists for detect.py to apply.
"""

import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from sxr.secrets.rule_regex import compile_rule

GENERIC_RULE_IDS = frozenset({"generic-api-key", "curl-auth-user", "curl-auth-header"})


@dataclass(frozen=True)
class Rule:
    """One compiled gitleaks rule."""

    id: str
    regex: re.Pattern
    keywords: tuple[str, ...]
    entropy: float | None
    secret_group: int
    allow_regexes: tuple[re.Pattern, ...]
    allow_stopwords: tuple[str, ...]


@dataclass(frozen=True)
class RuleSet:
    """All usable rules plus the global allowlist."""

    rules: tuple[Rule, ...]
    allow_regexes: tuple[re.Pattern, ...]
    allow_stopwords: tuple[str, ...]
    skipped: tuple[str, ...]


def _allow_parts(entries) -> tuple[list[re.Pattern], list[str]]:
    """Compiled regexes and stopwords from allowlist entries, rule-level
    or the top-level global allowlist.

    Path-only entries are ignored: sxr scans transcripts, not file trees.
    """
    regexes: list[re.Pattern] = []
    stopwords: list[str] = []
    for entry in entries or []:
        for rx in entry.get("regexes", []):
            regexes.append(compile_rule(rx))
        stopwords.extend(str(s).lower() for s in entry.get("stopwords", []))
    return regexes, stopwords


@lru_cache(maxsize=1)
def load_rules() -> RuleSet:
    """Parse and compile the vendored ruleset once per process."""
    raw = resources.files("sxr.secrets").joinpath("gitleaks.toml").read_bytes()
    cfg = tomllib.loads(raw.decode("utf-8"))
    top = cfg.get("allowlist", {})
    global_regexes, global_stopwords = _allow_parts([top])
    rules: list[Rule] = []
    for rec in cfg.get("rules", []):
        if "regex" not in rec:
            continue  # path-only rules; sxr scans transcripts, not file trees
        try:
            regex = compile_rule(rec["regex"])
        except (re.error, ValueError) as exc:
            raise ValueError(f"cannot compile secret rule {rec['id']}: {exc}") from exc
        allow_regexes, allow_stopwords = _allow_parts(rec.get("allowlists"))
        rules.append(
            Rule(
                id=rec["id"],
                regex=regex,
                keywords=tuple(str(k).lower() for k in rec.get("keywords", [])),
                entropy=rec.get("entropy"),
                secret_group=int(rec.get("secretGroup", 0)),
                allow_regexes=tuple(allow_regexes),
                allow_stopwords=tuple(allow_stopwords),
            )
        )
    return RuleSet(
        rules=tuple(rules),
        allow_regexes=tuple(global_regexes),
        allow_stopwords=tuple(global_stopwords),
        skipped=(),
    )


@lru_cache(maxsize=1)
def keyword_index() -> tuple[re.Pattern, dict[str, tuple[Rule, ...]], tuple[Rule, ...]]:
    """One combined keyword scan instead of per-rule substring loops.

    Returns (combined regex, keyword -> rules, rules with no keywords).
    The regex matches longest keyword first, and each long keyword's rule
    list already includes the rules of every keyword it contains, so a
    keyword swallowed by a longer match still triggers its rules.
    """
    ruleset = load_rules()
    by_keyword: dict[str, list[Rule]] = {}
    bare: list[Rule] = []
    for rule in ruleset.rules:
        if not rule.keywords:
            bare.append(rule)
        for k in rule.keywords:
            by_keyword.setdefault(k, []).append(rule)
    keywords = sorted(by_keyword, key=len, reverse=True)
    for k in keywords:  # containment: a hit on k must also trigger its substrings
        for sub in keywords:
            if sub != k and sub in k:
                by_keyword[k].extend(by_keyword[sub])
    combined = _keyword_regex(keywords)
    return combined, {k: tuple(v) for k, v in by_keyword.items()}, tuple(bare)


def _keyword_regex(keywords):
    """Share prefix branches so each character does not try every provider keyword."""
    trie = {}
    for keyword in keywords:
        node = trie
        for char in keyword:
            node = node.setdefault(char, {})
        node[""] = {}

    def branch(node):
        choices = [re.escape(char) + branch(child) for char, child in node.items() if char]
        if "" in node:
            choices.append("")  # Prefer the longer keyword when one contains another.
        return choices[0] if len(choices) == 1 else "(?:" + "|".join(choices) + ")"

    return re.compile(branch(trie) if trie else r"(?!)")
