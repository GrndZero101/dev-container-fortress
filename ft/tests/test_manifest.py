"""Tests for ft manifest parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from ft.installer import _release_tag_from_latest_redirect, build_plan
from ft.models import ToolAsset, ToolDefinition
from ft.manifest import load_manifest


def test_load_manifest_reads_multiple_tool_definitions() -> None:
    """Manifest loading should expose the configured core tools."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    assert {
        "tenv",
        "starship",
        "zoxide",
        "atuin",
        "bat",
        "gum",
        "glow",
        "bats",
        "fd",
        "jq",
        "lazygit",
        "neovim",
        "oh-my-posh",
        "ripgrep",
    }.issubset(manifest.tools)
    assert manifest.tools["starship"].version == "1.24.2"
    assert manifest.tools["zoxide"].version == "0.9.8"
    assert manifest.tools["atuin"].version == "18.13.6"
    assert manifest.tools["bat"].version == "0.26.1"
    assert manifest.tools["gum"].version == "0.16.0"
    assert manifest.tools["glow"].version == "2.1.2"
    assert manifest.tools["bats"].version == "1.13.0"
    assert manifest.tools["fd"].version == "10.4.2"
    assert manifest.tools["jq"].version == "1.8.1"
    assert manifest.tools["lazygit"].version == "0.61.1"
    assert manifest.tools["neovim"].version == "0.12.1"
    assert manifest.tools["oh-my-posh"].version == "29.10.0"
    assert manifest.tools["ripgrep"].version == "15.1.0"


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


def test_build_plan_can_resolve_latest_github_release() -> None:
    """Latest-resolution mode should update templated filenames and URLs."""
    tool = ToolDefinition(
        description="Demo tool",
        version="1.2.3",
        version_source="github_latest",
        release_tag_prefix="v",
        install_root=Path("/usr/local/bin"),
        variables={
            "github_repo": "example/demo",
            "asset_prefix": "demo-{version}",
        },
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                filename="{asset_prefix}-linux-amd64.tar.gz",
                url_template=(
                    "https://github.com/{github_repo}/releases/download/{release_tag}/{filename}"
                ),
                archive="tar.gz",
                binary_path="demo-tool",
            )
        ],
    )

    plan = build_plan(
        "demo-tool",
        tool,
        os_name="linux",
        architecture="amd64",
        target="ubuntu",
        resolve_latest=True,
        release_lookup=lambda _repo: "v9.8.7",
    )

    assert plan.resolved_version == "9.8.7"
    assert plan.resolved_release_tag == "v9.8.7"
    assert plan.asset.filename == "demo-9.8.7-linux-amd64.tar.gz"
    assert plan.asset.url.endswith("/v9.8.7/demo-9.8.7-linux-amd64.tar.gz")


def test_build_plan_supports_raw_binary_assets() -> None:
    """Raw assets should preserve the desired installed binary name."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    plan = build_plan(
        "jq",
        manifest.tools["jq"],
        os_name="linux",
        architecture="amd64",
        target="ubuntu",
    )

    assert plan.asset.archive == "raw"
    assert plan.asset.filename == "jq-linux-amd64"
    assert plan.asset.binary_path == "jq"
    assert plan.asset.url.endswith("/jq-1.8.1/jq-linux-amd64")


def test_build_plan_supports_raw_binary_rename_assets() -> None:
    """Raw assets should be able to install under a different binary name."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    plan = build_plan(
        "oh-my-posh",
        manifest.tools["oh-my-posh"],
        os_name="linux",
        architecture="amd64",
        target="ubuntu",
    )

    assert plan.asset.archive == "raw"
    assert plan.asset.filename == "posh-linux-amd64"
    assert plan.asset.binary_path == "oh-my-posh"
    assert plan.asset.url.endswith("/v29.10.0/posh-linux-amd64")


def test_enabled_tools_can_be_target_scoped() -> None:
    """Target-scoped downloader tools should only appear for matching targets."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    assert "ripgrep" in {name for name, _ in manifest.enabled_tools(target="ubuntu")}
    assert "ripgrep" not in {name for name, _ in manifest.enabled_tools(target="alpine")}
    assert "neovim" in {name for name, _ in manifest.enabled_tools(target="ubuntu")}
    assert "neovim" not in {name for name, _ in manifest.enabled_tools(target="alpine")}


def test_build_plan_includes_neovim_runtime_support_paths() -> None:
    """Neovim plans should carry lib/share runtime directories with the binary."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    manifest = load_manifest(manifest_path)

    plan = build_plan(
        "neovim",
        manifest.tools["neovim"],
        os_name="linux",
        architecture="amd64",
        target="ubuntu",
    )

    assert plan.asset.binary_path == "nvim-linux-x86_64/bin/nvim"
    assert plan.asset.support_paths == [
        "nvim-linux-x86_64/lib",
        "nvim-linux-x86_64/share",
    ]


def test_release_tag_from_latest_redirect_extracts_tag() -> None:
    """Latest-release redirect parsing should recover the GitHub release tag."""
    assert _release_tag_from_latest_redirect(
        "https://github.com/example/demo/releases/tag/v9.8.7"
    ) == "v9.8.7"
