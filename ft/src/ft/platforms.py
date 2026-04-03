"""Platform helpers for ft."""

from __future__ import annotations

import platform


def detect_architecture() -> str:
    """Return the normalized architecture for the running interpreter.

    Returns:
        A normalized architecture string such as ``amd64`` or ``arm64``.
    """
    machine_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    return machine_map.get(platform.machine(), platform.machine().lower())


def detect_system() -> str:
    """Return the normalized operating system for the running interpreter.

    Returns:
        A normalized operating system string such as ``linux``.
    """
    system_map = {
        "Linux": "linux",
        "Darwin": "darwin",
    }
    return system_map.get(platform.system(), platform.system().lower())
