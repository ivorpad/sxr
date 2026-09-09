"""Reuse SQLite pages between requests without retaining stale file inventories."""

import os
from contextlib import contextmanager

from sxr.index_store import connect, index_path


class Backend:
    """Keep one idle database connection and reopen it after clear or replacement."""

    def __init__(self):
        self.context = self.index = self.identity = None

    def close(self):
        """Release cached pages and file descriptors."""
        if self.context is not None:
            self.context.__exit__(None, None, None)
        self.context = self.index = self.identity = None

    @contextmanager
    def connection(self):
        """Reuse the connection only while the same cache file still exists."""
        path = index_path()
        try:
            stat = path.stat()
            identity = (str(path), stat.st_dev, stat.st_ino)
        except OSError:
            identity = None
        if self.index is None or identity != self.identity:
            self.close()
            context = connect()
            index = context.__enter__()
            try:
                stat = path.stat()
            except OSError:
                context.__exit__(None, None, None)
                raise
            self.context, self.index = context, index
            self.identity = (str(path), stat.st_dev, stat.st_ino)
        try:
            yield self.index
        finally:
            # No read transaction or writer lock survives a CLI request.
            self.index.db.rollback()


@contextmanager
def caller(cwd, environment):
    """Apply each caller's roots and current-session ID, including explicit unset values."""
    previous = {key: os.environ.get(key) for key in environment}
    directory = os.getcwd()
    try:
        for key, value in environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        os.chdir(cwd)
        yield
    finally:
        os.chdir(directory)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
