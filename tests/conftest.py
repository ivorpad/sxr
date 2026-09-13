"""Keep derived search data, and one-per-process notices, inside each test."""

import pytest

from sxr.util import reset_env_notices


@pytest.fixture(autouse=True)
def private_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "sxr-index"))
    monkeypatch.delenv("SXR_NO_CACHE", raising=False)
    # The unusable-env notice fires once per process so one command does not repeat
    # it; a test session is one process running many commands, so each test starts
    # with that memory cleared.
    reset_env_notices()
