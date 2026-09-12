"""Capture a remediation command with immutable source identity and raw output."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]


def identity():
    """Hash sources, tests, packaging and the verification tools used for this run."""
    paths = {"README.md", "pyproject.toml", "uv.lock", "justfile", "konpy.json"}
    for directory in ("src", "tests", "packaging", "native"):
        paths.update(
            str(p.relative_to(REPO))
            for p in (REPO / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    paths.update(str(p.relative_to(REPO)) for p in (REPO / "audit/2026-09-10").rglob("*.py"))
    paths.add("audit/2026-09-10/remediation/resolution-notes.json")
    return dict(
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        files={
            name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in sorted(paths)
        },
        python=sys.version,
        platform=platform.platform(),
    )


def main():
    """Run once, retaining failures and refusing to overwrite an earlier run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("name")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    name, argv = options.name, options.argv
    target = BASE / f"{name}.run.json"
    if target.exists():
        raise SystemExit(f"Evidence already exists: {target}")
    source = identity()
    stamp = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    source_path = BASE / f"source-{stamp[:16]}.json"
    source_path.write_text(json.dumps(source, indent=2) + "\n")
    started = datetime.now(UTC).isoformat()
    with (BASE / f"{name}.log").open("wb") as output:
        result = subprocess.run(argv, cwd=REPO, stdout=output, stderr=subprocess.STDOUT)
    record = dict(
        argv=argv,
        started=started,
        ended=datetime.now(UTC).isoformat(),
        exit_code=result.returncode,
        source_identity=source_path.name,
        source_unchanged=identity() == source,
        evidence=f"{name}.log",
        artifacts={
            path: hashlib.sha256((BASE / path).read_bytes()).hexdigest()
            for path in [f"{name}.log", *options.artifact]
            if (BASE / path).is_file()
        },
    )
    target.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    raise SystemExit(result.returncode or (0 if record["source_unchanged"] else 2))


if __name__ == "__main__":
    main()
