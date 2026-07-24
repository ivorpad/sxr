"""Aggregate views: list, tools, stats, path, grep. Counts, not judgment."""

import json
import re
import sys
from collections import Counter

from sxr.model import Event, SessionRef
from sxr.providers.claude_code import INTERRUPT_MARKER
from sxr.util import day, human_num, human_size, tab_row


def _session_json(ref: SessionRef) -> dict:
    """List-view metadata for one session as a flat object."""
    return {
        "type": "session",
        "id": ref.id,
        "provider": ref.provider,
        "cwd": ref.cwd,
        "started": day(ref.started),
        "title": ref.title,
        "name": ref.name,
        "kind": ref.kind,
        "model": ref.model,
        "messages": ref.messages,
        "errors": ref.errors,
        "tokens": ref.tokens,
        "size_bytes": ref.size_bytes,
        "path": str(ref.path),
    }


def list_view(refs: list[SessionRef], json_out: bool, limit: int | None) -> int:
    """Sessions newest first with @N handles; exit 0 even when empty."""
    shown = refs if limit is None else refs[:limit]
    if json_out:
        for ref in shown:
            print(json.dumps(_session_json(ref), ensure_ascii=False))
        return 0
    codex = bool(refs and refs[0].provider == "codex")
    header = (
        ["# @", "id", "started"]
        + (["kind", "model/effort"] if codex else [])
        + ["msgs", "errs", "tokens", "size", "title"]
    )
    print(tab_row(*header))
    for n, ref in enumerate(shown, start=1):
        row = [f"@{n}", ref.short_id, day(ref.started)]
        if codex:
            row += [ref.kind, ref.model]
        row += [
            ref.messages,
            ref.errors,
            human_num(ref.tokens),
            human_size(ref.size_bytes),
            ref.label,
        ]
        print(tab_row(*row))
    if limit is not None and len(refs) > limit:
        print(f"# +{len(refs) - limit} more (raise -n)")
    return 0


def tools_view(events: list[Event], json_out: bool) -> int:
    """Per-tool call and error counts; Skill inputs come from input.skill."""
    calls: Counter[str] = Counter()
    fails: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    for event in events:
        if event.kind != "tool":
            continue
        calls[event.tool] += 1
        if event.tag == "err":
            fails[event.tool] += 1
        if event.tool == "Skill":
            line = event.raw.get("line", {})
            for block in line.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    skills[str(block.get("input", {}).get("skill", ""))] += 1
    if json_out:
        rows = {
            "type": "tools",
            "calls": dict(calls),
            "errors": dict(fails),
            "skill_inputs": dict(skills),
        }
        print(json.dumps(rows, ensure_ascii=False))
        return 0 if calls else 1
    print(tab_row("# tool", "calls", "errors"))
    for tool, count in calls.most_common():
        print(tab_row(tool, count, fails.get(tool, 0)))
    if skills:
        inputs = ", ".join(f"{name} ({n})" for name, n in skills.most_common())
        print(f"# Skill inputs: {inputs}")
    return 0 if calls else 1


def _stat_rows(ref: SessionRef, events: list[Event]) -> list[tuple[str, object]]:
    """Field/value rows derived from record properties only."""
    kinds = Counter(e.kind for e in events)
    ts = [e.ts for e in events if e.ts]
    rows: list[tuple[str, object]] = [
        ("provider", ref.provider),
        ("session", ref.id),
        ("file", str(ref.path)),
        ("size", human_size(ref.size_bytes)),
        ("started", day(ts[0]) if ts else ""),
        ("ended", day(ts[-1]) if ts else ""),
        ("model", ref.model),
        ("messages", ref.messages),
        ("errors", ref.errors),
        ("tokens", human_num(ref.tokens)),
    ]
    for key in ("gitBranch", "originator", "cli_version", "effort", "sidechain_records"):
        if ref.extra.get(key):
            rows.append((key, ref.extra[key]))
    for skill, n in sorted((ref.extra.get("attribution") or {}).items()):
        rows.append((f"attribution.{skill}", n))
    rows.append(("user.text_meta", sum(1 for e in events if e.role == "user" and e.tag == "meta")))
    rows.append(
        ("interruption_markers", sum(1 for e in events if e.text.startswith(INTERRUPT_MARKER)))
    )
    rows.extend((f"records.{kind}", n) for kind, n in kinds.most_common())
    return rows


def stats_view(ref: SessionRef, events: list[Event], json_out: bool) -> int:
    """The elevation view: one field/value row per derived count."""
    rows = _stat_rows(ref, events)
    if json_out:
        print(json.dumps({"type": "stats", **dict(rows)}, ensure_ascii=False))
        return 0
    print(tab_row("# field", "value"))
    for field, value in rows:
        print(tab_row(field, value))
    return 0


def path_view(paths: list) -> int:
    """Session file paths, main transcript first; feed straight to jq."""
    for path in paths:
        print(path)
    return 0


def grep_view(
    pattern: str, refs: list[SessionRef], parse, fixed: bool, count: bool, json_out: bool
) -> int:
    """Search event text across the scope; -c counts per session."""
    flags = re.IGNORECASE if pattern == pattern.lower() else 0
    needle = re.compile(re.escape(pattern) if fixed else pattern, flags)
    total = 0
    if count:
        print(tab_row("# session", "matches"))
    for ref in refs:
        hits = [e for e in parse(ref.path) if e.text and needle.search(e.text)]
        total += len(hits)
        if count:
            print(tab_row(ref.short_id, len(hits)))
            continue
        for event in hits:
            if json_out:
                print(json.dumps(event.raw.get("line", {}), ensure_ascii=False))
            else:
                from sxr.util import one_line

                print(
                    tab_row(
                        ref.short_id, f"#{event.seq:04d}", event.role, f'"{one_line(event.text)}"'
                    )
                )
    if total == 0 and not count:
        print(f"no matches for '{pattern}'", file=sys.stderr)
        return 1
    return 0
