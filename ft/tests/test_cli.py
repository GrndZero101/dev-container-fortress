"""CLI and installer tests for ft."""

from __future__ import annotations

from pathlib import Path
import tarfile

from typer.testing import CliRunner

from ft.cli import _effective_install_root, app
from ft.installer import build_plan, install_tool
from ft.models import IntegrityConfig, ToolAsset, ToolDefinition

runner = CliRunner()


def test_plan_uses_environment_defaults(monkeypatch: object) -> None:
    """The CLI should honor environment-backed settings defaults."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    monkeypatch.setenv("FT_MANIFEST", str(manifest_path))
    monkeypatch.setenv("FT_TARGET", "ubuntu")
    monkeypatch.setenv("FT_SYSTEM", "linux")
    monkeypatch.setenv("FT_ARCHITECTURE", "amd64")

    result = runner.invoke(app, ["plan", "--tool", "atuin"])

    assert result.exit_code == 0
    assert "atuin plan" in result.stdout
    assert "18.13.6" in result.stdout
    assert "linux/amd64" in result.stdout


def test_effective_install_root_falls_back_to_user_local(monkeypatch: object) -> None:
    """A non-writable default install root should fall back to ~/.local/bin."""
    monkeypatch.setattr("ft.cli._is_writable_directory", lambda path: False)
    monkeypatch.setattr(Path, "home", lambda: Path("/tmp/test-home"))

    install_root = _effective_install_root(Path("/usr/local/bin"), None)

    assert install_root == Path("/tmp/test-home/.local/bin")


def test_install_tool_from_local_artifacts(tmp_path: Path) -> None:
    """The installer should extract, verify, and install a local tarball."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    binary_path = source_dir / "demo-tool"
    binary_path.write_text("#!/bin/sh\necho demo-tool version 1.0.0\n", encoding="utf-8")
    binary_path.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname="demo-tool")

    checksum_path = tmp_path / "checksums.txt"
    checksum_path.write_text(
        f"{_sha256(archive_path)}  demo-tool.tar.gz\n",
        encoding="utf-8",
    )

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "bin",
        healthcheck=["demo-tool", "version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan("demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu")

    installed_path = install_tool(plan, healthcheck=True)

    assert installed_path.exists()
    assert installed_path.read_text(encoding="utf-8").startswith("#!/bin/sh")


def test_install_tool_accepts_digest_only_checksum_files(tmp_path: Path) -> None:
    """Digest-only checksum files should verify successfully for single-asset releases."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    binary_path = source_dir / "demo-tool"
    binary_path.write_text("#!/bin/sh\necho demo-tool version 1.0.0\n", encoding="utf-8")
    binary_path.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname="demo-tool")

    checksum_path = tmp_path / "demo-tool.tar.gz.sha256"
    checksum_path.write_text(f"{_sha256(archive_path)}\n", encoding="utf-8")

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "bin",
        healthcheck=["demo-tool", "version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan("demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu")

    installed_path = install_tool(plan, healthcheck=True)

    assert installed_path.exists()
    assert installed_path.name == "demo-tool"


def test_build_plan_renders_template_variables() -> None:
    """Plan building should render asset and integrity templates from variables."""
    tool = ToolDefinition(
        description="Demo tool",
        version="1.2.3",
        install_root=Path("/usr/local/bin"),
        variables={"github_repo": "example/demo", "release_tag": "v1.2.3"},
        integrity=IntegrityConfig(
            checksum_url_template=(
                "https://github.com/{github_repo}/releases/download/{release_tag}/{filename}.sha256"
            )
        ),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                filename="demo-tool-linux-amd64.tar.gz",
                url_template=(
                    "https://github.com/{github_repo}/releases/download/{release_tag}/{filename}"
                ),
                archive="tar.gz",
                binary_path="demo-tool",
            )
        ],
    )

    plan = build_plan("demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu")

    assert plan.asset.url.endswith("/demo-tool-linux-amd64.tar.gz")
    assert plan.asset.checksum_asset == "demo-tool-linux-amd64.tar.gz"
    assert plan.integrity.checksum_url.endswith("/demo-tool-linux-amd64.tar.gz.sha256")


def _sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a local file."""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
