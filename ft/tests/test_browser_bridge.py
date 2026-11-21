"""Tests for the host browser bridge and the command that starts it."""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
from ft.browser_bridge import (
    BRIDGE_VERSION,
    SOCKET_NAME,
    handle_payload,
    serve,
    validate_url,
)
from ft.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _recording_opener(record: Path) -> list[str]:
    """Return an opener command that writes the URL it receives to ``record``.

    Args:
        record: The file to write.

    Returns:
        The command; the bridge appends the URL as its last argument.
    """
    return ["sh", "-c", 'printf %s "$1" > "$0"', str(record)]


def _send(socket_path: Path, payload: bytes) -> str:
    """Send one payload to a bridge socket and return its reply.

    Args:
        socket_path: The bridge socket.
        payload: The bytes to send.

    Returns:
        The reply without its trailing newline.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5.0)
        client.connect(str(socket_path))
        client.sendall(payload)
        return client.recv(1024).decode("utf-8").strip()


def _wait_for(path: Path) -> None:
    """Wait up to five seconds for a path to appear.

    Args:
        path: The path to wait for.
    """
    deadline = time.time() + 5.0
    while not path.exists():
        assert time.time() < deadline, f"{path} never appeared"
        time.sleep(0.02)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\n",
        b"not a url",
        b"example.com",
        b"/etc/passwd",
        b"--help",
        b"https://",
        b"https:///path-without-host",
        b"\xff\xfe",
    ],
)
def test_bridge_rejects_a_non_url_payload(payload: bytes) -> None:
    """Empty text, bare words, paths, flags, hostless URLs, and bad UTF-8 fail."""
    with pytest.raises(ValueError):
        validate_url(payload)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "FILE:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com/file",
        "ms-settings:display",
        "vscode://ms-vscode-remote.remote-containers/open",
        "smb://attacker.example/share",
        "mailto:someone@example.com",
    ],
)
def test_bridge_rejects_non_http_schemes(url: str) -> None:
    """Only http and https reach the host opener."""
    with pytest.raises(ValueError, match="scheme not allowed"):
        validate_url(url.encode())


@pytest.mark.parametrize(
    "payload",
    [
        b"https://example.com/ two-words",
        b"https://example.com\nfile:///etc/passwd",
        b"https://example.com\tx",
        b"https://example.com/\x00",
        b"https://example.com/\x1b[31m",
        b"https://example.com/\x7f",
    ],
)
def test_bridge_rejects_whitespace_and_control_characters(payload: bytes) -> None:
    """A payload cannot smuggle a second URL or an argument past the check."""
    with pytest.raises(ValueError, match="whitespace or control"):
        validate_url(payload)


@pytest.mark.parametrize(
    ("payload", "url"),
    [
        (b"https://github.com/login/device\n", "https://github.com/login/device"),
        (
            b"http://localhost:8080/callback?code=1",
            "http://localhost:8080/callback?code=1",
        ),
        (b"HTTPS://Example.com/a#b\r\n", "HTTPS://Example.com/a#b"),
    ],
)
def test_bridge_accepts_http_and_https_urls(payload: bytes, url: str) -> None:
    """An http or https URL with a host passes unchanged, minus the newline."""
    assert validate_url(payload) == url


def test_bridge_rejects_without_running_the_opener(tmp_path: Path) -> None:
    """A rejected payload never reaches the opener; an allowed one does."""
    record = tmp_path / "opened"
    opener = _recording_opener(record)

    reply = handle_payload(b"file:///etc/passwd\n", opener)
    assert reply == b"ERR invalid: scheme not allowed: file\n"
    assert not record.exists()

    assert handle_payload(b"https://example.com/x\n", opener) == b"OK\n"
    assert record.read_text(encoding="utf-8") == "https://example.com/x"


def test_bridge_reports_the_opener_exit_code() -> None:
    """A failing opener is reported, not hidden."""
    assert handle_payload(b"https://example.com\n", ["sh", "-c", "exit 3"]) == (
        b"ERR 3\n"
    )


def test_bridge_rejects_over_the_socket_and_keeps_serving(tmp_path: Path) -> None:
    """The broker answers each client and survives bad payloads."""
    record = tmp_path / "opened"
    socket_path = tmp_path / "b.sock"
    thread = threading.Thread(
        target=serve, args=(socket_path, _recording_opener(record)), daemon=True
    )
    thread.start()
    _wait_for(socket_path)
    assert socket_path.stat().st_mode & 0o777 == 0o600

    assert _send(socket_path, b"file:///etc/passwd\n").startswith("ERR invalid")
    assert _send(socket_path, b"\xff\n").startswith("ERR invalid")
    assert not record.exists()
    assert _send(socket_path, b"https://example.com/ok\n") == "OK"
    assert record.read_text(encoding="utf-8") == "https://example.com/ok"


def test_browser_bridge_command_without_an_opener_only_makes_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no host opener the command creates the folder and still succeeds."""
    monkeypatch.setattr("ft.cli._workspace_host_browser_opener_command", lambda: None)
    folder = tmp_path / "bridge"
    result = runner.invoke(app, ["devcontainer", "browser-bridge", str(folder)])
    assert result.exit_code == 0, result.output
    assert folder.is_dir()
    assert not (folder / SOCKET_NAME).exists()
    assert "no host browser opener" in result.output


def test_browser_bridge_command_starts_a_validating_broker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command starts the real broker once and reuses it on a second run."""
    record = tmp_path / "opened"
    opener = _recording_opener(record)
    monkeypatch.setenv("DEV_FORTRESS_HOST_BROWSER_OPENER", shlex.join(opener))
    folder = tmp_path / "bridge"
    pid_path = folder / "browser-open.pid"
    try:
        result = runner.invoke(app, ["devcontainer", "browser-bridge", str(folder)])
        assert result.exit_code == 0, result.output
        socket_path = folder / SOCKET_NAME
        assert socket_path.exists()
        first_pid = pid_path.read_text(encoding="utf-8").strip()
        signature = json.loads(
            (folder / "browser-open.command").read_text(encoding="utf-8")
        )
        assert signature["bridge"] == BRIDGE_VERSION

        assert _send(socket_path, b"javascript:alert(1)\n").startswith("ERR invalid")
        assert not record.exists()
        assert _send(socket_path, b"https://example.com/device\n") == "OK"
        assert record.read_text(encoding="utf-8") == "https://example.com/device"

        result = runner.invoke(app, ["devcontainer", "browser-bridge", str(folder)])
        assert result.exit_code == 0, result.output
        assert pid_path.read_text(encoding="utf-8").strip() == first_pid
    finally:
        if pid_path.is_file():
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid_path.read_text(encoding="utf-8")), signal.SIGTERM)


def test_browser_bridge_command_replaces_a_broker_from_older_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broker whose signature lacks the current bridge version is replaced."""
    monkeypatch.setattr(
        "ft.cli._workspace_host_browser_opener_command", lambda: ["true"]
    )
    folder = tmp_path / "bridge"
    folder.mkdir()
    pid_path = folder / "browser-open.pid"
    # A stand-in for a broker started by older code, with the old signature.
    stale = subprocess.Popen(["sleep", "60"])
    try:
        pid_path.write_text(f"{stale.pid}\n", encoding="utf-8")
        (folder / "browser-open.command").write_text('["true"]\n', encoding="utf-8")
        (folder / SOCKET_NAME).touch()

        result = runner.invoke(app, ["devcontainer", "browser-bridge", str(folder)])
        assert result.exit_code == 0, result.output
        assert stale.wait(timeout=5) == -signal.SIGTERM
        assert pid_path.read_text(encoding="utf-8").strip() != str(stale.pid)
    finally:
        stale.kill()
        stale.wait()
        if pid_path.is_file():
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid_path.read_text(encoding="utf-8")), signal.SIGTERM)
