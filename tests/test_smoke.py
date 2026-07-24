"""Smoke tests for the package scaffold and the konpy.json line-limit regexes."""

import json
import re
from pathlib import Path

import sxr


def test_version() -> None:
    assert sxr.__version__


def _limit_pattern(convention_name: str) -> re.Pattern[str]:
    config = json.loads((Path(__file__).parent.parent / "konpy.json").read_text())
    convention = next(c for c in config["conventions"] if c["name"] == convention_name)
    return re.compile(convention["mustNot"]["matchContent"][0], re.MULTILINE)


def test_max_module_length_regex() -> None:
    pattern = _limit_pattern("max-module-length")
    assert not pattern.search("x = 1\n" * 300)
    assert pattern.search("x = 1\n" * 301)
    assert pattern.search("\n" * 300 + "x")
