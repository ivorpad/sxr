"""Secret detection for session transcripts: patterns, structure, entropy.

Detection only. Nothing in this package prints a secret value; callers get
Finding spans and mask them with fingerprints before any output, because
sxr's own output is recorded into the very corpus it audits.
"""

from sxr.secrets.detect import Finding, scan_text
from sxr.secrets.fingerprint import fingerprint, marker

__all__ = ["Finding", "fingerprint", "marker", "scan_text"]
