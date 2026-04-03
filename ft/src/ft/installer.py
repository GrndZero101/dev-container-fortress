"""Download, verify, and install tools described in the downloader manifest."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen
import zipfile

from ft.models import ToolAsset, ToolDefinition


@dataclass(slots=True)
class InstallPlan:
    """Resolved installation plan for one tool."""

    name: str
    tool: ToolDefinition
    asset: ToolAsset
    os_name: str
    architecture: str


def build_plan(
    name: str,
    tool: ToolDefinition,
    *,
    os_name: str,
    architecture: str,
) -> InstallPlan:
    """Build an installation plan for one tool."""
    return InstallPlan(
        name=name,
        tool=tool,
        asset=tool.asset_for(os_name=os_name, architecture=architecture),
        os_name=os_name,
        architecture=architecture,
    )


def _download(url: str, destination: Path) -> None:
    """Download one file to disk."""
    with urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _parse_checksum_manifest(checksum_path: Path) -> dict[str, str]:
    """Parse a standard sha256sum-style manifest."""
    checksums: dict[str, str] = {}
    for raw_line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        digest, filename = parts[0], parts[-1].lstrip("*")
        checksums[filename] = digest
    return checksums


def _sha256(path: Path) -> str:
    """Compute the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_checksum(plan: InstallPlan, asset_path: Path, workspace: Path) -> None:
    """Verify the asset checksum when a checksum manifest is configured."""
    integrity = plan.tool.integrity
    if not integrity.checksum_url:
        return
    if not plan.asset.checksum_asset:
        raise ValueError(
            f"tool {plan.name!r} defines checksum metadata but no checksum_asset"
        )

    checksum_path = workspace / "checksums.txt"
    _download(integrity.checksum_url, checksum_path)
    expected_checksums = _parse_checksum_manifest(checksum_path)
    expected_digest = expected_checksums.get(plan.asset.checksum_asset)
    if expected_digest is None:
        raise RuntimeError(
            f"checksum manifest does not contain {plan.asset.checksum_asset!r}"
        )

    actual_digest = _sha256(asset_path)
    if actual_digest != expected_digest:
        raise RuntimeError(
            f"checksum verification failed for {plan.asset.checksum_asset}: "
            f"expected {expected_digest}, got {actual_digest}"
        )


def _extract_asset(plan: InstallPlan, asset_path: Path, workspace: Path) -> Path:
    """Extract or stage an asset into the temporary workspace."""
    unpack_dir = workspace / "unpacked"
    unpack_dir.mkdir(parents=True, exist_ok=True)

    archive_type = plan.asset.archive
    if archive_type == "tar.gz":
        with tarfile.open(asset_path, mode="r:gz") as archive:
            archive.extractall(unpack_dir)
    elif archive_type == "zip":
        with zipfile.ZipFile(asset_path) as archive:
            archive.extractall(unpack_dir)
    elif archive_type == "raw":
        target = unpack_dir / Path(plan.asset.binary_path).name
        shutil.copy2(asset_path, target)
    else:
        raise ValueError(f"unsupported archive type: {archive_type}")

    return unpack_dir / plan.asset.binary_path


def _install_binary(binary_path: Path, install_root: Path) -> Path:
    """Install one executable into the target root."""
    install_root.mkdir(parents=True, exist_ok=True)
    destination = install_root / binary_path.name
    shutil.copy2(binary_path, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    return destination


def _run_healthcheck(command: list[str], install_root: Path) -> None:
    """Run the tool healthcheck command."""
    if not command:
        return

    environment = os.environ.copy()
    environment["PATH"] = f"{install_root}:{environment.get('PATH', '')}"
    subprocess.run(command, check=True, env=environment)


def install_tool(
    plan: InstallPlan,
    *,
    install_root: Path | None = None,
    healthcheck: bool = True,
) -> Path:
    """Install the resolved tool asset into the destination root."""
    destination_root = Path(install_root or plan.tool.install_root)
    with tempfile.TemporaryDirectory(prefix=f"{plan.name}-") as temp_dir:
        workspace = Path(temp_dir)
        asset_path = workspace / Path(plan.asset.url).name
        _download(plan.asset.url, asset_path)
        _verify_checksum(plan, asset_path, workspace)
        binary_path = _extract_asset(plan, asset_path, workspace)
        installed_path = _install_binary(binary_path, destination_root)

    if healthcheck:
        _run_healthcheck(plan.tool.healthcheck, destination_root)
    return installed_path
