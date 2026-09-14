"""Find qualifiers `tasks.md` dropped from the CSV rows it paraphrases.

SXR-CLI-21 hit a manufactured conflict: two rows scoped `command: sxr show`
proposed rejecting negative limits, `tasks.md` paraphrased them without the scope,
and the result read as a proposal for every command -- which contradicted D-05 and
cost a reviewer escalation. The rows were right; the derived document had lost a
word. `tasks.md`, `ledger.md` and `contracts.md` are all derived, and later slices
trust them, so the same loss anywhere else is worth knowing about.

Three checks, all mechanical, none pretending to read prose:

1. **Scope loss.** A task whose rows all name one command, whose prose speaks
   normatively for a different command.
2. **Shared-flag loss.** An unscoped rule about a flag that several commands own,
   inside a task whose rows all name one command. This is the slice-21 shape
   exactly, and the check is validated against slice 21's preserved original
   wording by `--selftest`.
3. **Clause loss.** Content words in a row's `after` and `acceptance` that appear
   nowhere in the task's prose. Noisy by nature, so it reports the words rather
   than a verdict.

Findings need a human read: this narrows thousands of words to a short list, it
does not decide anything.

    uv run python audit_qualifiers.py
    uv run python audit_qualifiers.py --task SXR-CLI-07
    uv run python audit_qualifiers.py --selftest
"""

import argparse
import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE.parent.parent / "2026-09-10" / "command-review" / "commands-before-after.csv"
TASKS = HERE / "tasks.md"

COMMANDS = (
    "show",
    "prompts",
    "grep",
    "cmds",
    "tools",
    "errors",
    "find",
    "list",
    "stats",
    "skills",
    "index",
    "init",
)
STOP = set(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "no",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "when",
        "which",
        "with",
        "without",
        "any",
        "all",
        "more",
        "one",
        "only",
        "same",
        "than",
        "then",
        "there",
        "these",
        "those",
        "two",
        "use",
        "used",
        "uses",
        "using",
        "each",
        "every",
        "other",
        "rather",
        "so",
        "still",
        "such",
        "also",
        "does",
        "do",
        "done",
        "both",
        "after",
        "before",
        "between",
        "during",
        "if",
        "per",
        "via",
        "what",
        "where",
        "while",
        "whether",
        "must",
        "may",
        "should",
        "would",
        "could",
        "will",
        "shall",
        "new",
        "old",
        "first",
        "second",
    ]
)
NORMATIVE = re.compile(
    r"\b(must|should|reject|rejects|treat|treats|keep|keeps|make|makes"
    r"|add|adds|rename|apply|applies|now|no longer|means)\b"
)

# The wording slice 21 shipped with, preserved so check 2 can be shown to catch it.
SELFTEST = (
    "`--budget` and `--line-limit` reject negatives (exit 2), 0 means no trimming, "
    "and an invalid environment value is reported once."
)


def tasks_blocks(text: str) -> dict:
    """Task id -> (prose, declared row ids), split on the level-2 headings."""
    blocks = {}
    parts = re.split(r"^## (SXR-[A-Z0-9-]+)", text, flags=re.M)
    for ident, body in zip(parts[1::2], parts[2::2], strict=True):
        rows = re.search(r"\*\*rows:\*\* (.*)", body)
        ids = [r.strip() for r in rows.group(1).split(",")] if rows else []
        blocks.setdefault(ident, (body, ids))
    return blocks


def flag_owners(rows: dict) -> dict:
    """Flag -> the commands whose rows mention it, from the CSV rather than guessed."""
    owners: dict = {}
    for row in rows.values():
        command = (row.get("command") or "").replace("sxr ", "").strip()
        text = f"{row.get('item', '')} {row.get('before', '')}"
        for flag in re.findall(r"--[a-z][a-z-]+", text):
            owners.setdefault(flag, set()).add(command)
    return owners


def sentences(body: str) -> list:
    """Prose split into rules: sentence ends, and the bullets tasks.md is made of."""
    return [" ".join(part.split()) for part in re.split(r"(?<=[.;])\s+|\n- ", body)]


def scope_loss(body: str, rows: list) -> list:
    """Commands the prose speaks for normatively that no row is scoped to."""
    scopes = {(r.get("command") or "").replace("sxr ", "").strip() for r in rows}
    scopes.discard("")
    if not scopes or len(scopes) > 3:
        return []
    found = []
    for flat in sentences(body):
        if not NORMATIVE.search(flat):
            continue
        for name in COMMANDS:
            if name in scopes:
                continue
            if re.search(rf"`sxr {name}\b|\b{name} (?:rejects|treats|keeps|now|no longer)", flat):
                found.append((name, flat[:150]))
    return found


def shared_flag_loss(body: str, rows: list, owners: dict) -> list:
    """Unscoped rules about a flag that several commands own, in a one-command task.

    This is the slice-21 shape. Both of its rows were scoped `sxr show`; the prose
    said "`--budget` and `--line-limit` reject negatives (exit 2)" naming no command,
    and `--budget` belongs to `show`, `prompts` and `grep`. A reader of the derived
    document cannot tell which of the three the rule is about, and the one who
    guessed "all of them" escalated a conflict that did not exist.
    """
    scopes = {(r.get("command") or "").replace("sxr ", "").strip() for r in rows}
    scopes.discard("")
    if len(scopes) != 1:
        return []
    return [hit for flat in sentences(body) for hit in _unscoped_rule(flat, scopes, owners)]


def _unscoped_rule(flat: str, scopes: set, owners: dict) -> list:
    """One sentence's verdict: a shared flag ruled on without naming a command."""
    if not NORMATIVE.search(flat) or flat.startswith("**rows:"):
        return []
    if any(re.search(rf"`?sxr {name}\b|`{name}`", flat) for name in COMMANDS):
        return []
    for flag in sorted(set(re.findall(r"--[a-z][a-z-]+", flat))):
        elsewhere = owners.get(flag, set()) - scopes - {""}
        if len(elsewhere) >= 2:
            return [(flag, sorted(elsewhere), flat[:150])]
    return []


def clause_loss(body: str, rows: list) -> list:
    """Content words from each row's proposal that the prose never repeats."""
    prose = set(re.findall(r"[a-z][a-z-]{3,}", body.lower()))
    out = []
    for row in rows:
        proposal = f"{row.get('after', '')} {row.get('acceptance', '')}".lower()
        missing = sorted(
            {
                word
                for word in re.findall(r"[a-z][a-z-]{3,}", proposal)
                if word not in prose and word not in STOP
            }
        )
        if len(missing) >= 4:
            out.append((row["id"], missing))
    return out


def selftest(owners: dict) -> int:
    """Show check 2 catching the wording it was built for, and exit nonzero if not."""
    scoped = {"show"}
    hits = _unscoped_rule(SELFTEST, scoped, owners)
    print(f"  wording: {SELFTEST}")
    print(f"  rows scoped to: {', '.join(sorted(scoped))}")
    if not hits:
        print("  FAIL: the check does not catch the defect it exists for")
        return 1
    flag, elsewhere, _ = hits[0]
    print(f"  caught: {flag} is also owned by {', '.join(elsewhere)}, and no command is named")
    return 0


def report(ident: str, body: str, ids: list, rows: dict, owners: dict) -> tuple:
    """Print one task's findings; return its (scope, shared, clause) counts."""
    declared = [rows[i] for i in ids if i in rows]
    absent = [i for i in ids if i not in rows]
    scope = scope_loss(body, declared)
    shared = shared_flag_loss(body, declared, owners)
    clauses = clause_loss(body, declared)
    if not (scope or shared or clauses or absent):
        return (0, 0, 0)
    named = ", ".join(sorted({(r.get("command") or "?") for r in declared}))
    print(f"\n{ident}  ({len(declared)} rows: {named})")
    for i in absent:
        print(f"  row not in the CSV at all: {i}")
    for name, flat in scope:
        print(f"  SCOPE  prose speaks for '{name}', no row is scoped to it:\n         {flat}")
    for flag, elsewhere, flat in shared:
        print(f"  SHARED {flag} is also on {', '.join(elsewhere)}; this rule names no command:")
        print(f"         {flat}")
    for row_id, missing in clauses:
        print(f"  CLAUSE {row_id}: {len(missing)} proposal words absent from the prose")
        print(f"         {', '.join(missing[:14])}")
    return (len(scope), len(shared), len(clauses))


def main() -> None:
    """Print the checks, per task, with counts a reader can triage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="Only this task id")
    parser.add_argument("--selftest", action="store_true", help="Check 2 against slice 21")
    args = parser.parse_args()
    rows = {r["id"]: r for r in csv.DictReader(CSV_PATH.open())}
    owners = flag_owners(rows)
    if args.selftest:
        raise SystemExit(selftest(owners))
    blocks = tasks_blocks(TASKS.read_text())
    totals = [0, 0, 0]
    for ident, (body, ids) in blocks.items():
        if args.task and ident != args.task:
            continue
        for index, count in enumerate(report(ident, body, ids, rows, owners)):
            totals[index] += count
    print(
        f"\n{totals[0]} scope findings, {totals[1]} shared-flag findings, "
        f"{totals[2]} clause findings across {len(blocks)} tasks"
    )


if __name__ == "__main__":
    main()
