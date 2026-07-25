"""Claude Code provider: locate sessions by cwd and parse JSONL records.

Sessions live at ~/.claude/projects/<flattened-cwd>/<session-uuid>.jsonl.
Every extracted value is a property already present in the records; nothing
here classifies or interprets content.
"""

import json
import os
from pathlib import Path
from typing import Any

from sxr.model import Event, SessionRef

INTERRUPT_MARKER = "[Request interrupted by user"


def projects_dir() -> Path:
    """Base directory holding one flattened-cwd directory per project."""
    root = os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")
    return Path(root).expanduser() / "projects"


def flatten_cwd(cwd: str) -> str:
    """Mirror Claude Code's lossy path flattening: `/` and `.` become `-`."""
    return "".join("-" if ch in "/." else ch for ch in cwd)


def _iter_records(path: Path):
    """Yield (seq, record) for each parseable JSONL line, 1-based."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for seq, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield seq, json.loads(line)
            except json.JSONDecodeError:
                continue


def _block_events(seq: int, ts: str, role: str, blocks: list[Any], meta: bool) -> list[Event]:
    """Events for the content blocks of one user/assistant record."""
    events: list[Event] = []
    tag = "meta" if meta else ""
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        if btype == "text":
            events.append(Event(seq, ts, role, "text", block.get("text", ""), tag=tag))
        elif btype == "thinking":
            events.append(Event(seq, ts, role, "thinking", block.get("thinking", "")))
        elif btype == "tool_use":
            events.append(
                Event(
                    seq,
                    ts,
                    role,
                    "tool",
                    _tool_arg(block.get("input", {})),
                    tool=block.get("name", ""),
                    raw={"id": block.get("id", "")},
                )
            )
        elif btype == "tool_result":
            events.append(
                Event(
                    seq,
                    ts,
                    role,
                    "result",
                    _result_text(block.get("content")),
                    is_error=bool(block.get("is_error")),
                    raw={"tool_use_id": block.get("tool_use_id", "")},
                )
            )
        else:
            events.append(Event(seq, ts, role, btype, json.dumps(block, ensure_ascii=False)))
    return events


def _tool_arg(tool_input: dict[str, Any]) -> str:
    """One-line argument summary straight from the tool_use input properties."""
    for key in ("command", "file_path", "skill", "pattern", "prompt", "url"):
        if key in tool_input:
            return str(tool_input[key])
    return json.dumps(tool_input, ensure_ascii=False)


def _result_text(content: Any) -> str:
    """Text of a tool_result block; content is a string or a block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def _record_events(seq: int, rec: dict[str, Any]) -> list[Event]:
    """Events for one record; unknown types survive with kind = their type."""
    rtype = rec.get("type", "")
    ts = rec.get("timestamp", "")
    if rtype in ("user", "assistant"):
        role = "user" if rtype == "user" else "asst"
        content = rec.get("message", {}).get("content", "")
        if isinstance(content, str):
            tag = "meta" if rec.get("isMeta") else ""
            tag = "compact" if rec.get("isCompactSummary") else tag
            return [Event(seq, ts, role, "text", content, tag=tag)]
        events = _block_events(seq, ts, role, content, bool(rec.get("isMeta")))
        denial = rec.get("toolDenialKind", "")
        for event in events:
            if denial and event.kind == "result":
                event.tag = denial
        return events or [Event(seq, ts, role, rtype)]
    if rtype == "system":
        kind = f"system.{rec.get('subtype', '')}"
        return [Event(seq, ts, "sys", kind, rec.get("content", ""))]
    if rtype == "attachment":
        att = rec.get("attachment", {})
        kind = f"attachment.{att.get('type', '')}"
        return [Event(seq, ts, "attach", kind, str(att.get("content", "")))]
    text = (
        rec.get("aiTitle")
        or rec.get("customTitle")
        or rec.get("agentName")
        or rec.get("lastPrompt")
        or rec.get("mode")
        or rec.get("permissionMode")
        or ""
    )
    return [Event(seq, ts, "meta", rtype, str(text))]


def parse(path: Path) -> list[Event]:
    """All events of a session file, with tool calls annotated ok/err."""
    events: list[Event] = []
    for seq, rec in _iter_records(path):
        made = _record_events(seq, rec)
        for event in made:
            event.raw["line"] = rec
        events.extend(made)
    _pair_tools(events)
    return events


def _pair_tools(events: list[Event]) -> None:
    """Tag each tool event ok/err from its paired tool_result's is_error."""
    tools = {e.raw.get("id"): e for e in events if e.kind == "tool"}
    for event in events:
        if event.kind != "result":
            continue
        call = tools.get(event.raw.get("tool_use_id"))
        if call is not None:
            event.tool = call.tool
            call.tag = "err" if event.is_error else "ok"


def _summarize(path: Path) -> SessionRef:
    """List-view metadata for one session file, from record properties."""
    ref = SessionRef("claude", path.stem, path, size_bytes=path.stat().st_size)
    for _seq, rec in _iter_records(path):
        rtype = rec.get("type", "")
        ts = rec.get("timestamp", "")
        if ts and not ref.started:
            ref.started = ts
        if rec.get("isSidechain"):
            ref.extra["sidechain_records"] = ref.extra.get("sidechain_records", 0) + 1
        skill = rec.get("attributionSkill")
        if skill:
            counts = ref.extra.setdefault("attribution", {})
            counts[skill] = counts.get(skill, 0) + 1
        if rtype == "assistant":
            ref.messages += 1
            msg = rec.get("message", {})
            ref.model = msg.get("model", ref.model)
            ref.extra["effort"] = rec.get("effort", ref.extra.get("effort", ""))
            ref.tokens += int((msg.get("usage") or {}).get("output_tokens") or 0)
        elif rtype == "user":
            ref.messages += 1
            ref.cwd = rec.get("cwd", ref.cwd)
            ref.extra.setdefault("gitBranch", rec.get("gitBranch", ""))
            ref.errors += _error_blocks(rec)
        elif rtype == "ai-title":
            ref.title = rec.get("aiTitle", ref.title)
        elif rtype == "custom-title":
            ref.name = rec.get("customTitle", ref.name)
        if rec.get("isApiErrorMessage"):
            ref.errors += 1
        if rtype == "user" and not rec.get("isMeta") and "first_user" not in ref.extra:
            text = _user_text(rec)
            if text:
                ref.extra["first_user"] = text
    if not ref.title:
        ref.title = ref.extra.get("first_user", "")
    return ref


def _user_text(rec: dict[str, Any]) -> str:
    """The typed text of a user record: string content or first text block."""
    content = rec.get("message", {}).get("content", "")
    if isinstance(content, str):
        return content
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", "")
    return ""


def _error_blocks(rec: dict[str, Any]) -> int:
    """How many content blocks of a user record carry is_error: true."""
    content = rec.get("message", {}).get("content", "")
    if not isinstance(content, list):
        return 0
    return sum(1 for b in content if isinstance(b, dict) and b.get("is_error"))


def list_sessions(cwd: str) -> list[SessionRef]:
    """Sessions recorded for cwd, newest first."""
    project = projects_dir() / flatten_cwd(cwd)
    if not project.is_dir():
        return []
    refs = [_summarize(f) for f in project.glob("*.jsonl")]
    refs.sort(key=lambda r: (r.started, r.id), reverse=True)
    return refs


def session_paths(ref: SessionRef) -> list[Path]:
    """Main transcript path plus any subagent transcript files."""
    paths = [ref.path]
    subagents = ref.path.parent / ref.id / "subagents"
    if subagents.is_dir():
        paths.extend(sorted(subagents.glob("*.jsonl")))
    return paths
