"""Run this tree's human-prompt predicate and upstream's over the same records.

Read-only. Upstream's `prompt_selection.py` is materialized from
`origin/HEAD` with `git show` into a temp file and imported from there; the
repository, HEAD and working tree are never touched.

    uv run python probe_prompt_predicates.py --output evidence-06/prompt-predicates.log
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = "origin/HEAD"


def load_upstream(directory: Path):
    """Import origin/HEAD's prompt_selection module without checking anything out."""
    source = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{UPSTREAM}:src/sxr/prompt_selection.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    path = directory / "upstream_prompt_selection.py"
    path.write_text(source)
    # Upstream's module imports navigation.scope_command, which this tree does not
    # have -- itself a sign of the coupling. Shim it in memory only; no file changes.
    import sxr.navigation

    if not hasattr(sxr.navigation, "scope_command"):
        sxr.navigation.scope_command = lambda ref, verb, *args: ""
    spec = importlib.util.spec_from_file_location("upstream_prompt_selection", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases() -> list[tuple[str, str, dict, str]]:
    """(label, event kind, record, session prompt kind) for one record each.

    The predicate's `kind` argument is the session-wide prompt kind, so it is
    passed separately from the event's own kind; that is the only way the
    `event.kind != kind` rejection gets exercised.
    """

    def codex(kinds) -> dict:
        payload = {"type": "message", "role": "user"}
        if kinds is not None:
            payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
        return {"type": "response_item", "payload": payload}

    return [
        # Claude shapes
        ("claude plain user text", "text", {"type": "user", "message": {"role": "user"}}, "text"),
        ("claude isMeta", "text", {"type": "user", "isMeta": True}, "text"),
        ("claude isCompactSummary", "text", {"type": "user", "isCompactSummary": True}, "text"),
        ("claude isMeta false", "text", {"type": "user", "isMeta": False}, "text"),
        ("claude tool_result in a text session", "result", {"type": "user", "message": {}}, "text"),
        # Codex content_item_kinds
        ("codex user.text", "user_message", codex(["user.text"]), "user_message"),
        ("codex user.image", "user_message", codex(["user.image"]), "user_message"),
        (
            "codex environment_context",
            "user_message",
            codex(["environment_context"]),
            "user_message",
        ),
        ("codex user_instructions", "user_message", codex(["user_instructions"]), "user_message"),
        ("codex hooks context", "user_message", codex(["hooks.session_start"]), "user_message"),
        ("codex tool output", "user_message", codex(["tool.output"]), "user_message"),
        (
            "codex mixed user first",
            "user_message",
            codex(["user.text", "environment_context"]),
            "user_message",
        ),
        (
            "codex mixed user last",
            "user_message",
            codex(["environment_context", "user.text"]),
            "user_message",
        ),
        ("codex empty kinds list", "user_message", codex([]), "user_message"),
        ("codex kinds all non-string", "user_message", codex([123, None]), "user_message"),
        ("codex kinds mixed types", "user_message", codex([123, "user.text"]), "user_message"),
        ("codex kinds not a list", "user_message", codex("user.text"), "user_message"),
        ("codex kinds is None", "user_message", codex(None), "user_message"),
        (
            "codex unlabelled legacy",
            "user_message",
            {"type": "response_item", "payload": {}},
            "user_message",
        ),
        ("codex no payload at all", "user_message", {"type": "response_item"}, "user_message"),
        (
            "codex user.text but isMeta",
            "user_message",
            {**codex(["user.text"]), "isMeta": True},
            "user_message",
        ),
        (
            "codex text record in a user_message session",
            "text",
            codex(["user.text"]),
            "user_message",
        ),
        ("empty record", "text", {}, "text"),
    ]


def main() -> int:
    """Compare both predicates case by case and report any divergence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Where to write the log")
    args = parser.parse_args()

    sys.path.insert(0, str(REPO / "src"))
    from sxr.model import Event
    from sxr.views_prompts import human_prompt as mine

    lines = [
        "Differential probe: this tree's human_prompt vs origin/HEAD's _prompt_record",
        f"repo: {REPO}",
        f"upstream ref: {UPSTREAM} = "
        + subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", UPSTREAM], capture_output=True, text=True
        ).stdout.strip(),
        "",
        f"{'case':40s} {'event.kind':13s} {'session':13s} {'mine':6s} {'up':6s} verdict",
        "-" * 96,
    ]
    with tempfile.TemporaryDirectory(prefix="sxr-upstream-") as directory:
        upstream = load_upstream(Path(directory)).__dict__["_prompt_record"]
        disagreements = []
        for label, kind, record, prompt_kind in cases():
            event = Event(1, "2026-09-01T12:00:00Z", "user", kind, "text", raw={"line": record})
            a, b = mine(event, prompt_kind), upstream(event, prompt_kind)
            verdict = "same" if a == b else "DIVERGES"
            if a != b:
                disagreements.append((label, a, b))
            lines.append(
                f"{label:40s} {kind:13s} {prompt_kind:13s} {str(a):6s} {str(b):6s} {verdict}"
            )

    lines += ["", f"cases: {len(cases())}", f"divergences: {len(disagreements)}"]
    for label, a, b in disagreements:
        lines.append(f"  {label}: mine={a} upstream={b}")
    if not disagreements:
        lines.append("  none: the two predicates agree on every shape probed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps({"cases": len(cases()), "divergences": len(disagreements)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
