"""Stable masked identity for a secret: a salted hash, never the value.

The same key fingerprints identically everywhere it appears, so an audit
can say "one AWS key, 12 sessions" without storing or showing the value.
The salt is local and random; without it the 8-hex tag is not usefully
brute-forceable from published output.
"""

import hashlib
import os
import secrets
from functools import lru_cache
from pathlib import Path


def salt_path() -> Path:
    """Where the local salt lives; SXR_SALT_FILE overrides for tests."""
    override = os.environ.get("SXR_SALT_FILE")
    if override:
        return Path(override)
    return Path.home() / ".config" / "sxr" / "salt"


@lru_cache(maxsize=4)
def _salt(path: Path) -> bytes:
    """Load the salt, creating a random 0600 file on first use."""
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    path.write_bytes(salt)
    path.chmod(0o600)
    return salt


def fingerprint(value: str) -> str:
    """8-hex salted tag for a secret value."""
    return hashlib.sha256(_salt(salt_path()) + value.encode()).hexdigest()[:8]


def marker(kind: str, value: str) -> str:
    """The in-band replacement written where a secret stood."""
    return f"[sxr:redacted:{kind}:{fingerprint(value)}]"
