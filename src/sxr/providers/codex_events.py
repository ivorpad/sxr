"""Codex rollout record fields and stable execution identities."""

import json
import shlex
from typing import Any

from sxr.model import Event


def _parts_text(content: Any) -> str:
    """Join the text parts of a message/reasoning content array."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _outcome(payload: dict[str, Any]) -> str:
    """A recorded outcome, leaving absent or unfinished states unknown."""
    code = payload.get("exit_code")
    if isinstance(code, int):
        return "err" if code else "ok"
    if payload.get("status") in ("failed", "error", "declined"):
        return "err"
    return ""


def _output_fields(output: Any) -> tuple[str, str]:
    """Text and outcome from a function_call_output payload's output field."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return output, ""
    if isinstance(output, dict):
        outcome = _outcome(output.get("metadata") or {}) or _outcome(output)
        return str(output.get("output", "")), outcome
    return _parts_text(output), ""


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
        text, outcome = _output_fields(payload.get("output"))
        return Event(
            seq,
            ts,
            "user",
            "result",
            text,
            is_error=outcome == "err",
            raw={"tool_use_id": payload.get("call_id", ""), "outcome": outcome},
        )
    return Event(seq, ts, "meta", f"response.{ptype}")


def _end_event(seq: int, ts: str, ptype: str, payload: dict[str, Any]) -> Event:
    """Event for an event_msg *_end payload; error state is a property."""
    outcome = ""
    text = ""
    if ptype == "exec_command_end":
        outcome = _outcome(payload)
        text = str(payload.get("stderr") or payload.get("aggregated_output") or "")
    elif ptype == "patch_apply_end":
        if isinstance(payload.get("success"), bool):
            outcome = "ok" if payload["success"] else "err"
        text = str(payload.get("stderr") or payload.get("stdout") or "")
    elif ptype == "mcp_tool_call_end":
        result = payload.get("result")
        if isinstance(result, dict):
            outcome = "err" if "Err" in result else "ok" if "Ok" in result else ""
        text = json.dumps(payload.get("invocation", ""), ensure_ascii=False)
    return Event(
        seq,
        ts,
        "meta",
        f"event.{ptype}",
        text,
        is_error=outcome == "err",
        raw={"tool_use_id": payload.get("call_id", ""), "outcome": outcome},
    )


def _command_item(seq: int, ts: str, payload: dict[str, Any]) -> Event:
    """One command with its output; the outer orchestration call stays separate."""
    item = payload["item"]
    command = item.get("command") or ""
    if isinstance(command, list):
        command = shlex.join(str(part) for part in command)
    output = item.get("aggregated_output")
    if output is None:
        output = "\n".join(str(item[k]) for k in ("stdout", "stderr") if item.get(k))
    command, output = str(command), str(output)
    outcome = _outcome(item)
    identity = item.get("call_id") or item.get("id") or ""
    return Event(
        seq,
        ts,
        "asst",
        "tool",
        "\n".join(p for p in (command, output) if p),
        tool="exec_command",
        is_error=outcome == "err",
        tag=outcome,
        raw={
            "id": identity,
            "tool_use_id": identity,
            "command": command,
            "output": output,
            "outcome": outcome,
            "completed_item": payload["type"] == "item_completed",
            "identities": [value for value in (item.get("id"), item.get("call_id")) if value],
        },
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
        if (
            ptype in ("item_started", "item_updated", "item_completed")
            and (payload.get("item") or {}).get("type") == "CommandExecution"
        ):
            return _command_item(seq, ts, payload)
        if ptype == "user_message":
            return Event(seq, ts, "user", "user_message", str(payload.get("message", "")))
        if ptype == "exec_command_begin":
            return _command_item(seq, ts, {"type": ptype, "item": payload})
        if ptype in ("exec_command_end", "patch_apply_end", "mcp_tool_call_end"):
            return _end_event(seq, ts, ptype, payload)
        return Event(seq, ts, "meta", f"event.{ptype}")
    if rtype == "turn_context":
        text = f"{payload.get('model', '')}/{payload.get('effort', '')}"
        return Event(seq, ts, "ctx", "turn_context", text)
    return Event(seq, ts, "meta", rtype)


def canonicalize(events: list[Event]) -> None:
    """Count each stable call/outcome once, retaining duplicate source records."""
    parents: dict[str, str] = {}

    def root(identity: str) -> str:
        parents.setdefault(identity, identity)
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity

    identities: dict[int, list[str]] = {}
    for event in events:
        values = event.raw.get("identities") or [
            event.raw.get("id") or event.raw.get("tool_use_id")
        ]
        values = [str(value) for value in values if value]
        if not values:
            continue
        identities[event.seq] = values
        for value in values[1:]:
            parents[root(value)] = root(values[0])

    groups: dict[tuple[str, str], list[Event]] = {}
    for event in events:
        if event.seq not in identities:
            continue
        identity = root(identities[event.seq][0])
        event.raw["logical_id"] = identity
        facets = (["call"] if event.kind == "tool" else []) + (
            ["outcome"] if "outcome" in event.raw else []
        )
        for facet in facets:
            groups.setdefault((identity, facet), []).append(event)

    winners = {}
    kept: set[int] = set()
    for key, candidates in groups.items():
        winner = max(
            candidates,
            key=lambda e: (
                bool(e.raw.get("outcome")) if key[1] == "outcome" else False,
                bool(e.raw.get("completed_item")),
                "command" in e.raw,
                -e.seq,
            ),
        )
        winners[key] = winner
        kept.add(winner.seq)
        winner.raw["source_seqs"] = sorted(
            set(winner.raw.get("source_seqs", [])) | {e.seq for e in candidates}
        )
    for event in events:
        identity = event.raw.get("logical_id")
        if not identity:
            continue
        call = winners.get((identity, "call"))
        outcome = winners.get((identity, "outcome"))
        if event.seq not in kept:
            event.raw["duplicate_of"] = (outcome or call).seq
            event.kind = f"duplicate.{event.kind}"
            event.text = event.tool = event.tag = ""
            event.is_error = False
            continue
        if event.kind == "tool":
            event.tag = outcome.raw.get("outcome", "") if outcome else ""
            if event is not outcome:
                event.is_error = False
                event.text = event.raw.get("command", event.text)
        elif call is not None:
            event.tool = call.tool
