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

from sxr.file_stamp import signature
from sxr.index_store import clear
from sxr.model import SessionRef
from sxr.output import RowBudget
from sxr.secrets.files import last_timestamp, physical_paths
from sxr.secrets.patterns import load_rules
from sxr.secrets.records import clean_line as _clean_line
from sxr.util import is_live, tab_row


@dataclass
class FileResult:
    """What changed (or would change) in one session file."""

    name: str
    lines: int = 0
    replacements: int = 0
    kinds: Counter = field(default_factory=Counter)
    error: str = ""


def _copy_prefix(source, target, length):
    """Copy the already scanned prefix in bounded chunks when the first secret is found."""
    source.seek(0)
    while length:
        chunk = source.read(min(length, 1048576))
        if not chunk:
            raise OSError("changed while cleaning; skipped")
        target.write(chunk)
        length -= len(chunk)


def _clean_file(path: Path, apply: bool, expected=None) -> FileResult:
    """Scan one file; with apply, rewrite via a validated atomic replace."""
    result = FileResult(path.name)
    tmp_name = ""
    try:
        path = path.resolve(strict=True)
        with contextlib.ExitStack() as stack:
            source = stack.enter_context(path.open("rb"))
            stat = os.fstat(source.fileno())
            stamp = signature(stat)
            if (expected and stamp != expected) or signature(path.stat()) != stamp:
                raise OSError("changed before cleaning; skipped")
            tmp = None
            offset = 0
            for raw in source:
                new, count, kinds = _clean_line(raw)
                if count:
                    result.lines += 1
                    result.replacements += count
                    result.kinds.update(kinds)
                    if apply and tmp is None:
                        tmp = stack.enter_context(
                            tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
                        )
                        tmp_name = tmp.name
                        _copy_prefix(source, tmp, offset)
                        source.seek(offset + len(raw))
                if tmp:
                    tmp.write(new)
                offset += len(raw)
            if signature(os.fstat(source.fileno())) != stamp:
                raise OSError("changed while cleaning; skipped")
            if tmp:
                tmp.flush()
                os.fsync(tmp.fileno())
        if tmp_name:
            os.chmod(tmp_name, stat.st_mode & 0o777)
        if signature(path.stat()) != stamp:
            raise OSError("changed while cleaning; skipped")
        if tmp_name:
            os.replace(tmp_name, path)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        # Scanner exceptions can contain input text; only filesystem messages are safe.
        result.error = str(exc) if isinstance(exc, OSError) else type(exc).__name__
    finally:
        if tmp_name:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError as exc:
                result.error = f"{result.error}; cannot remove temporary file: {exc}".lstrip("; ")
    return result


def _clear_cache(stage):
    """Drop cached transcript data before and after apply, reporting incomplete work."""
    try:
        clear()
    except (OSError, sqlite3.Error) as exc:
        print(f"error: cannot clear search index {stage} cleaning: {exc}", file=sys.stderr)
        return False
    return True


def _print_result(ref, path, result, json_out, apply):
    """One masked file result, with full structured counts when requested."""
    if json_out:
        print(
            json.dumps(
                dict(
                    type="clean",
                    session=ref.short_id,
                    file=str(path),
                    lines=result.lines,
                    replacements=result.replacements,
                    kinds=dict(result.kinds),
                    applied=apply,
                )
            )
        )
    else:
        kinds = ",".join(f"{k}({n})" for k, n in result.kinds.most_common())
        print(tab_row(ref.short_id, result.name, result.lines, result.replacements, kinds))


def clean_view(
    refs: list[SessionRef],
    session_paths,
    apply: bool,
    json_out: bool = False,
    limit: int | None = None,
) -> int:
    """Clean (or preview) every file of every session in scope; exit 1 if none."""
    try:
        load_rules()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if apply and not _clear_cache("before"):
        return 2
    total = files = errors = skipped_live = 0
    seen, budget = set(), RowBudget(limit)
    if not json_out:
        print(tab_row("# session", "file", "lines", "replacements", "kinds"))
    for ref in refs:
        try:
            paths = physical_paths(ref, session_paths)
        except OSError as exc:
            errors += 1
            print(f"# {ref.short_id}: {exc}", file=sys.stderr)
            continue
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            try:
                expected = signature(path.stat())
                if (path == ref.path and is_live(ref.ended)) or is_live(last_timestamp(path)):
                    skipped_live += 1
                    continue
                r = _clean_file(path, apply, expected=expected)
            except (OSError, ValueError, RecursionError) as exc:
                message = str(exc) if isinstance(exc, OSError) else type(exc).__name__
                r = FileResult(path.name, error=message)
            if r.error:
                errors += 1
                print(f"# {ref.short_id}/{r.name}: {r.error}", file=sys.stderr)
                continue
            if not r.replacements:
                continue
            total += r.replacements
            files += 1
            for _ in budget.take([r]):
                _print_result(ref, path, r, json_out, apply)
    budget.notice("file rows", stderr=json_out)
    summary = sys.stderr if json_out else sys.stdout
    if skipped_live:
        print(f"# skipped {skipped_live} (live) session(s) still being written", file=summary)
    if apply and not _clear_cache("after"):
        return 2
    if errors:
        print(f"# cleaning incomplete: {errors} file(s) failed", file=sys.stderr)
        return 2
    if not total:
        print("# nothing to clean in scope", file=summary)
        return 1
    if apply:
        print(
            f"# cleaned {total} secret occurrences across {files} files; "
            "markers: [sxr:redacted:<kind>:<fp>]. Rotation is still the real fix.",
            file=summary,
        )
    else:
        print(
            f"# DRY RUN: {total} occurrences across {files} files; nothing written. "
            "Write with: sxr secrets clean --apply",
            file=summary,
        )
    return 0
