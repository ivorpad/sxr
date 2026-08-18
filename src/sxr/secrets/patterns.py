"""Vendored gitleaks ruleset (MIT, github.com/gitleaks/gitleaks) for Python re.

gitleaks.toml ships verbatim from upstream; updating coverage means
replacing that file, not editing regexes here. Rules whose regex Python's
re cannot compile are skipped at load and counted in RuleSet.skipped.
This module only loads and compiles: each Rule carries its keywords,
entropy threshold, secretGroup, and allowlists for detect.py to apply.
"""

import re
import tomllib
import warnings
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

GENERIC_RULE_IDS = frozenset({"generic-api-key", "curl-auth-user"})


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
            try:
                regexes.append(re.compile(rx))
            except re.error:
                continue
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
    skipped: list[str] = []
    for rec in cfg.get("rules", []):
        if "regex" not in rec:
            continue  # path-only rules; sxr scans transcripts, not file trees
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                regex = re.compile(rec["regex"])
        except re.error:
            skipped.append(rec["id"])
            continue
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
        skipped=tuple(skipped),
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
    combined = re.compile("|".join(re.escape(k) for k in keywords))
    return combined, {k: tuple(v) for k, v in by_keyword.items()}, tuple(bare)
