"""Exercise the native launcher against real worker processes and changing sources."""

import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sxr import __version__
from sxr.index_store import clear
from sxr.worker_protocol import request, send_request
from test_providers import CODEX_RECORDS, _write_claude, _write_codex


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("SXR_NO_DAEMON", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)
    # Test paths can exceed macOS's Unix socket limit; give this cache a short name.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="sxrw-", dir="/tmp") as cache:
        monkeypatch.setenv("SXR_CACHE_DIR", cache)
        root = Path(__file__).resolve().parent.parent
        target = tmp_path / "bundle with spaces"
        target.mkdir()
        command = target / "sxr"
        subprocess.run(
            [
                "cc",
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
                str(command),
            ],
            check=True,
        )
        shim = target / "sxr-python"
        shim.write_text(f"#!{sys.executable}\nfrom sxr import main\nmain()\n")
        shim.chmod(0o755)
        monkeypatch.setenv("PYTHONPATH", str(root / "src"))
        _write_claude(tmp_path, monkeypatch)
        source = _write_codex(tmp_path, monkeypatch)
        try:
            yield command, source
        finally:
            subprocess.run([str(command), "serve", "stop"], capture_output=True, timeout=10)


def run(command, *args, **kwargs):
    return subprocess.run(
        [str(command), *args], capture_output=True, text=True, timeout=15, **kwargs
    )


def find(command, query="hello", **kwargs):
    return run(command, "find", query, "--path", "/w", "--json", **kwargs)


def test_worker_reuses_process_but_observes_changes_and_current_id(launcher):
    command, source = launcher
    original = find(command)
    assert original.returncode == 0, original.stderr
    status = json.loads(run(command, "serve", "status").stdout)
    env = dict(os.environ, CODEX_THREAD_ID=CODEX_RECORDS[0]["payload"]["session_id"])
    assert json.loads(find(command, env=env).stdout)["total"] == 0
    assert find(command).stdout == original.stdout  # Explicitly unsets the previous caller's ID.
    source.write_text(source.read_text().replace("hello", "replacement"))
    assert find(command).returncode == 1
    assert find(command, "replacement").returncode == 0
    clear()
    assert find(command, "replacement").returncode == 0
    assert json.loads(run(command, "serve", "status").stdout)["pid"] == status["pid"]
    source.unlink()
    assert find(command, "replacement").returncode == 1


def test_worker_parallel_start_paths_fallback_and_relocation(launcher, tmp_path):
    command, source = launcher
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: find(command), range(4)))
    assert all(result.returncode == 0 for result in results), [r.stderr for r in results]
    assert len({r.stdout for r in results}) == 1
    result = run(command, "find", "hello", "--paths", "--path", "/w")
    assert result.stdout.strip() == str(source.resolve())
    direct = find(command, env=dict(os.environ, SXR_NO_DAEMON="1"))
    assert direct.stdout == results[0].stdout and direct.returncode == 0
    assert run(command, "serve", "stop").returncode == 0
    moved = tmp_path / "new prefix"
    shutil.move(command.parent, moved)
    command = moved / "sxr"
    try:
        assert find(command).stdout == direct.stdout
    finally:
        run(command, "serve", "stop")
        shutil.move(moved, tmp_path / "bundle with spaces")


def test_worker_idle_expiry_and_rejects_bad_request(launcher):
    command, _ = launcher
    path = Path(os.environ["SXR_CACHE_DIR"]) / f"find-{__version__}.sock"
    worker = subprocess.Popen(
        [str(command), "serve", "--foreground", str(path), "--idle", "0.2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert path.stat().st_mode & 0o777 == 0o600
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(2)
            stream.connect(str(path))
            stream.sendall(struct.pack("!I", 1024 * 1024 + 1))
            assert stream.recv(1) == b"E"
        assert worker.wait(timeout=5) == 0
        assert not path.exists()
    finally:
        if worker.poll() is None:
            worker.terminate()
        worker.communicate(timeout=5)


def test_protocol_rejects_oversized_frames_and_environment():
    sender, receiver = socket.socketpair()
    with sender, receiver:
        send_request(sender, __version__, "find", "/", [], {"UNEXPECTED": "bad"})
        with pytest.raises(ValueError, match="invalid environment"):
            request(receiver)
    sender, receiver = socket.socketpair()
    with sender, receiver:
        sender.sendall(struct.pack("!I", 1024 * 1024 + 1))
        with pytest.raises(ValueError, match="too large"):
            request(receiver)


def test_worker_refused_path_falls_back_without_replacing_it(launcher):
    command, _ = launcher
    path = Path(os.environ["SXR_CACHE_DIR"]) / f"find-{__version__}.sock"
    path.write_text("keep this file")
    result = find(command)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["total"] == 1
    assert path.read_text() == "keep this file"


def test_worker_skill_lookup_observes_installs_and_caller_roots(launcher, tmp_path):
    command, _ = launcher
    root = tmp_path / ".agents/skills/notify"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("fixture")
    result = run(command, "skills", "notify", "--paths")
    assert result.returncode == 0 and result.stdout.strip() == str(root / "SKILL.md")
    status = json.loads(run(command, "serve", "status").stdout)
    other = tmp_path / "other-config/skills/other"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("fixture")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(other.parent.parent))
    assert run(command, "skills", "other", "--exact", "--paths", env=env).returncode == 0
    assert run(command, "skills", "other", "--exact", "--paths").returncode == 1
    (root / "SKILL.md").unlink()
    assert run(command, "skills", "notify", "--paths").returncode == 1
    assert json.loads(run(command, "serve", "status").stdout)["pid"] == status["pid"]
