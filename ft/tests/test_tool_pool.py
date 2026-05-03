"""Tests for the canonical tool-pool manifest."""

from __future__ import annotations

from pathlib import Path
import re

from ft.manifest import load_manifest
from ft.tool_pool import load_tool_pool_manifest


def _repo_root() -> Path:
    """Return the repository root for test fixtures."""
    return Path(__file__).resolve().parents[2]


def _brewfile_formulae(path: Path) -> list[str]:
    """Extract formula names from one Brewfile.

    Args:
        path: Brewfile path.

    Returns:
        Formula names in file order.
    """
    pattern = re.compile(r'^brew\s+"([^"]+)"\s*$')
    formulae: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            formulae.append(match.group(1))
    return formulae


def _host_playbook_linuxbrew_formulae(path: Path) -> list[str]:
    """Extract the Linuxbrew formula list from the host playbook.

    Args:
        path: Host playbook path.

    Returns:
        Linuxbrew formula names in file order.
    """
    start_marker = "    dev_container_fortress_homebrew_linux_packages:"
    formula_prefix = "      - "
    collecting = False
    formulae: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == start_marker:
            collecting = True
            continue
        if collecting and line.startswith(formula_prefix):
            formulae.append(line[len(formula_prefix) :].strip())
            continue
        if collecting and not line.startswith("      "):
            break
    return formulae


def _enabled_downloader_tools(path: Path) -> list[str]:
    """Return enabled downloader-managed tool names in stable order."""
    manifest = load_manifest(path)
    return [name for name, _definition in manifest.enabled_tools()]


def test_tool_pool_manifest_loads_expected_platform_groups() -> None:
    """The tool-pool manifest should expose common and platform overlays."""
    manifest_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    manifest = load_tool_pool_manifest(manifest_path)

    assert "yazi" in manifest.homebrew.common.formulae
    assert "reattach-to-user-namespace" in manifest.homebrew.macos.formulae
    assert "tmux" in manifest.downloader.common.target_tools
    assert "tenv" in manifest.downloader.common.implemented_tools
    assert "ft" in manifest.containers.common.command_checks
    assert manifest.homebrew.linux.formulae == []
    assert manifest.homebrew.wsl.formulae == []


def test_ansible_linuxbrew_formulae_match_canonical_linux_pool() -> None:
    """The Ansible Linuxbrew list should match the canonical Linux tool pool."""
    manifest_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    playbook_path = _repo_root() / "ansible" / "playbooks" / "host.yml"
    manifest = load_tool_pool_manifest(manifest_path)
    ansible_formulae = _host_playbook_linuxbrew_formulae(playbook_path)
    assert ansible_formulae == manifest.homebrew.formulae_for("linux")


def test_base_brewfile_matches_canonical_common_pool() -> None:
    """The base Brewfile should track the canonical common Homebrew pool."""
    manifest_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    brewfile_path = _repo_root() / "brew" / "Brewfile"
    manifest = load_tool_pool_manifest(manifest_path)

    assert _brewfile_formulae(brewfile_path) == manifest.homebrew.common.formulae


def test_macos_brewfile_matches_canonical_macos_overlay() -> None:
    """The macOS Brewfile should track the canonical macOS-only overlay."""
    manifest_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    brewfile_path = _repo_root() / "brew" / "Brewfile.macos"
    manifest = load_tool_pool_manifest(manifest_path)

    assert _brewfile_formulae(brewfile_path) == manifest.homebrew.macos.formulae


def test_enabled_downloader_manifest_matches_implemented_common_tool_pool() -> None:
    """The downloader manifest should match the implemented shared tool subset."""
    tool_pool_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    downloader_manifest_path = _repo_root() / "ft" / "tools" / "tools.toml"
    tool_pool = load_tool_pool_manifest(tool_pool_path)

    assert _enabled_downloader_tools(downloader_manifest_path) == (
        tool_pool.downloader.implemented_tools_for("linux")
    )


def test_implemented_downloader_subset_fits_declared_target_pool() -> None:
    """Implemented downloader tools should stay within the target parity set."""
    tool_pool_path = _repo_root() / "ft" / "tools" / "tool-pool.toml"
    tool_pool = load_tool_pool_manifest(tool_pool_path)

    implemented = set(tool_pool.downloader.implemented_tools_for("linux"))
    target = set(tool_pool.downloader.target_tools_for("linux"))

    assert implemented.issubset(target)
