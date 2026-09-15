"""Build and pour a Homebrew bottle from a verified published portable bundle."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from publish import TARGETS, call, formula


def build(version, directory):
    """Use Homebrew's bottle builder, then verify installation from its archive."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Version must be X.Y.Z")
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    call(
        "gh",
        "release",
        "download",
        f"v{version}",
        "--dir",
        str(directory),
        "--pattern",
        "SHA256SUMS",
        "--pattern",
        f"sxr-{version}-*.tar.gz",
    )
    checksums = dict(
        (name, digest)
        for digest, name in (
            line.split() for line in (directory / "SHA256SUMS").read_text().splitlines()
        )
    )
    for target in TARGETS:
        name = f"sxr-{version}-{target}.tar.gz"
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != checksums[name]:
            raise SystemExit(f"Checksum mismatch: {name}")
    # Tapping now evaluates formulae, so trust this formula before cloning the tap.
    call("brew", "trust", "--formula", "ivorpad/tap/sxr")
    call("brew", "tap", "ivorpad/tap")
    tap = Path(call("brew", "--repository", "ivorpad/tap").strip())
    path = tap / "Formula/sxr.rb"
    tests = path.read_text().split("  test do", 1)[1]
    path.write_text(formula(version, directory, tests))
    call("brew", "install", "--build-bottle", "ivorpad/tap/sxr")
    call("brew", "test", "ivorpad/tap/sxr")
    call(
        "brew",
        "bottle",
        "--json",
        "--no-rebuild",
        f"--root-url=https://github.com/ivorpad/sxr/releases/download/v{version}",
        "ivorpad/tap/sxr",
        cwd=directory,
    )
    (metadata,) = directory.glob("*.bottle.json")
    (entry,) = json.loads(metadata.read_text()).values()
    if entry["bottle"]["cellar"] not in {"any", "any_skip_relocation"}:
        raise SystemExit(f"Bottle requires a fixed Cellar: {entry['bottle']['cellar']}")
    (details,) = entry["bottle"]["tags"].values()
    bottle = directory / details["local_filename"]
    call("brew", "uninstall", "ivorpad/tap/sxr")
    call("brew", "install", str(bottle))
    prefix = Path(call("brew", "--prefix", "sxr").strip())
    receipt = json.loads((prefix / "INSTALL_RECEIPT.json").read_text())
    assert receipt["poured_from_bottle"], "Homebrew fell back to a source install"
    call("brew", "test", "ivorpad/tap/sxr")
    print(f"Built and tested {bottle.name}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--output", type=Path, default=Path("bottles"))
    args = parser.parse_args()
    build(args.version, args.output)
