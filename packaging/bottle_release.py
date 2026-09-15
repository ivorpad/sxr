"""Attach verified bottles to an existing release and update its formula."""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from publish import call


def collect(version, directory):
    """Validate four native bottle results and return their DSL and upload paths."""
    root_url = f"https://github.com/ivorpad/sxr/releases/download/v{version}"
    tags, files, families = {}, [], set()
    for path in sorted(directory.rglob("*.bottle.json")):
        (entry,) = json.loads(path.read_text()).values()
        assert entry["formula"]["name"] == "sxr"
        assert entry["formula"]["pkg_version"] == version
        bottle = entry["bottle"]
        assert bottle["root_url"] == root_url and bottle["rebuild"] == 0
        assert bottle["cellar"] in {"any", "any_skip_relocation"}
        (tag,) = bottle["tags"]
        assert re.fullmatch(r"[a-z0-9_]+", tag) and tag not in tags
        details = bottle["tags"][tag]
        family = (
            "linux" if tag.endswith("_linux") else "macos",
            "arm64" if tag.startswith("arm64_") else "x86_64",
        )
        assert family not in families
        families.add(family)
        for key in ("local_filename", "filename"):
            assert Path(details[key]).name == details[key]
        source = path.parent / details["local_filename"]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == details["sha256"], f"Bottle checksum mismatch: {tag}"
        # brew bottle uses a double dash locally and a single dash in its URLs.
        destination = path.parent / details["filename"]
        if source != destination:
            source.rename(destination)
        files.append(destination)
        tags[tag] = (digest, bottle["cellar"])
    assert families == {
        ("macos", "arm64"),
        ("macos", "x86_64"),
        ("linux", "arm64"),
        ("linux", "x86_64"),
    }, "Require one bottle for every supported platform"
    lines = ["", "  bottle do", f'    root_url "{root_url}"']
    lines += [
        f'    sha256 cellar: :{cellar}, {tag}: "{digest}"'
        for tag, (digest, cellar) in sorted(tags.items())
    ]
    return "\n".join([*lines, "  end", ""]), files


def attach(version, run, tap, directory):
    """Require a successful bottle workflow before uploading and advertising bottles."""
    result = json.loads(call("gh", "run", "view", str(run), "--json", "conclusion,workflowName"))
    assert result == {"conclusion": "success", "workflowName": "Homebrew bottles"}
    call("gh", "run", "download", str(run), "--dir", str(directory))
    block, files = collect(version, directory)
    path = tap / "Formula/sxr.rb"
    original = path.read_text()
    assert f'  version "{version}"' in original
    assert "  bottle do" not in original, "Formula already has bottles"
    updated = original.replace("\n  def install", block + "\n  def install", 1)
    assert updated != original
    checksums = directory / "BOTTLE_SHA256SUMS"
    checksums.write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(files))
    )
    call("gh", "release", "upload", f"v{version}", *(str(p) for p in files), str(checksums))
    path.write_text(updated)
    call("brew", "style", "--fix", "ivorpad/tap/sxr")


def build_and_attach(version, head, tap):
    """Dispatch the bottle workflow and wait before completing formula publication."""
    import time
    from datetime import UTC, datetime

    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    call("gh", "workflow", "run", "bottles.yml", "--ref", "main", "-f", f"version={version}")
    run = None
    for _ in range(30):
        runs = json.loads(
            call(
                "gh",
                "run",
                "list",
                "--workflow",
                "bottles.yml",
                "--commit",
                head,
                "--limit",
                "10",
                "--json",
                "databaseId,createdAt,displayTitle",
            )
        )
        matches = [
            r
            for r in runs
            if r["createdAt"] >= started and r["displayTitle"] == f"Homebrew bottles {version}"
        ]
        if matches:
            run = matches[0]["databaseId"]
            break
        time.sleep(2)
    assert run is not None, "Could not locate dispatched bottle workflow"
    print(
        f"Building Homebrew bottles: https://github.com/ivorpad/sxr/actions/runs/{run}", flush=True
    )
    call("gh", "run", "watch", str(run), "--interval", "30", "--exit-status")
    with tempfile.TemporaryDirectory(prefix="sxr-bottles-") as temporary:
        attach(version, run, tap, Path(temporary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--run", required=True, type=int)
    args = parser.parse_args()
    tap = Path(call("brew", "--repository", "ivorpad/tap").strip())
    assert not call("git", "-C", str(tap), "status", "--porcelain")
    with tempfile.TemporaryDirectory(prefix="sxr-bottles-") as temporary:
        attach(args.version, args.run, tap, Path(temporary))
