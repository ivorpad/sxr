"""Build a relocatable directory bundle and its native search launcher."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from sxr import __version__


def main():
    """Compile on the target OS; installations only unpack this archive."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    options = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = options.output.resolve()
    system = dict(Darwin="macos", Linux="linux")[platform.system()]
    machine = dict(aarch64="arm64", arm64="arm64", x86_64="x86_64")[platform.machine()]
    name = f"sxr-{__version__}-{system}-{machine}"
    build = output / "build" / name
    bundle = build / "sxr-python"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "sxr-python",
            "--distpath",
            str(build),
            "--workpath",
            str(build / "work"),
            "--specpath",
            str(build),
            "--paths",
            str(root / "src"),
            "--copy-metadata",
            "sxr",
            "--copy-metadata",
            "typer",
            "--collect-data",
            "sxr.secrets",
            str(root / "packaging" / "entry.py"),
        ],
        check=True,
    )
    subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-O2",
            "-std=c11",
            "-D_DEFAULT_SOURCE",
            "-Wall",
            "-Wextra",
            "-Werror",
            f'-DSXR_VERSION="{__version__}"',
            str(root / "native" / "launcher.c"),
            str(root / "native" / "protocol.c"),
            "-o",
            str(bundle / "sxr"),
        ],
        check=True,
    )
    for filename in ("LICENSE", "README.md"):
        shutil.copy2(root / filename, bundle)
    subprocess.run([str(bundle / "sxr"), "--version"], check=True)
    archive = output / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(bundle, arcname="sxr")
    print(archive)


if __name__ == "__main__":
    main()
