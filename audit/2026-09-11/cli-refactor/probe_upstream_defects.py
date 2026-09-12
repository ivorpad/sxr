"""Measure prompts behavior across three trees: 48b11c6c, origin/HEAD, and this one.

Answers the audit questions that need running code rather than reading: whether
upstream's catalog path honors --budget, what unit -n takes there, whether -n in
JSON ever limited distinct physical records, and how each tree exits on negative
limits. Read-only: each ref is materialized with `git archive` into a temp
directory outside the repository and removed afterwards.

    uv run python probe_upstream_defects.py --output evidence-M/upstream-defects.json
"""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "48b11c6cf08200de363e108924e42fdbc52d83e8"
PUBLISHED = "8f93114f8a1712cc7f02f2cfb91cf10d3040bb04"


def materialize(ref: str, directory: Path) -> Path:
    """Extract one ref's tree into directory; returns its src path."""
    target = directory / ref[:8]
    target.mkdir(parents=True)
    archive = target / "tree.tar"
    with archive.open("wb") as handle:
        subprocess.run(["git", "-C", str(REPO), "archive", ref], stdout=handle, check=True)
    subprocess.run(["tar", "-x", "-C", str(target), "-f", str(archive)], check=True)
    return target / "src"


def corpus(home: Path) -> None:
    """A Codex scope whose newest session is a subagent and whose next is empty.

    The oldest session carries three human prompts in three physical records, so
    -n's unit is observable, and one long prompt so a budget is observable.
    """

    def human(text: str) -> dict:
        return {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["user.text"]},
        }

    def write(day: int, ident: str, records: list[dict], source: str | None = None) -> None:
        payload = {"id": ident, "cwd": "/w", "timestamp": f"2026-09-{day:02d}T12:00:00Z"}
        if source:
            payload["source"] = source
        folder = home / "sessions" / "2026" / "09" / f"{day:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        head = {"timestamp": payload["timestamp"], "type": "session_meta", "payload": payload}
        items = [
            {
                "timestamp": f"2026-09-{day:02d}T12:0{index}:00Z",
                "type": "response_item",
                "payload": record,
            }
            for index, record in enumerate(records, start=1)
        ]
        name = f"rollout-2026-09-{day:02d}T12-00-00-{ident}.jsonl"
        (folder / name).write_text("\n".join(json.dumps(r) for r in [head, *items]) + "\n")

    write(
        1,
        "01999991-aaaa-7000-8000-00000000000a",
        [
            human("first human ask"),
            human("second human ask " + "x" * 400),
            human("third human ask"),
        ],
    )
    write(2, "01999992-bbbb-7000-8000-00000000000b", [])
    write(3, "01999993-cccc-7000-8000-00000000000c", [human("subagent ask")], source="subagent")


def run(source: Path, home: Path, cache: Path, *args: str) -> dict:
    """One invocation against one tree, in its own Codex profile and cache."""
    environment = dict(
        os.environ,
        PYTHONPATH=str(source),
        CODEX_HOME=str(home),
        SXR_CACHE_DIR=str(cache),
    )
    done = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", "from sxr import main; main()", *args],
        capture_output=True,
        text=True,
        env=environment,
    )
    return {
        "args": list(args),
        "exit": done.returncode,
        "stdout_lines": done.stdout.splitlines(),
        "stderr_lines": done.stderr.splitlines(),
    }


CASES = [
    ("bare", ["--codex", "prompts", "--path", "/w"]),
    ("bare-json", ["--codex", "prompts", "--path", "/w", "--json"]),
    ("bare-json-n1", ["--codex", "prompts", "--path", "/w", "--json", "-n", "1"]),
    ("bare-n1", ["--codex", "prompts", "--path", "/w", "-n", "1"]),
    ("bare-budget-0", ["--codex", "prompts", "--path", "/w", "--budget", "0"]),
    ("bare-budget-50", ["--codex", "prompts", "--path", "/w", "--budget", "50"]),
    ("explicit-json-n1", ["--codex", "prompts", "@3", "--path", "/w", "--json", "-n", "1"]),
    ("explicit-budget-50", ["--codex", "prompts", "@3", "--path", "/w", "--budget", "50"]),
    ("negative-limit", ["--codex", "prompts", "--path", "/w", "-n", "-1"]),
    ("negative-budget", ["--codex", "prompts", "--path", "/w", "--budget", "-5"]),
    ("errors-compact", ["--codex", "errors", "--path", "/w", "--compact"]),
    ("help", ["prompts", "--help"]),
]


def main() -> int:
    """Run every case against every tree and write one JSON record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the JSON")
    args = parser.parse_args()

    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="sxr-defects-") as directory:
        base = Path(directory)
        home = base / "codex"
        corpus(home)
        trees = {
            "base-48b11c6c": materialize(BASE, base),
            "published-8f93114": materialize(PUBLISHED, base),
            "this-tree": REPO / "src",
        }
        for name, source in trees.items():
            results[name] = {}
            for label, argv in CASES:
                cache = base / f"cache-{name}-{label}"
                results[name][label] = run(source, home, cache, *argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")

    for label, _argv in CASES:
        print(f"\n### {label}")
        for name in trees:
            case = results[name][label]
            out = case["stdout_lines"]
            print(f"  {name:20} exit={case['exit']}  stdout={len(out)} lines")
            for line in out[:4]:
                print(f"      | {line[:110]}")
            for line in case["stderr_lines"][:2]:
                print(f"      ! {line[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
