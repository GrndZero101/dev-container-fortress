"""Host-side browser bridge for workspace containers."""

from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import sys


def serve(socket_path: Path, opener_command: list[str]) -> int:
    """Serve one simple Unix socket that forwards URLs into the host browser."""
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
                payload = connection.recv(8192).decode("utf-8").strip()
                if not payload:
                    connection.sendall(b"ERR empty\n")
                    continue
                result = subprocess.run(
                    [*opener_command, payload],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    connection.sendall(b"OK\n")
                else:
                    connection.sendall(f"ERR {result.returncode}\n".encode("utf-8"))
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
