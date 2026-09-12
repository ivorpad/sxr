"""Render every session an argument selected, not just the first one.

`@A:@B` resolves to several sessions, so `show`, `prompts` and `tools` render a
list. Two rules keep that readable and backward compatible:

Identity. When a selection holds more than one session, each session's output is
preceded by the same banner, `# session @N  <short id>  <path>`. Text views put
it on stdout with the data it labels; `--json` views put it on stderr, because
raw JSONL records are a fixed contract and stdout must stay parseable.

One allowance. `-n` is a single row allowance for the whole invocation, matching
`errors`, `cmds`, `stats` and `path`. A selection of exactly one session takes
the unchanged single-session path, so existing output stays byte-identical.
"""

import sys
from collections.abc import Callable

from sxr.model import SessionRef
from sxr.output import RowBudget


def banner(ref: SessionRef, *, stderr: bool = False) -> None:
    """Name the session whose output follows: scope handle, id, and file.

    Colliding ids already display as their handle, so a field is printed once.
    """
    fields = [ref.extra.get("handle", ""), ref.short_id, str(ref.path)]
    named = [value for index, value in enumerate(fields) if value and value not in fields[:index]]
    print("# session " + "  ".join(named), file=sys.stderr if stderr else sys.stdout)


def render(
    refs: list[SessionRef],
    render_one: Callable[[SessionRef, RowBudget | None], int],
    limit: int | None,
    label: str,
    *,
    json_out: bool = False,
) -> int:
    """Render each selected session in scope order; exit 1 only when all are empty.

    render_one receives the shared row allowance, or None when it owns its own.
    """
    if len(refs) == 1:
        return render_one(refs[0], None)
    budget = RowBudget(limit)
    codes = []
    for index, ref in enumerate(refs):
        if index and not json_out:
            print()
        banner(ref, stderr=json_out)
        codes.append(render_one(ref, budget))
    budget.notice(label, stderr=json_out)
    return 0 if 0 in codes else 1
