"""Codex provider: locate rollouts by session_meta cwd and parse records.

Rollouts live at ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl. Line one is
session_meta; scoping to a cwd means reading first lines. Titles come from
~/.codex/history.jsonl. Only record properties are read, never interpreted.
"""

import json
import os
from pathlib import Path
from typing import Any

from sxr.model import Event, SessionRef


def sessions_root() -> Path:
    """Directory tree holding the dated rollout files."""
    root = os.environ.get("CODEX_HOME", "~/.codex")
    return Path(root).expanduser() / "sessions"


def history_titles() -> dict[str, str]:
    """First recorded user text per session id, from history.jsonl."""
    titles: dict[str, str] = {}
    history = sessions_root().parent / "history.jsonl"
    if not history.is_file():
        return titles
    with history.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            titles.setdefault(entry.get("session_id", ""), entry.get("text", ""))
    return titles


def _first_record(path: Path) -> dict[str, Any] | None:
    """The session_meta record, or None when the file is empty/torn."""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            line = fh.readline().strip()
        rec = json.loads(line) if line else None
    except (OSError, json.JSONDecodeError):
        return None
    return rec if isinstance(rec, dict) and rec.get("type") == "session_meta" else None


def _iter_records(path: Path):
    """Yield (seq, record) per parseable line; a torn final line is skipped."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for seq, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield seq, json.loads(line)
            except json.JSONDecodeError:
                continue


def _parts_text(content: Any) -> str:
    """Join the text parts of a message/reasoning content array."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _output_fields(output: Any) -> tuple[str, bool]:
    """(text, is_error) from a function_call_output payload's output field."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return output, False
    if isinstance(output, dict):
        exit_code = (output.get("metadata") or {}).get("exit_code")
        return str(output.get("output", "")), bool(exit_code)
    return _parts_text(output), False


def _response_event(seq: int, ts: str, payload: dict[str, Any]) -> Event:
    """Event for one response_item payload."""
    ptype = payload.get("type", "")
    if ptype in ("message", "agent_message"):
        roles = {"user": "user", "assistant": "asst"}
        role = roles.get(str(payload.get("role", "assistant")), "sys")
        tag = payload.get("phase") or ""
        return Event(seq, ts, role, "text", _parts_text(payload.get("content")), tag=tag)
    if ptype == "reasoning":
        return Event(seq, ts, "asst", "thinking", _parts_text(payload.get("summary")))
    if ptype in ("function_call", "custom_tool_call", "tool_search_call"):
        text = str(payload.get("arguments") or payload.get("input") or "")
        return Event(
            seq,
            ts,
            "asst",
            "tool",
            text,
            tool=payload.get("name", ptype),
            raw={"id": payload.get("call_id", "")},
        )
    if ptype == "web_search_call":
        return Event(
            seq, ts, "asst", "tool", json.dumps(payload.get("action", {})), tool="web_search"
        )
    if ptype in ("function_call_output", "custom_tool_call_output", "tool_search_output"):
        text, is_error = _output_fields(payload.get("output"))
        return Event(
            seq,
            ts,
            "user",
            "result",
            text,
            is_error=is_error,
            raw={"tool_use_id": payload.get("call_id", "")},
        )
    return Event(seq, ts, "meta", f"response.{ptype}")


def _end_event(seq: int, ts: str, ptype: str, payload: dict[str, Any]) -> Event:
    """Event for an event_msg *_end payload; error state is a property."""
    is_error = False
    text = ""
    if ptype == "exec_command_end":
        is_error = bool(payload.get("exit_code"))
        text = str(payload.get("stderr") or payload.get("aggregated_output") or "")
    elif ptype == "patch_apply_end":
        is_error = payload.get("success") is False
        text = str(payload.get("stderr") or payload.get("stdout") or "")
    elif ptype == "mcp_tool_call_end":
        result = payload.get("result")
        is_error = isinstance(result, dict) and "Err" in result
        text = json.dumps(payload.get("invocation", ""), ensure_ascii=False)
    return Event(
        seq,
        ts,
        "meta",
        f"event.{ptype}",
        text,
        is_error=is_error,
        raw={"tool_use_id": payload.get("call_id", "")},
    )


def _record_event(seq: int, rec: dict[str, Any]) -> Event:
    """Event for one rollout record; unknown types keep their type as kind."""
    rtype = rec.get("type", "")
    ts = rec.get("timestamp", "")
    payload = rec.get("payload") or {}
    if rtype == "response_item":
        return _response_event(seq, ts, payload)
    if rtype == "event_msg":
        ptype = payload.get("type", "")
        if ptype == "user_message":
            return Event(seq, ts, "user", "user_message", str(payload.get("message", "")))
        if ptype in ("exec_command_end", "patch_apply_end", "mcp_tool_call_end"):
            return _end_event(seq, ts, ptype, payload)
        return Event(seq, ts, "meta", f"event.{ptype}")
    if rtype == "turn_context":
        text = f"{payload.get('model', '')}/{payload.get('effort', '')}"
        return Event(seq, ts, "ctx", "turn_context", text)
    return Event(seq, ts, "meta", rtype)


def parse(path: Path) -> list[Event]:
    """All events of one rollout, with tool calls annotated ok/err."""
    events = []
    for seq, rec in _iter_records(path):
        event = _record_event(seq, rec)
        event.raw["line"] = rec
        events.append(event)
    tools = {e.raw.get("id"): e for e in events if e.kind == "tool"}
    for event in events:
        if event.kind == "result":
            call = tools.get(event.raw.get("tool_use_id"))
            if call is not None:
                event.tool = call.tool
                call.tag = "err" if event.is_error else "ok"
    return events


def _summarize(path: Path, meta: dict[str, Any], titles: dict[str, str]) -> SessionRef:
    """List-view metadata for one rollout, from record properties."""
    payload = meta.get("payload") or {}
    sid = payload.get("session_id") or payload.get("id") or path.stem
    ref = SessionRef(
        "codex",
        sid,
        path,
        cwd=payload.get("cwd", ""),
        started=meta.get("timestamp", ""),
        size_bytes=path.stat().st_size,
    )
    source = payload.get("source")
    ref.kind = source if isinstance(source, str) else str(payload.get("thread_source") or "")
    ref.extra["originator"] = payload.get("originator", "")
    ref.extra["cli_version"] = payload.get("cli_version", "")
    seen_errors: set[str] = set()
    for seq, rec in _iter_records(path):
        pay = rec.get("payload") or {}
        ptype = pay.get("type", "")
        if rec.get("type") == "response_item" and ptype in ("message", "agent_message"):
            ref.messages += 1
        elif rec.get("type") == "turn_context":
            ref.model = f"{pay.get('model', '')}/{pay.get('effort', '')}"
        elif rec.get("type") == "event_msg" and ptype == "token_count":
            total = (pay.get("info") or {}).get("total_token_usage") or {}
            ref.tokens = int(total.get("total_tokens") or ref.tokens)
        event = _record_event(seq, rec)
        if event.kind == "user_message" and not ref.extra.get("first_user"):
            ref.extra["first_user"] = event.text
        if event.is_error:
            call_id = str(event.raw.get("tool_use_id") or seq)
            if call_id not in seen_errors:
                seen_errors.add(call_id)
                ref.errors += 1
    ref.title = titles.get(sid) or ref.extra.get("first_user", "")
    return ref


def list_sessions(cwd: str) -> list[SessionRef]:
    """Rollouts whose session_meta cwd matches, newest first."""
    root = sessions_root()
    if not root.is_dir():
        return []
    titles = history_titles()
    refs = []
    for path in root.rglob("rollout-*.jsonl"):
        meta = _first_record(path)
        if meta and (meta.get("payload") or {}).get("cwd") == cwd:
            refs.append(_summarize(path, meta, titles))
    refs.sort(key=lambda r: (r.started, r.id), reverse=True)
    return refs


def session_paths(ref: SessionRef) -> list[Path]:
    """The rollout file (subagent linkage is a later milestone)."""
    return [ref.path]
