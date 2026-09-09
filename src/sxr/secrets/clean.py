"""Rewrite session files, replacing detected secrets with masked markers.

DRY RUN by default: nothing is written without --apply. The rewrite is
byte-conservative: files are processed as raw lines, only lines carrying a
certain or probable finding change, every changed line must still parse as
JSON, and the original is replaced atomically only after validation. Lines
that are not valid UTF-8 or JSON pass through byte-identical. Sessions
still being written ((live)) are skipped. No backup is kept on purpose: a
backup would keep the secrets. Cleaning stops re-propagation; rotating the
credential is the real remediation.
"""

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sxr.index_store import clear
from sxr.model import SessionRef
from sxr.secrets.detect import scan_text
from sxr.secrets.fingerprint import marker
from sxr.util import is_live, tab_row


@dataclass
class FileResult:
    """What changed (or would change) in one session file."""

    name: str
    lines: int = 0
    replacements: int = 0
    kinds: Counter = field(default_factory=Counter)
    error: str = ""


def _strings(node, out: list) -> None:
    """Collect every string value in a parsed record, nested included."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _strings(value, out)
    elif isinstance(node, list):
        for value in node:
            _strings(value, out)


def _replacements(line: str) -> dict[str, tuple[str, str]]:
    """value -> (marker, kind) for every certain/probable finding in one line."""
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return {}
    strings: list[str] = []
    _strings(rec, strings)
    found: dict[str, tuple[str, str]] = {}
    for text in strings:
        for f in scan_text(text):
            found[f.value] = (marker(f.kind, f.value), f.kind)
    return found


def _clean_line(raw: bytes) -> tuple[bytes, int, list[str]]:
    """(new bytes, replacement count, kinds) for one raw JSONL line.

    A secret whose exact text is absent from the raw line (JSON escaping
    inside the value) is left alone rather than risk a mangling rewrite.
    """
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw, 0, []
    found = _replacements(line)
    if not found:
        return raw, 0, []
    kinds: list[str] = []
    count = 0
    for value, (mark, kind) in found.items():
        hits = line.count(value)
        if hits:
            line = line.replace(value, mark)
            count += hits
            kinds.append(kind)
    if not count:
        return raw, 0, []
    try:
        json.loads(line)
    except json.JSONDecodeError:
        return raw, 0, []  # never write a line the readers cannot parse
    return line.encode("utf-8"), count, kinds


def _clean_file(path: Path, apply: bool) -> FileResult:
    """Scan one file; with apply, rewrite via a validated atomic replace."""
    result = FileResult(path.name)
    stat = path.stat()
    tmp_name = ""
    try:
        with contextlib.ExitStack() as stack:
            tmp = None
            if apply:
                tmp = stack.enter_context(
                    tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
                )
                tmp_name = tmp.name
            for raw in stack.enter_context(path.open("rb")):
                new, count, kinds = _clean_line(raw)
                if count:
                    result.lines += 1
                    result.replacements += count
                    result.kinds.update(kinds)
                if tmp:
                    tmp.write(new)
        if not apply:
            return result
        if not result.replacements:
            os.unlink(tmp_name)
            return result
        after = path.stat()
        if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
            os.unlink(tmp_name)
            result.error = "changed while cleaning; skipped"
            return result
        os.chmod(tmp_name, stat.st_mode & 0o777)
        os.replace(tmp_name, path)
        return result
    except OSError as exc:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        result.error = str(exc)
        return result


def clean_view(refs: list[SessionRef], session_paths, apply: bool) -> int:
    """Clean (or preview) every file of every session in scope; exit 1 if none."""
    if apply:
        try:
            clear()
        except (OSError, sqlite3.Error) as exc:
            print(f"error: cannot clear search index before cleaning: {exc}", file=sys.stderr)
            return 2
    total = files = 0
    skipped_live = 0
    print(tab_row("# session", "file", "lines", "replacements", "kinds"))
    for ref in refs:
        ref.summarize()
        if is_live(ref.ended):
            skipped_live += 1
            continue
        for path in session_paths(ref):
            r = _clean_file(path, apply)
            if r.error:
                print(f"# {ref.short_id}/{r.name}: {r.error}", file=sys.stderr)
                continue
            if not r.replacements:
                continue
            total += r.replacements
            files += 1
            kinds = ",".join(f"{k}({n})" for k, n in r.kinds.most_common())
            print(tab_row(ref.short_id, r.name, r.lines, r.replacements, kinds))
    if skipped_live:
        print(f"# skipped {skipped_live} (live) session(s) still being written")
    if not total:
        print("# nothing to clean in scope")
        return 1
    if apply:
        try:
            clear()
        except (OSError, sqlite3.Error) as exc:
            print(
                f"error: files cleaned but search index could not be cleared: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            f"# cleaned {total} secret occurrences across {files} files; "
            "markers: [sxr:redacted:<kind>:<fp>]. Rotation is still the real fix."
        )
    else:
        print(
            f"# DRY RUN: {total} occurrences across {files} files; nothing written. "
            "Write with: sxr clean --apply"
        )
    return 0
