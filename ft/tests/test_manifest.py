"""Tests for ft manifest parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from ft.installer import build_plan
from ft.manifest import load_manifest


def test_load_manifest_reads_tenv_definition() -> None:
    """Manifest loading should expose the configured tenv tool."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    tool = manifest.tools["tenv"]
    asset = tool.asset_for(os_name="linux", architecture="amd64")

    assert tool.version == "4.8.3"
    assert asset.archive == "tar.gz"
    assert asset.checksum_asset == "tenv_v4.8.3_Linux_x86_64.tar.gz"


def test_load_manifest_rejects_missing_tools(tmp_path: Path) -> None:
    """Manifest loading should fail when no tools are defined."""
    manifest_path = tmp_path / "tools.toml"
    manifest_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty \\[tools\\] table"):
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
    )

    assert plan.asset.checksum_asset == "tenv_v4.8.3_Linux_arm64.tar.gz"
