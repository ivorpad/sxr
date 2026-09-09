"""An idle-expiring local worker for repeated, freshly verified session searches."""

import argparse
import fcntl
import json
import os
import socket
import stat
import struct
import sys
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from sxr import __version__, find_service
from sxr.find_cli import main as find
from sxr.index_store import index_path
from sxr.worker_backend import Backend, caller
from sxr.worker_protocol import Output, frame, number, read_exact, request, send_request


def socket_path():
    """Use a versioned socket beside the private index."""
    return index_path().parent / f"find-{__version__}.sock"


def _handle(stream):
    version, action, cwd, arguments, environment = request(stream)
    if version != __version__:
        raise ValueError("worker version mismatch")
    with redirect_stdout(Output(stream, b"O")), redirect_stderr(Output(stream, b"E")):
        if action in ("find", "skills"):
            with caller(cwd, environment):
                try:
                    if action == "skills":
                        from sxr.skills_cli import main as skills

                        code = skills(arguments)
                    else:
                        code = find(arguments)
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else 2
        else:
            print(json.dumps(dict(pid=os.getpid(), version=__version__, running=action != "stop")))
            code = 0
    frame(stream, b"R", struct.pack("!I", code))
    return action != "stop"


def _remove_stale(path):
    if path.exists() or path.is_symlink():
        existing = path.lstat()
        if not stat.S_ISSOCK(existing.st_mode) or existing.st_uid != os.getuid():
            raise OSError("worker path is not an owned socket")
        path.unlink()


def serve(path, idle=300):
    """Accept serial owner-only requests; every find still inventories current source files."""
    path = Path(path).absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_uid != os.getuid():
        raise OSError("worker directory belongs to another user")
    lock = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    backend = Backend()
    original = find_service.connect
    identity = None
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        _remove_stale(path)
        with closing(socket.socket(socket.AF_UNIX)) as listener:
            mask = os.umask(0o077)
            try:
                listener.bind(str(path))
                path.chmod(0o600)
            finally:
                os.umask(mask)
            identity = path.lstat().st_ino
            listener.listen(16)
            listener.settimeout(idle)
            find_service.connect = backend.connection
            os.chdir("/")
            while True:
                try:
                    stream, _ = listener.accept()
                except TimeoutError:
                    break
                with stream:
                    stream.settimeout(10)
                    try:
                        if not _handle(stream):
                            break
                    except (OSError, ValueError, TypeError) as exc:
                        try:
                            frame(stream, b"E", f"error: worker request failed: {exc}\n".encode())
                            frame(stream, b"R", struct.pack("!I", 2))
                        except OSError:
                            pass
    finally:
        find_service.connect = original
        backend.close()
        if identity is not None and path.exists() and path.lstat().st_ino == identity:
            path.unlink()
        os.close(lock)
    return 0


def control(action):
    """Read status or stop this version's worker without sending operating-system signals."""
    with closing(socket.socket(socket.AF_UNIX)) as stream:
        stream.settimeout(5)
        stream.connect(str(socket_path()))
        send_request(stream, __version__, action, os.getcwd(), [], {})
        while True:
            kind = read_exact(stream, 1)
            data = read_exact(stream, number(stream))
            if kind == b"R":
                return struct.unpack("!I", data)[0]
            destination = sys.stdout if kind == b"O" else sys.stderr
            destination.write(data.decode("utf-8", errors="replace"))


def main(arguments):
    """Manage the optional worker used by Homebrew's native find launcher."""
    parser = argparse.ArgumentParser(prog="sxr serve")
    parser.add_argument("action", nargs="?", choices=("status", "stop"), default="status")
    parser.add_argument("--foreground", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--idle", type=float, default=300, help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    try:
        if options.foreground:
            if options.idle <= 0:
                parser.error("--idle must be positive")
            return serve(options.foreground, options.idle)
        return control(options.action)
    except (OSError, ValueError) as exc:
        print(f"error: worker unavailable: {exc}", file=sys.stderr)
        return 1
