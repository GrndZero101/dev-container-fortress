"""Host-side browser bridge for workspace containers and devcontainers.

A container cannot reach the host browser itself, so the host runs a small
broker on a Unix socket that the container sees through a bind mount. The
container's ``ft-host-browser-open`` helper writes one URL to the socket, and
the broker hands it to the host opener (``xdg-open``, ``wslview``, or
``$BROWSER``).

The container is less trusted than the host, so the broker accepts only an
absolute ``http`` or ``https`` URL: a ``file:`` path, an ``ms-settings:`` or
other custom-scheme link, or a payload that is not a URL never reaches the
opener.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Where the bridge appears inside a container, shared by ``ft workspace`` and
# the rendered devcontainers. The image ships the helper.
CONTAINER_BRIDGE_DIR = "/tmp/dev-fortress-host-services"
SOCKET_NAME = "browser-open.sock"
CONTAINER_SOCKET = f"{CONTAINER_BRIDGE_DIR}/{SOCKET_NAME}"
CONTAINER_OPEN_COMMAND = "/usr/local/bin/ft-host-browser-open"
# The environment that sends a container's browser launches through the helper.
SOCKET_ENV = "DEV_FORTRESS_HOST_BROWSER_SOCKET"
BROWSER_ENV_NAMES = ("BROWSER", "GH_BROWSER")

# Part of the running broker's signature, so starting a container after an
# upgrade replaces a broker that runs older code, such as one without URL
# validation. Bump it when the broker's behaviour changes.
BRIDGE_VERSION = 2

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_PAYLOAD_BYTES = 8192


def validate_url(payload: bytes) -> str:
    """Return the URL a payload carries, if the broker may open it.

    Args:
        payload: The bytes one client sent, with an optional trailing newline.

    Returns:
        The URL.

    Raises:
        ValueError: When the payload is empty, not UTF-8, holds whitespace or
            control characters, or is not an absolute ``http`` or ``https``
            URL with a host.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("not UTF-8") from error
    url = text.removesuffix("\n").removesuffix("\r")
    if not url:
        raise ValueError("empty")
    if any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in url):
        raise ValueError("whitespace or control characters")
    try:
        parts = urlsplit(url)
    except ValueError as error:
        raise ValueError("not a URL") from error
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"scheme not allowed: {parts.scheme or 'none'}")
    if not parts.hostname:
        raise ValueError("no host")
    return url


def handle_payload(payload: bytes, opener_command: list[str]) -> bytes:
    """Validate one payload, open it when allowed, and return the reply.

    Args:
        payload: The bytes one client sent.
        opener_command: The host opener; the URL is appended as one argument.

    Returns:
        ``OK``, ``ERR invalid: <reason>``, or ``ERR <exit code>``, each with a
        trailing newline.
    """
    try:
        url = validate_url(payload)
    except ValueError as error:
        return f"ERR invalid: {error}\n".encode()
    result = subprocess.run(
        [*opener_command, url],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        return b"OK\n"
    return f"ERR {result.returncode}\n".encode()


def serve(socket_path: Path, opener_command: list[str]) -> int:
    """Serve one Unix socket that forwards validated URLs to the host browser."""
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(socket_path))
        socket_path.chmod(0o600)
        server.listen()
        while True:
            connection, _ = server.accept()
            with connection:
                try:
                    connection.settimeout(5.0)
                    payload = connection.recv(MAX_PAYLOAD_BYTES)
                    connection.sendall(handle_payload(payload, opener_command))
                except OSError:
                    # One misbehaving client must not stop the broker.
                    continue
    finally:
        server.close()
        if socket_path.exists():
            socket_path.unlink()


def main(argv: list[str] | None = None) -> int:
    """Run the browser bridge server from the command line."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(
            "usage: python -m ft.browser_bridge <socket-path> <opener> [args...]",
            file=sys.stderr,
        )
        return 2
    return serve(Path(args[0]), args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
