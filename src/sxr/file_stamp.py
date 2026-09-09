"""Filesystem identity shared by discovery, indexes, and transcript reads."""

import os


def signature(stat: os.stat_result) -> tuple[int, ...]:
    """Detect replacement, rewriting, truncation and metadata-preserving edits."""
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
