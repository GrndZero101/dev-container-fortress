"""Manifest-driven tool installer skeleton for container targets."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
import sys
import tomllib


def detect_platform() -> tuple[str, str]:
    """Return normalized OS and architecture identifiers."""
    system_map = {
        "Linux": "linux",
        "Darwin": "darwin",
    }
    machine_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    system = system_map.get(platform.system(), platform.system().lower())
    machine = machine_map.get(platform.machine(), platform.machine().lower())
    return system, machine


def load_manifest(path: Path) -> dict[str, object]:
    """Load the TOML tool manifest from disk."""
    with path.open("rb") as handle:
        return tomllib.load(handle)


def iter_enabled_tools(manifest: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    """Return enabled tool entries from the manifest."""
    tools = manifest.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError("manifest [tools] table is missing or invalid")

    enabled: list[tuple[str, dict[str, object]]] = []
    for name, config in sorted(tools.items()):
        if not isinstance(config, dict):
            continue
        if config.get("enabled", True):
            enabled.append((name, config))
    return enabled


def main(argv: list[str]) -> int:
    """Parse arguments and print the planned tool installation set."""
    parser = argparse.ArgumentParser(
        description="Plan pinned tool installation for container targets."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to the tool manifest TOML file.",
    )
    parser.add_argument(
        "--target",
        choices=("ubuntu", "alpine"),
        required=True,
        help="Container target being built.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    system_name, arch = detect_platform()

    print(f"Target: {args.target}")
    print(f"Host platform: {system_name}/{arch}")
    print("Planned tools:")

    for name, config in iter_enabled_tools(manifest):
        version = config.get("version", "latest")
        print(f"- {name}: {version}")

    print()
    print("Installer implementation status: planning only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

