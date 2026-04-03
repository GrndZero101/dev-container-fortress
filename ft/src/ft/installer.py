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
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

from ft.models import IntegrityConfig, ToolAsset, ToolDefinition


@dataclass(slots=True)
class ResolvedIntegrity:
    """Integrity metadata after manifest templating has been resolved."""

    checksum_url: str | None = None
    checksum_format: str = "sha256sum"
    signature_url: str | None = None
    certificate_url: str | None = None


@dataclass(slots=True)
class ResolvedAsset:
    """A concrete downloadable asset after manifest templating is resolved."""

    os: str
    arch: str
    target: str | None
    url: str
    archive: str
    binary_path: str
    checksum_asset: str | None = None
    filename: str | None = None


@dataclass(slots=True)
class InstallPlan:
    """Resolved installation plan for one tool."""

    name: str
    tool: ToolDefinition
    asset: ResolvedAsset
    integrity: ResolvedIntegrity
    os_name: str
    architecture: str
    target: str | None = None


class _TemplateContext(dict[str, str]):
    """Raise a clearer error when a manifest template references an unknown key."""

    def __missing__(self, key: str) -> str:
        raise ValueError(f"manifest template references unknown variable {key!r}")


def _render_optional(template: str | None, context: dict[str, str]) -> str | None:
    """Render an optional template-like string against the plan context."""
    if template is None:
        return None
    return template.format_map(_TemplateContext(context))


def _default_filename(url: str) -> str:
    """Derive a filename from a fully rendered download URL."""
    return Path(urlparse(url).path).name


def _resolve_asset(
    name: str,
    tool: ToolDefinition,
    asset: ToolAsset,
    *,
    os_name: str,
    architecture: str,
    target: str | None,
) -> ResolvedAsset:
    """Resolve one asset with tool and asset variables applied."""
    context: dict[str, str] = {
        "tool_name": name,
        "version": tool.version,
        "os": os_name,
        "arch": architecture,
        "system": os_name,
        "architecture": architecture,
        "target": target or "",
        **tool.variables,
        **asset.variables,
    }
    filename = _render_optional(asset.filename, context)
    if filename is not None:
        context["filename"] = filename

    url = _render_optional(asset.url_template, context) or _render_optional(asset.url, context)
    if url is None:
        raise ValueError(f"tool {name!r} has no downloadable URL for {os_name}/{architecture}")

    context.setdefault("filename", filename or _default_filename(url))
    binary_path = _render_optional(asset.binary_path, context)
    checksum_asset = _render_optional(asset.checksum_asset, context) or context["filename"]

    return ResolvedAsset(
        os=os_name,
        arch=architecture,
        target=asset.target,
        url=url,
        archive=asset.archive,
        binary_path=binary_path,
        checksum_asset=checksum_asset,
        filename=context["filename"],
    )


def _resolve_integrity(
    integrity: IntegrityConfig,
    context: dict[str, str],
) -> ResolvedIntegrity:
    """Resolve integrity URLs with the same template context as the asset."""
    return ResolvedIntegrity(
        checksum_url=_render_optional(integrity.checksum_url_template, context)
        or _render_optional(integrity.checksum_url, context),
        checksum_format=integrity.checksum_format,
        signature_url=_render_optional(integrity.signature_url_template, context)
        or _render_optional(integrity.signature_url, context),
        certificate_url=_render_optional(integrity.certificate_url_template, context)
        or _render_optional(integrity.certificate_url, context),
    )


def build_plan(
    name: str,
    tool: ToolDefinition,
    *,
    os_name: str,
    architecture: str,
    target: str | None = None,
) -> InstallPlan:
    """Build an installation plan for one tool."""
    selected_asset = tool.asset_for(
        os_name=os_name,
        architecture=architecture,
        target=target,
    )
    resolved_asset = _resolve_asset(
        name,
        tool,
        selected_asset,
        os_name=os_name,
        architecture=architecture,
        target=target,
    )
    context = {
        "tool_name": name,
        "version": tool.version,
        "os": os_name,
        "arch": architecture,
        "system": os_name,
        "architecture": architecture,
        "target": target or "",
        "filename": resolved_asset.filename or _default_filename(resolved_asset.url),
        **tool.variables,
        **selected_asset.variables,
    }
    return InstallPlan(
        name=name,
        tool=tool,
        asset=resolved_asset,
        integrity=_resolve_integrity(tool.integrity, context),
        os_name=os_name,
        architecture=architecture,
        target=target,
    )


def _download(url: str, destination: Path) -> None:
    """Download one file to disk."""
    with urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _parse_checksum_manifest(checksum_path: Path) -> tuple[dict[str, str], str | None]:
    """Parse checksum files published in common upstream formats."""
    checksums: dict[str, str] = {}
    standalone_digest: str | None = None
    for raw_line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 1:
            standalone_digest = parts[0]
            continue
        digest, filename = parts[0], parts[-1].lstrip("*")
        checksums[filename] = digest
    return checksums, standalone_digest


def _sha256(path: Path) -> str:
    """Compute the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_checksum(plan: InstallPlan, asset_path: Path, workspace: Path) -> None:
    """Verify the asset checksum when a checksum manifest is configured."""
    integrity = plan.integrity
    if not integrity.checksum_url:
        return
    if not plan.asset.checksum_asset:
        raise ValueError(
            f"tool {plan.name!r} defines checksum metadata but no checksum_asset"
        )

    checksum_path = workspace / "checksums.txt"
    _download(integrity.checksum_url, checksum_path)
    expected_checksums, standalone_digest = _parse_checksum_manifest(checksum_path)
    expected_digest = expected_checksums.get(plan.asset.checksum_asset) or standalone_digest
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
        asset_name = plan.asset.filename or _default_filename(plan.asset.url)
        asset_path = workspace / asset_name
        _download(plan.asset.url, asset_path)
        _verify_checksum(plan, asset_path, workspace)
        binary_path = _extract_asset(plan, asset_path, workspace)
        installed_path = _install_binary(binary_path, destination_root)

    if healthcheck:
        _run_healthcheck(plan.tool.healthcheck, destination_root)
    return installed_path
