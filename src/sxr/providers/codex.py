"""Codex provider: locate rollouts by session_meta cwd and parse records.

Rollouts live at ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl. Line one is
session_meta; scoping to a cwd means reading first lines. Titles come from
~/.codex/history.jsonl. Only record properties are read, never interpreted.
"""

import json
import os
from functools import cache, partial
from pathlib import Path
from typing import Any

from sxr.discovery import deduplicate, matches_path, normalize_path, project_paths
from sxr.model import Event, SessionRef
from sxr.providers.codex_events import _record_event, canonicalize


def sessions_root() -> Path:
    """Directory tree holding the dated rollout files."""
    root = os.environ.get("CODEX_HOME", "~/.codex")
    return Path(root).expanduser() / "sessions"


def history_titles(root: Path | None = None) -> dict[str, str]:
    """First recorded user text per session id, from history.jsonl."""
    titles: dict[str, str] = {}
    history = (root if root is not None else sessions_root().parent) / "history.jsonl"
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


def parse(path: Path) -> list[Event]:
    """All events of one rollout, with tool calls annotated ok/err."""
    events = []
    for seq, rec in _iter_records(path):
        event = _record_event(seq, rec)
        event.raw["line"] = rec
        events.append(event)
    canonicalize(events)
    return events


def _metadata(path: Path, meta: dict[str, Any]) -> SessionRef:
    """Identity, scope and ordering from the rollout's first record."""
    payload = meta.get("payload") or {}
    sid = payload.get("id") or payload.get("session_id") or path.stem
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
    ref.extra["session_id"] = payload.get("session_id", "")
    lineage = source.get("subagent", {}) if isinstance(source, dict) else {}
    spawn = lineage.get("thread_spawn", {}) if isinstance(lineage, dict) else {}
    ref.extra["parent_thread_id"] = payload.get("parent_thread_id") or spawn.get(
        "parent_thread_id", ""
    )
    ref.extra["originator"] = payload.get("originator", "")
    ref.extra["cli_version"] = payload.get("cli_version", "")
    return ref


def _summarize(ref: SessionRef, titles, events: list[Event] | None = None) -> None:
    """Fill summary fields without reading the transcript a second time."""
    for event in parse(ref.path) if events is None else events:
        rec = event.raw["line"]
        pay = rec.get("payload") or {}
        ptype = pay.get("type", "")
        ref.ended = rec.get("timestamp") or ref.ended
        if rec.get("type") == "response_item" and ptype in ("message", "agent_message"):
            ref.messages += 1
        elif rec.get("type") == "turn_context":
            ref.model = f"{pay.get('model', '')}/{pay.get('effort', '')}"
        elif rec.get("type") == "event_msg" and ptype == "token_count":
            total = (pay.get("info") or {}).get("total_token_usage") or {}
            ref.tokens = int(total.get("total_tokens") or ref.tokens)
        if event.kind == "user_message" and not ref.extra.get("first_user"):
            ref.extra["first_user"] = event.text
        if event.is_error:
            ref.errors += 1
    ref.title = titles().get(ref.id) or ref.extra.get("first_user", "")


def list_sessions(
    cwd: str,
    *,
    recursive: bool = False,
    worktrees: bool = False,
    include_archives: bool = False,
    lazy: bool = False,
) -> list[SessionRef]:
    """Matching rollouts, optionally including descendants, worktrees and archives."""
    targets = project_paths(cwd, worktrees)
    roots = [normalize_path(sessions_root())]
    if include_archives:
        roots.append(roots[0].parent / "archived_sessions")
    titles = cache(history_titles)
    refs = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("rollout-*.jsonl")):
            meta = _first_record(path)
            if meta and matches_path(
                (meta.get("payload") or {}).get("cwd", ""), targets, recursive
            ):
                ref = _metadata(path, meta)
                ref._summary_loader = partial(_summarize, ref, titles)
                ref.extra.update(root=str(root), archived=root != roots[0], provenance=[str(path)])
                refs.append(ref)
    refs = deduplicate(refs)
    refs.sort(key=lambda r: (r.started, r.id), reverse=True)
    if not lazy:
        for ref in refs:
            ref.summarize()
    return refs


def session_paths(ref: SessionRef) -> list[Path]:
    """The rollout file (subagent linkage is a later milestone)."""
    return [ref.path]
