"""Keep derived search data inside each test's temporary directory."""

import pytest


@pytest.fixture(autouse=True)
def private_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "sxr-index"))
    monkeypatch.delenv("SXR_NO_CACHE", raising=False)
