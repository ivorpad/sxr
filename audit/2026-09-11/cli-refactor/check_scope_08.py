"""Prove what SXR-CLI-08 did and did not change, case by case.

Three claims, each checked mechanically against the captures rather than argued:

1. **Raw `--json` records are unchanged.** The set of printed lines must be equal
   before and after; only the order in which sessions are visited may differ,
   because that is the corrected chronology (D-09).
2. **A literal `--since`/`--before` bound keeps the same sessions.** Window
   filtering already compared UTC instants, so unifying the parser must not move
   scope for any literal bound. Order and the displayed date may change.
3. **An `@N` bound may keep a different set, and that is the renumbering, not the
   window.** Reported explicitly with the sessions gained and lost.

    uv run python check_scope_08.py --output evidence-slice-08/scope-report.txt
"""

import argparse
import re
from pathlib import Path

# Not a fixed width: a Claude short id is 8 characters and a Codex one is 13,
# and assuming 8 made every Codex row parse as empty and every check on it
# vacuously pass.
SESSION = re.compile(r"^@\d+\t(\S+)\t", re.MULTILINE)
KEY = {"aaaaaaa1": "S1", "bbbbbbb2": "S2", "ccccccc3": "S3", "ddddddd4": "S4"}
KEY |= {"01999991-aaaa": "S1", "01999992-bbbb": "S2"}
KEY |= {"01999993-cccc": "S3", "01999994-dddd": "S4"}


def stdout_of(path: Path) -> str:
    """The stdout section of one capture file."""
    text = path.read_text()
    body = text.split("--- stdout\n", 1)[1]
    return body.split("--- stderr", 1)[0]


def sessions(body: str) -> list[str]:
    """The listed sessions, in printed order, as fixture keys.

    An id the fixture does not know is returned verbatim rather than dropped, so
    a parsing mistake shows up as a strange key instead of a silent pass.
    """
    return [KEY.get(short, f"?{short}") for short in SESSION.findall(body)]


def lines(body: str) -> list[str]:
    """Nonempty stdout lines."""
    return [line for line in body.splitlines() if line]


def report(before: Path, after: Path) -> list[str]:
    """One block per claim, naming every case and its verdict."""
    out: list[str] = []
    failures = 0

    out.append("1. Raw --json records: the printed set must be identical (D-09)")
    for path in sorted(before.glob("raw-*.txt")):
        name = path.name[:-4]
        old, new = lines(stdout_of(path)), lines(stdout_of(after / path.name))
        same_set = sorted(old) == sorted(new)
        same_order = old == new
        state = (
            "identical" if same_order else ("reordered, same records" if same_set else "CHANGED")
        )
        failures += 0 if same_set else 1
        out.append(f"   {state:<26} {name}  ({len(old)} -> {len(new)} records)")

    out.append("")
    out.append("2. Literal --since/--before bounds: the kept set must be identical")
    literal = [p for p in sorted(before.glob("scope-*.txt")) if "handle" not in p.name]
    for path in literal:
        name = path.name[:-4]
        old, new = sessions(stdout_of(path)), sessions(stdout_of(after / path.name))
        same_set = sorted(old) == sorted(new)
        state = (
            "identical" if old == new else ("reordered, same set" if same_set else "SET CHANGED")
        )
        failures += 0 if same_set else 1
        out.append(f"   {state:<26} {name}  {old or '(none)'} -> {new or '(none)'}")

    out.append("")
    out.append("3. @N bounds: the set may move, because @N renumbers")
    for path in sorted(before.glob("scope-*handle*.txt")):
        name = path.name[:-4]
        old, new = sessions(stdout_of(path)), sessions(stdout_of(after / path.name))
        gained = [s for s in new if s not in old]
        lost = [s for s in old if s not in new]
        note = (
            "same set" if not gained and not lost else f"gained {gained or '-'}, lost {lost or '-'}"
        )
        out.append(f"   {note:<26} {name}  {old or '(none)'} -> {new or '(none)'}")

    out.append("")
    out.append(f"failures: {failures}")
    return out


def main() -> None:
    """Write the report to --output and print its last line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="File to write (required)")
    parser.add_argument("--before", type=Path, default=Path("evidence-slice-08/before"))
    parser.add_argument("--after", type=Path, default=Path("evidence-slice-08/after"))
    args = parser.parse_args()
    body = report(args.before, args.after)
    args.output.write_text("\n".join(body) + "\n")
    print("\n".join(body))


if __name__ == "__main__":
    main()
