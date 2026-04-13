"""Tests for ft manifest parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from ft.installer import build_plan
from ft.manifest import load_manifest


def test_load_manifest_reads_multiple_tool_definitions() -> None:
    """Manifest loading should expose the configured core tools."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    assert {"tenv", "starship", "zoxide", "atuin", "gum", "glow", "bats"}.issubset(
        manifest.tools
    )
    assert manifest.tools["starship"].version == "1.24.2"
    assert manifest.tools["zoxide"].version == "0.9.8"
    assert manifest.tools["atuin"].version == "18.13.6"
    assert manifest.tools["gum"].version == "0.16.0"
    assert manifest.tools["glow"].version == "2.1.1"
    assert manifest.tools["bats"].version == "1.13.0"


def test_load_manifest_rejects_missing_tools(tmp_path: Path) -> None:
    """Manifest loading should fail when no tools are defined."""
    manifest_path = tmp_path / "tools.toml"
    manifest_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=r"non-empty \[tools\] table"):
        load_manifest(manifest_path)


def test_build_plan_selects_arm64_asset() -> None:
    """Plan building should select the matching arm64 asset."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    plan = build_plan(
        "tenv",
        manifest.tools["tenv"],
        os_name="linux",
        architecture="arm64",
        target="ubuntu",
    )

    assert plan.asset.filename == "tenv_v4.8.3_Linux_arm64.tar.gz"
    assert plan.asset.url.endswith("/tenv_v4.8.3_Linux_arm64.tar.gz")
    assert plan.integrity.checksum_url.endswith("/tenv_v4.8.3_checksums.txt")


def test_build_plan_prefers_target_specific_asset() -> None:
    """Target-specific assets should let Ubuntu and Alpine diverge cleanly."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    ubuntu_plan = build_plan(
        "atuin",
        manifest.tools["atuin"],
        os_name="linux",
        architecture="amd64",
        target="ubuntu",
    )
    alpine_plan = build_plan(
        "atuin",
        manifest.tools["atuin"],
        os_name="linux",
        architecture="amd64",
        target="alpine",
    )

    assert ubuntu_plan.asset.filename == "atuin-x86_64-unknown-linux-gnu.tar.gz"
    assert alpine_plan.asset.filename == "atuin-x86_64-unknown-linux-musl.tar.gz"
    assert ubuntu_plan.asset.binary_path == "atuin-x86_64-unknown-linux-gnu/atuin"
    assert alpine_plan.asset.binary_path == "atuin-x86_64-unknown-linux-musl/atuin"
