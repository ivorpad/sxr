"""Pin down what -n counts in each tree, and how many --help surfaces upstream changed.

Two questions the first probe left open. A corpus with two human sessions makes
the unit of `prompts -n 1` observable: a record limit truncates one session's
prompts, a row limit truncates the list of sessions. And every command's --help
is captured from both refs so the claim that upstream changed exactly two
surfaces can be counted rather than asserted.

    uv run python probe_limit_unit.py --output evidence-M/limit-unit.json
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
SURFACES = [
    [],
    ["cmds"],
    ["errors"],
    ["find"],
    ["grep"],
    ["index"],
    ["init"],
    ["list"],
    ["path"],
    ["prompts"],
    ["secrets"],
    ["secrets", "audit"],
    ["secrets", "clean"],
    ["serve"],
    ["show"],
    ["skills"],
    ["stats"],
    ["tools"],
]


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
    """Two human sessions plus an empty and a background one, newest first."""

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

    write(1, "01999991-aaaa-7000-8000-00000000000a", [human("older one"), human("older two")])
    write(2, "01999992-bbbb-7000-8000-00000000000b", [human("newer one"), human("newer two")])
    write(3, "01999993-cccc-7000-8000-00000000000c", [])
    write(4, "01999994-dddd-7000-8000-00000000000d", [human("bg ask")], source="subagent")


def run(source: Path, *args: str, home: Path | None = None, cache: Path) -> dict:
    """One invocation against one tree."""
    environment = dict(os.environ, PYTHONPATH=str(source), SXR_CACHE_DIR=str(cache))
    if home:
        environment["CODEX_HOME"] = str(home)
    done = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", "from sxr import main; main()", *args],
        capture_output=True,
        text=True,
        env=environment,
    )
    return {"exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


CASES = [
    ("bare", ["--codex", "prompts", "--path", "/w"]),
    ("bare-n1", ["--codex", "prompts", "--path", "/w", "-n", "1"]),
    ("bare-n2", ["--codex", "prompts", "--path", "/w", "-n", "2"]),
    ("bare-json-n1", ["--codex", "prompts", "--path", "/w", "--json", "-n", "1"]),
    ("show-negative-budget", ["--codex", "show", "--path", "/w", "--budget", "-5"]),
    ("show-negative-limit", ["--codex", "show", "--path", "/w", "-n", "-1"]),
    ("tail-zero", ["--codex", "show", "--path", "/w", "--tail", "0"]),
]


def main() -> int:
    """Run the limit cases, then diff every --help surface between the two refs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the JSON")
    args = parser.parse_args()

    report: dict[str, dict] = {"limit_unit": {}, "help_surfaces": {}}
    with tempfile.TemporaryDirectory(prefix="sxr-limit-") as directory:
        base = Path(directory)
        home = base / "codex"
        corpus(home)
        trees = {
            "base-48b11c6c": materialize(BASE, base),
            "published-8f93114": materialize(PUBLISHED, base),
            "this-tree": REPO / "src",
        }
        for label, argv in CASES:
            report["limit_unit"][label] = {}
            for name, source in trees.items():
                cache = base / f"cache-{name}-{label}"
                report["limit_unit"][label][name] = run(source, *argv, home=home, cache=cache)
        for index, surface in enumerate(SURFACES):
            label = " ".join(["sxr", *surface]) or "sxr"
            texts = {}
            for name in ("base-48b11c6c", "published-8f93114", "this-tree"):
                cache = base / f"help-{name}-{index}"
                texts[name] = run(trees[name], *surface, "--help", cache=cache)["stdout"]
            report["help_surfaces"][label] = {
                "base_published_identical": texts["base-48b11c6c"] == texts["published-8f93114"],
                "base_lines": len(texts["base-48b11c6c"].splitlines()),
                "published_lines": len(texts["published-8f93114"].splitlines()),
                "this_tree_lines": len(texts["this-tree"].splitlines()),
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")

    for label in report["limit_unit"]:
        print(f"\n### {label}")
        for name, case in report["limit_unit"][label].items():
            lines = case["stdout"].splitlines()
            print(f"  {name:20} exit={case['exit']}  {len(lines)} stdout lines")
            for line in lines[:6]:
                print(f"      | {line[:100]}")
            for line in case["stderr"].splitlines()[:1]:
                print(f"      ! {line[:100]}")
    changed = [k for k, v in report["help_surfaces"].items() if not v["base_published_identical"]]
    print(f"\n### help surfaces: {len(report['help_surfaces'])} compared")
    print(f"  changed between the two refs ({len(changed)}): {', '.join(changed) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
