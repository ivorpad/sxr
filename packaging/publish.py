"""Publish already-committed sources and matching, verified portable CI artifacts."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

TARGETS = ("macos-arm64", "macos-x86_64", "linux-arm64", "linux-x86_64")


def call(*arguments, **kwargs):
    """Run commands without shell interpolation, stopping at the first failed operation."""
    return subprocess.run(arguments, check=True, text=True, capture_output=True, **kwargs).stdout


def formula(version, assets, tests):
    """Install bundles directly, preserving the tap's existing functional tests."""
    lines = [
        "class Sxr < Formula",
        '  desc "Session x-ray: read Claude Code and Codex sessions from the terminal"',
        '  homepage "https://github.com/ivorpad/sxr"',
        f'  version "{version}"',
        '  license "MIT"',
    ]
    for system in ("macos", "linux"):
        lines.extend(["", f"  on_{system} do"])
        for architecture, block in (("arm64", "on_arm"), ("x86_64", "on_intel")):
            name = f"sxr-{version}-{system}-{architecture}.tar.gz"
            checksum = hashlib.sha256((assets / name).read_bytes()).hexdigest()
            lines.extend(
                [
                    f"    {block} do",
                    f'      url "https://github.com/ivorpad/sxr/releases/download/v{version}/{name}"',
                    f'      sha256 "{checksum}"',
                    "    end",
                ]
            )
        lines.append("  end")
    lines.extend(
        [
            "",
            "  def install",
            '    libexec.install Dir["*"]',
            '    bin.install_symlink libexec/"sxr"',
            "  end",
            "",
            "  test do" + tests,
        ]
    )
    return "\n".join(lines)


def prepare(version, head, directory):
    """Require successful builds for this exact commit and collect all six release assets."""
    runs = json.loads(
        call(
            "gh",
            "run",
            "list",
            "--workflow",
            "binaries.yml",
            "--commit",
            head,
            "--status",
            "success",
            "--limit",
            "1",
            "--json",
            "databaseId",
        )
    )
    if not runs:
        raise SystemExit("Run gh workflow run binaries.yml --ref main and wait for success first")
    run = str(runs[0]["databaseId"])
    call("gh", "run", "download", run, "--dir", str(directory / "ci"))
    assets = directory / "assets"
    assets.mkdir()
    for target in TARGETS:
        name = f"sxr-{version}-{target}.tar.gz"
        source = list((directory / "ci").rglob(name))
        if len(source) != 1:
            raise SystemExit(f"Expected exactly one verified CI artifact: {name}")
        shutil.copy2(source[0], assets / name)
    call("uv", "build", "--out-dir", str(assets))
    checksums = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(assets.iterdir())
    ]
    (assets / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    return assets


def publish(version, notes, head, assets, tap):
    """Publish immutable assets before updating Homebrew to use their checksums."""
    tag = f"v{version}"
    formula_path = tap / "Formula/sxr.rb"
    tests = formula_path.read_text().split("  test do", 1)[1]
    updated = formula(version, assets, tests)
    notes_path = assets.parent / "notes.md"
    notes_path.write_text(notes)
    call("git", "tag", tag)
    call("git", "push", "origin", f"refs/tags/{tag}")
    assert call("git", "ls-remote", "origin", f"refs/tags/{tag}").split()[0] == head
    call(
        "gh",
        "release",
        "create",
        tag,
        "--verify-tag",
        "--title",
        f"sxr {version}",
        "--notes-file",
        str(notes_path),
        *(str(p) for p in sorted(assets.iterdir())),
    )
    formula_path.write_text(updated)
    call("brew", "style", "--fix", "ivorpad/tap/sxr")
    call("git", "-C", str(tap), "add", "Formula/sxr.rb")
    call("git", "-C", str(tap), "commit", "-m", f"sxr {version}: install portable runtimes")
    call("git", "-C", str(tap), "push", "origin", "main")
    assert (
        call("git", "-C", str(tap), "ls-remote", "origin", "main").split()[0]
        == call("git", "-C", str(tap), "rev-parse", "HEAD").strip()
    )
    print("Published release and Homebrew formula", flush=True)
    print(call("brew", "upgrade", "sxr"), flush=True)
    print(call("brew", "test", "sxr"), flush=True)
    assert version in call("sxr", "--version")


def main():
    """Require a clean, pushed main branch with its version bump already committed."""
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("notes")
    options = parser.parse_args()
    version = options.version
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Version must be X.Y.Z"
    assert tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"] == version, (
        "Commit the version bump in pyproject.toml, src/sxr/__init__.py, and uv.lock first"
    )
    assert call("git", "branch", "--show-current").strip() == "main"
    assert not call("git", "status", "--porcelain"), "Working tree must be clean"
    head = call("git", "rev-parse", "HEAD").strip()
    assert call("git", "ls-remote", "origin", "main").split()[0] == head
    assert not call("git", "ls-remote", "origin", f"refs/tags/v{version}"), "Tag already exists"
    tap = Path(call("brew", "--repository", "ivorpad/tap").strip())
    assert not call("git", "-C", str(tap), "status", "--porcelain"), "Tap must be clean"
    with tempfile.TemporaryDirectory(prefix="sxr-release-") as temporary:
        assets = prepare(version, head, Path(temporary))
        publish(version, options.notes, head, assets, tap)


if __name__ == "__main__":
    main()
