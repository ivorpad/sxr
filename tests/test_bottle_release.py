"""Only complete, checksum-verified portable bottles may enter the formula."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def release(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "packaging"))
    return importlib.import_module("bottle_release")


def write_bottle(root, tag, version="0.14.0", cellar="any_skip_relocation"):
    """Create one native job's archive and Homebrew metadata."""
    directory = root / tag
    directory.mkdir()
    name = f"sxr--{version}.{tag}.bottle.tar.gz"
    archive = directory / name
    archive.write_bytes(f"fixture {tag}".encode())
    metadata = {
        "ivorpad/tap/sxr": {
            "formula": {"name": "sxr", "pkg_version": version},
            "bottle": {
                "root_url": f"https://github.com/ivorpad/sxr/releases/download/v{version}",
                "cellar": cellar,
                "rebuild": 0,
                "tags": {
                    tag: {
                        "local_filename": name,
                        "filename": name.replace("--", "-"),
                        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    }
                },
            },
        },
    }
    (directory / f"sxr--{version}.{tag}.bottle.json").write_text(json.dumps(metadata))
    return archive


@pytest.mark.parametrize("cellar", ["any", "any_skip_relocation"])
def test_four_platform_bottles_use_homebrew_url_names(release, tmp_path, cellar):
    for tag in ("arm64_sonoma", "sequoia", "arm64_linux", "x86_64_linux"):
        write_bottle(tmp_path, tag, cellar=cellar)
    block, files = release.collect("0.14.0", tmp_path)
    assert block.count(f"cellar: :{cellar},") == 4
    assert len(files) == 4 and all(path.exists() for path in files)
    assert all(path.name.startswith("sxr-0.14.0.") for path in files)


def test_missing_platform_prevents_publication(release, tmp_path):
    write_bottle(tmp_path, "arm64_sonoma")
    with pytest.raises(AssertionError, match="every supported platform"):
        release.collect("0.14.0", tmp_path)


def test_corrupt_bottle_prevents_publication(release, tmp_path):
    archive = write_bottle(tmp_path, "arm64_sonoma")
    archive.write_bytes(b"corrupted archive")
    with pytest.raises(AssertionError, match="checksum mismatch"):
        release.collect("0.14.0", tmp_path)


@pytest.mark.parametrize(
    "version,cellar", [("0.13.0", "any_skip_relocation"), ("0.14.0", "/cellar")]
)
def test_wrong_version_or_fixed_cellar_prevents_publication(release, tmp_path, version, cellar):
    write_bottle(tmp_path, "arm64_sonoma", version, cellar)
    with pytest.raises(AssertionError):
        release.collect("0.14.0", tmp_path)
