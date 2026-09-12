"""Run the same `prompts` invocations against three trees: HEAD, this tree, upstream.

Read-only with respect to git: the HEAD and origin/HEAD trees are materialized
with `git archive` into temp directories, so no worktree, checkout or index
operation happens. Dependencies are identical across the three (`uv.lock` differs
only in the version line), so each tree is imported by prepending its `src` to
`sys.path` in a subprocess.

    uv run python probe_prompts_three_way.py --output evidence-06/prompts-three-way.log
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

CASES = [
    ("bare", []),
    ("bare --json", ["--json"]),
    ("bare --all", ["--all"]),
    ("@3 (2 human prompts, 1 very long)", ["@3"]),
    ("@3 --all", ["@3", "--all"]),
    ("@3 --json", ["@3", "--json"]),
    ("@3 --budget 0", ["@3", "--budget", "0"]),
    ("@2 (context only)", ["@2"]),
    ("@1 (subagent)", ["@1"]),
    ("@3:@4 (range)", ["@3:@4"]),
    ("--latest", ["--latest"]),
    ("-n 0 --budget 0 (the old workaround)", ["-n", "0", "--budget", "0"]),
]

LONG = "please rebuild the release pipeline " * 40

RUNNER = """
import io, json, os, sys
from contextlib import redirect_stderr, redirect_stdout
sys.path.insert(0, sys.argv[1])
from typer.testing import CliRunner
from sxr.cli import app
args = json.loads(sys.argv[2])
out, err = io.StringIO(), io.StringIO()
with redirect_stdout(out), redirect_stderr(err):
    result = CliRunner().invoke(app, args)
stderr = result.stderr if result.stderr_bytes is not None else err.getvalue()
print(json.dumps({"exit": result.exit_code, "out": result.stdout, "err": stderr}))
"""


def codex_corpus(root: Path) -> None:
    """Two human sessions, one newer empty session, one newer subagent session."""

    def item(seq: int, payload: dict) -> dict:
        return dict(
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z", type="response_item", payload=payload
        )

    def human(text: str) -> dict:
        return dict(
            type="message",
            role="user",
            content=[dict(type="input_text", text=text)],
            internal_chat_message_metadata_passthrough=dict(content_item_kinds=["user.text"]),
        )

    def injected(text: str) -> dict:
        return dict(
            type="message",
            role="user",
            content=[dict(type="input_text", text=text)],
            internal_chat_message_metadata_passthrough=dict(
                content_item_kinds=["environment_context"]
            ),
        )

    def session(day: int, ident: str, records: list[dict], source: str | None = None) -> None:
        payload = dict(id=ident, cwd="/w", timestamp=f"2026-09-{day:02d}T12:00:00Z")
        if source:
            payload["source"] = source
        directory = root / "sessions" / "2026" / "09" / f"{day:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"rollout-2026-09-{day:02d}T12-00-00-{ident}.jsonl"
        head = dict(timestamp=payload["timestamp"], type="session_meta", payload=payload)
        path.write_text("\n".join(json.dumps(r) for r in [head, *records]) + "\n")

    session(
        1,
        "01999991-aaaa-7000-8000-00000000000a",
        [item(1, human("first human ask alpha")), item(2, injected("injected-context alpha"))],
    )
    session(
        2,
        "01999992-bbbb-7000-8000-00000000000b",
        [
            item(1, human(LONG)),
            item(2, injected("injected-context beta")),
            item(3, human("second human ask beta")),
        ],
    )
    session(3, "01999993-cccc-7000-8000-00000000000c", [item(1, injected("only context"))])
    session(
        4,
        "01999994-dddd-7000-8000-00000000000d",
        [item(1, human("subagent ask"))],
        source="subagent",
    )


def tree(ref: str, directory: Path) -> Path:
    """Materialize one git ref with `git archive`; never touches HEAD or the index."""
    target = directory / ref.replace("/", "-")
    target.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", ref], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(target)], input=archive, check=True)
    return target / "src"


def run(src: Path, args: list[str], root: Path, cache: Path) -> dict:
    """One invocation in one tree, in its own cache root."""
    environment = dict(os.environ)
    environment.update(CODEX_HOME=str(root), SXR_CACHE_DIR=str(cache))
    environment.pop("SXR_NO_CACHE", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            RUNNER,
            str(src),
            json.dumps(["--codex", "prompts", *args, "--path", "/w"]),
        ],
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        return {"exit": "CRASH", "out": "", "err": completed.stderr.strip()[-400:]}
    return json.loads(completed.stdout)


def summarize(result: dict) -> str:
    """A one-line shape of an invocation's result, for a side-by-side table."""
    if result["exit"] == "CRASH":
        return "crash"
    body = result["out"]
    parts = [f"exit={result['exit']}"]
    if not body.strip():
        parts.append("no stdout")
    else:
        rows = [line for line in body.splitlines() if line.strip()]
        parts.append(f"{len(rows)} stdout lines")
        if "prompt_session" in body:
            parts.append("session catalog JSON")
        elif body.lstrip().startswith("{"):
            parts.append("raw records")
        elif any(row.startswith("# @") or "\tstarted\t" in row for row in rows):
            parts.append("session table")
        if any(
            m in body for m in ("first human ask alpha", "second human ask beta", "subagent ask")
        ):
            parts.append("prompt text")
        if "injected-context" in body:
            parts.append("+injected")
        if "[+" in body and "chars]" in body:
            parts.append("TRIMMED")
        if LONG.strip() in body.replace("\n", " ") or LONG[:200] in body:
            parts.append("long prompt whole")
    if "no human prompts" in result["err"]:
        parts.append("stderr: no human prompts")
    if "needs a session" in result["err"] or "cannot be combined" in result["err"]:
        parts.append("stderr: usage error")
    if "# prompts:" in result["err"]:
        parts.append("stderr: navigation")
    if "# session @" in body:
        parts.append("per-session banner")
    return ", ".join(parts)


def main() -> int:
    """Write the three-way table and the raw results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the log")
    args = parser.parse_args()

    lines = [
        "Three-way `prompts` comparison over one synthetic Codex corpus",
        "",
        "corpus: @1 subagent (newer), @2 context-only (newer), @3 two human prompts",
        "        (one very long), @4 one human prompt. Handles are newest-first.",
        "",
    ]
    raw: dict[str, dict[str, dict]] = {}
    with tempfile.TemporaryDirectory(prefix="sxr-3way-") as directory:
        base = Path(directory)
        trees = {
            "HEAD 48b11c6c": tree("HEAD", base / "trees"),
            "this tree": REPO / "src",
            "upstream 8f93114": tree("origin/HEAD", base / "trees"),
        }
        corpus = base / "corpus"
        codex_corpus(corpus)
        for label, argv in CASES:
            raw[label] = {}
            lines.append(f"$ sxr --codex prompts {' '.join(argv)} --path /w")
            for name, src in trees.items():
                cache = base / "cache" / f"{name}-{label}".replace(" ", "-").replace("/", "-")
                cache.mkdir(parents=True, exist_ok=True)
                result = run(src, argv, corpus, cache)
                raw[label][name] = result
                lines.append(f"    {name:18s} {summarize(result)}")
            lines.append("")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    args.output.with_suffix(".json").write_text(json.dumps(raw, indent=2) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
