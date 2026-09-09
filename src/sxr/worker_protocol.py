"""Bounded local requests and streamed CLI output over an owner-only Unix socket."""

import struct

ENVIRONMENT = (
    "HOME",
    "PATH",
    "SXR_CACHE_DIR",
    "SXR_NO_CACHE",
    "XDG_CACHE_HOME",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "CODEX_THREAD_ID",
    "CODEX_SESSION_ID",
    "TZ",
    "XDG_CONFIG_HOME",
)
MAX_FIELD = 1024 * 1024
MAX_REQUEST = 4 * MAX_FIELD


def read_exact(stream, size):
    """Read a complete field or reject a disconnected client."""
    parts = bytearray()
    while len(parts) < size:
        chunk = stream.recv(size - len(parts))
        if not chunk:
            raise ConnectionError("incomplete worker request")
        parts.extend(chunk)
    return bytes(parts)


def number(stream):
    """Read an unsigned network-order field length."""
    return struct.unpack("!I", read_exact(stream, 4))[0]


def field(stream, budget):
    """Decode a filesystem string, preserving undecodable path bytes."""
    size = number(stream)
    if size == 0xFFFFFFFF:
        return None
    budget[0] += size
    if size > MAX_FIELD or budget[0] > MAX_REQUEST:
        raise ValueError("worker request is too large")
    return read_exact(stream, size).decode("utf-8", errors="surrogateescape")


def request(stream):
    """Accept only the current protocol and explicitly forwarded environment settings."""
    budget = [0]
    version, action, cwd = (field(stream, budget) for _ in range(3))
    count = number(stream)
    if count > 4096:
        raise ValueError("too many find arguments")
    arguments = [field(stream, budget) for _ in range(count)]
    count = number(stream)
    if count > len(ENVIRONMENT):
        raise ValueError("too many environment settings")
    environment = {}
    for _ in range(count):
        key, value = field(stream, budget), field(stream, budget)
        if key not in ENVIRONMENT or key in environment:
            raise ValueError("invalid environment setting")
        environment[key] = value
    if not version or action not in ("find", "skills", "status", "stop") or not cwd:
        raise ValueError("invalid worker request")
    if any(arg is None for arg in arguments):
        raise ValueError("missing find argument")
    return version, action, cwd, arguments, environment


def send_request(stream, version, action, cwd, arguments, environment):
    """Send the same wire format used by the native CLI launcher."""

    def send(value):
        data = value.encode("utf-8", errors="surrogateescape") if value is not None else None
        stream.sendall(struct.pack("!I", len(data) if data is not None else 0xFFFFFFFF))
        if data:
            stream.sendall(data)

    for value in (version, action, cwd):
        send(value)
    stream.sendall(struct.pack("!I", len(arguments)))
    for value in arguments:
        send(value)
    stream.sendall(struct.pack("!I", len(environment)))
    for key, value in environment.items():
        send(key)
        send(value)


def frame(stream, kind, data):
    """Stream bounded chunks without buffering a long index build's progress."""
    stream.sendall(kind + struct.pack("!I", len(data)) + data)


class Output:
    """A text stream forwarding stdout or stderr immediately to the calling CLI."""

    encoding = "utf-8"

    def __init__(self, stream, kind):
        self.stream, self.kind = stream, kind

    def write(self, text):
        """Forward output in small frames while retaining the normal text-stream API."""
        data = text.encode("utf-8", errors="backslashreplace")
        for start in range(0, len(data), 16384):
            frame(self.stream, self.kind, data[start : start + 16384])
        return len(text)

    def flush(self):
        """Writes are already forwarded synchronously."""

    def isatty(self):
        """The worker preserves the CLI's plain, pipe-friendly output."""
        return False
