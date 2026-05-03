"""Download, verify, and install tools described in the downloader manifest."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from typing import Callable
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
    support_paths: list[str]
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
    resolved_version: str = ""
    resolved_release_tag: str | None = None


@dataclass(slots=True)
class CachedAsset:
    """Resolved cache paths for one downloadable tool asset."""

    cache_dir: Path
    metadata_path: Path
    asset_path: Path
    checksum_path: Path | None = None


class _TemplateContext(dict[str, str]):
    """Raise a clearer error when a manifest template references an unknown key."""

    def __missing__(self, key: str) -> str:
        raise ValueError(f"manifest template references unknown variable {key!r}")


def _render_optional(template: str | None, context: dict[str, str]) -> str | None:
    """Render an optional template-like string against the plan context."""
    if template is None:
        return None
    return template.format_map(_TemplateContext(context))


def _render_variables(variables: dict[str, str], context: dict[str, str]) -> dict[str, str]:
    """Render manifest variables, allowing references to earlier resolved keys."""
    pending = dict(variables)
    resolved: dict[str, str] = {}
    while pending:
        progressed = False
        for key in list(pending):
            value = pending[key]
            try:
                rendered = value.format_map(_TemplateContext({**context, **resolved}))
            except ValueError:
                continue
            resolved[key] = rendered
            pending.pop(key)
            progressed = True
        if progressed:
            continue
        unresolved = ", ".join(sorted(pending))
        raise ValueError(f"manifest variables contain unresolved templates: {unresolved}")
    return resolved


def _default_filename(url: str) -> str:
    """Derive a filename from a fully rendered download URL."""
    return Path(urlparse(url).path).name


def _release_tag_from_latest_redirect(final_url: str) -> str:
    """Extract a GitHub release tag from a resolved /releases/latest URL."""
    parsed = urlparse(final_url)
    marker = "/releases/tag/"
    if marker not in parsed.path:
        raise RuntimeError(
            f"GitHub latest release redirect did not resolve to a tag URL: {final_url}"
        )
    return parsed.path.rsplit(marker, maxsplit=1)[-1]


def _latest_github_release_tag(github_repo: str) -> str:
    """Return the latest GitHub release tag for one repository."""
    request_url = f"https://github.com/{github_repo}/releases/latest"
    with urlopen(request_url, timeout=30) as response:
        return _release_tag_from_latest_redirect(response.geturl())


def _resolve_version(
    tool: ToolDefinition,
    *,
    release_lookup: Callable[[str], str] | None = None,
    resolve_latest: bool,
) -> tuple[str, str | None]:
    """Return the effective version and release tag for one tool."""
    if tool.version_source == "pinned":
        return tool.version, None
    if not resolve_latest:
        return tool.version, f"{tool.release_tag_prefix}{tool.version}"

    github_repo = tool.variables.get("github_repo")
    if not github_repo:
        raise ValueError(
            "github_latest tools must define variables.github_repo in the manifest"
        )

    lookup = release_lookup or _latest_github_release_tag
    release_tag = lookup(github_repo)
    version = release_tag
    if tool.release_tag_prefix and release_tag.startswith(tool.release_tag_prefix):
        version = release_tag.removeprefix(tool.release_tag_prefix)
    return version, release_tag


def _resolve_asset(
    name: str,
    tool: ToolDefinition,
    asset: ToolAsset,
    *,
    os_name: str,
    architecture: str,
    target: str | None,
    resolved_version: str,
    resolved_release_tag: str | None,
) -> ResolvedAsset:
    """Resolve one asset with tool and asset variables applied."""
    context: dict[str, str] = {
        "tool_name": name,
        "version": resolved_version,
        "os": os_name,
        "arch": architecture,
        "system": os_name,
        "architecture": architecture,
        "target": target or "",
    }
    if resolved_release_tag is not None:
        context["release_tag"] = resolved_release_tag
    context.update(_render_variables(tool.variables, context))
    context.update(_render_variables(asset.variables, context))
    filename = _render_optional(asset.filename, context)
    if filename is not None:
        context["filename"] = filename

    url = _render_optional(asset.url_template, context) or _render_optional(
        asset.url, context
    )
    if url is None:
        raise ValueError(
            f"tool {name!r} has no downloadable URL for {os_name}/{architecture}"
        )

    context.setdefault("filename", filename or _default_filename(url))
    binary_path = _render_optional(asset.binary_path, context)
    checksum_asset = (
        _render_optional(asset.checksum_asset, context) or context["filename"]
    )
    support_paths = [_render_optional(path, context) or path for path in asset.support_paths]

    return ResolvedAsset(
        os=os_name,
        arch=architecture,
        target=asset.target,
        url=url,
        archive=asset.archive,
        binary_path=binary_path,
        support_paths=support_paths,
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
    resolve_latest: bool = False,
    release_lookup: Callable[[str], str] | None = None,
) -> InstallPlan:
    """Build an installation plan for one tool."""
    resolved_version, resolved_release_tag = _resolve_version(
        tool,
        release_lookup=release_lookup,
        resolve_latest=resolve_latest,
    )
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
        resolved_version=resolved_version,
        resolved_release_tag=resolved_release_tag,
    )
    context = {
        "tool_name": name,
        "version": resolved_version,
        "os": os_name,
        "arch": architecture,
        "system": os_name,
        "architecture": architecture,
        "target": target or "",
        "filename": resolved_asset.filename or _default_filename(resolved_asset.url),
    }
    if resolved_release_tag is not None:
        context["release_tag"] = resolved_release_tag
    context.update(_render_variables(tool.variables, context))
    context.update(_render_variables(selected_asset.variables, context))
    return InstallPlan(
        name=name,
        tool=tool,
        asset=resolved_asset,
        integrity=_resolve_integrity(tool.integrity, context),
        os_name=os_name,
        architecture=architecture,
        target=target,
        resolved_version=resolved_version,
        resolved_release_tag=resolved_release_tag,
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


def _cached_tools_root() -> Path:
    """Return the shared downloader cache root under the current XDG cache home."""
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "dev-container-fortress" / "tools"
    return Path.home() / ".cache" / "dev-container-fortress" / "tools"


def _safe_cache_component(value: str | None, *, default: str) -> str:
    """Normalize free-form cache key segments into stable path-safe strings."""
    if not value:
        return default
    normalized = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "-"
        for character in value
    ).strip("-")
    return normalized or default


def _resolved_identity(plan: InstallPlan) -> str:
    """Return the best available resolved identity for one tool build plan."""
    if plan.resolved_release_tag:
        return plan.resolved_release_tag
    if plan.resolved_version:
        return plan.resolved_version
    return "manifest"


def _cache_paths(plan: InstallPlan, *, cache_root: Path | None = None) -> CachedAsset:
    """Return the cache directory and file paths for one resolved asset."""
    root = Path(cache_root) if cache_root is not None else _cached_tools_root()
    cache_dir = (
        root
        / _safe_cache_component(plan.name, default="tool")
        / _safe_cache_component(plan.target, default="generic")
        / _safe_cache_component(plan.os_name, default="system")
        / _safe_cache_component(plan.architecture, default="arch")
        / _safe_cache_component(_resolved_identity(plan), default="version")
    )
    filename = plan.asset.filename or _default_filename(plan.asset.url)
    checksum_filename = (
        Path(urlparse(plan.integrity.checksum_url).path).name
        if plan.integrity.checksum_url
        else None
    )
    return CachedAsset(
        cache_dir=cache_dir,
        metadata_path=cache_dir / "metadata.json",
        asset_path=cache_dir / filename,
        checksum_path=cache_dir / checksum_filename if checksum_filename else None,
    )


def _cache_metadata(plan: InstallPlan, *, asset_sha256: str | None = None) -> dict[str, str]:
    """Render the cache metadata that must match for one stored asset."""
    metadata = {
        "tool": plan.name,
        "target": plan.target or "",
        "os": plan.os_name,
        "arch": plan.architecture,
        "version": plan.resolved_version,
        "release_tag": plan.resolved_release_tag or "",
        "url": plan.asset.url,
        "filename": plan.asset.filename or _default_filename(plan.asset.url),
        "checksum_url": plan.integrity.checksum_url or "",
    }
    if asset_sha256 is not None:
        metadata["asset_sha256"] = asset_sha256
    return metadata


def _read_cache_metadata(metadata_path: Path) -> dict[str, str] | None:
    """Load cached metadata when present and parseable."""
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_cache_metadata(metadata_path: Path, metadata: dict[str, str]) -> None:
    """Persist cache metadata alongside the downloaded asset."""
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _expected_checksum(plan: InstallPlan, checksum_path: Path) -> str | None:
    """Read the expected digest for the resolved asset from a cached checksum file."""
    if not plan.asset.checksum_asset:
        raise ValueError(
            f"tool {plan.name!r} defines checksum metadata but no checksum_asset"
        )
    expected_checksums, standalone_digest = _parse_checksum_manifest(checksum_path)
    return expected_checksums.get(plan.asset.checksum_asset) or standalone_digest


def _prepare_cached_asset(
    plan: InstallPlan,
    *,
    cache_root: Path | None = None,
) -> Path:
    """Ensure the resolved asset and checksum manifest exist in the downloader cache."""
    cached_asset = _cache_paths(plan, cache_root=cache_root)
    cached_asset.cache_dir.mkdir(parents=True, exist_ok=True)

    expected_metadata = _cache_metadata(plan)
    cached_metadata = _read_cache_metadata(cached_asset.metadata_path)
    metadata_matches = cached_metadata is not None and all(
        cached_metadata.get(key) == value for key, value in expected_metadata.items()
    )
    if not metadata_matches:
        shutil.rmtree(cached_asset.cache_dir, ignore_errors=True)
        cached_asset.cache_dir.mkdir(parents=True, exist_ok=True)
        cached_metadata = None

    if plan.integrity.checksum_url and cached_asset.checksum_path is not None:
        if not cached_asset.checksum_path.exists():
            _download(plan.integrity.checksum_url, cached_asset.checksum_path)

    asset_sha256 = cached_metadata.get("asset_sha256") if cached_metadata else None
    if cached_asset.asset_path.exists():
        actual_sha256 = _sha256(cached_asset.asset_path)
        if asset_sha256 and actual_sha256 != asset_sha256:
            cached_asset.asset_path.unlink()
            actual_sha256 = None
        else:
            asset_sha256 = actual_sha256

        if (
            actual_sha256 is not None
            and plan.integrity.checksum_url
            and cached_asset.checksum_path is not None
        ):
            expected_digest = _expected_checksum(plan, cached_asset.checksum_path)
            if expected_digest is None or actual_sha256 != expected_digest:
                cached_asset.asset_path.unlink()
                asset_sha256 = None

    if not cached_asset.asset_path.exists():
        _download(plan.asset.url, cached_asset.asset_path)
        asset_sha256 = _sha256(cached_asset.asset_path)
        if plan.integrity.checksum_url and cached_asset.checksum_path is not None:
            expected_digest = _expected_checksum(plan, cached_asset.checksum_path)
            if expected_digest is None:
                raise RuntimeError(
                    f"checksum manifest does not contain {plan.asset.checksum_asset!r}"
                )
            if asset_sha256 != expected_digest:
                raise RuntimeError(
                    f"checksum verification failed for {plan.asset.checksum_asset}: "
                    f"expected {expected_digest}, got {asset_sha256}"
                )

    _write_cache_metadata(
        cached_asset.metadata_path,
        _cache_metadata(plan, asset_sha256=asset_sha256 or _sha256(cached_asset.asset_path)),
    )
    return cached_asset.asset_path


def _extract_asset(plan: InstallPlan, asset_path: Path, workspace: Path) -> tuple[Path, list[Path]]:
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

    return (
        unpack_dir / plan.asset.binary_path,
        [unpack_dir / support_path for support_path in plan.asset.support_paths],
    )


def _install_binary(binary_path: Path, install_root: Path) -> Path:
    """Install one executable into the target root."""
    install_root.mkdir(parents=True, exist_ok=True)
    destination = install_root / binary_path.name
    shutil.copy2(binary_path, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    return destination


def _install_support_path(support_path: Path, install_root: Path) -> Path:
    """Install one support file or directory next to the binary root."""
    destination_root = install_root.parent
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / support_path.name
    if support_path.is_dir():
        if destination.exists() and not destination.is_dir():
            destination.unlink()
        shutil.copytree(support_path, destination, dirs_exist_ok=True)
        return destination
    if destination.exists():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.copy2(support_path, destination)
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
    cache_root: Path | None = None,
) -> Path:
    """Install the resolved tool asset into the destination root."""
    destination_root = Path(install_root or plan.tool.install_root)
    with tempfile.TemporaryDirectory(prefix=f"{plan.name}-") as temp_dir:
        workspace = Path(temp_dir)
        asset_path = _prepare_cached_asset(plan, cache_root=cache_root)
        binary_path, support_paths = _extract_asset(plan, asset_path, workspace)
        for support_path in support_paths:
            _install_support_path(support_path, destination_root)
        installed_path = _install_binary(binary_path, destination_root)

    if healthcheck:
        _run_healthcheck(plan.tool.healthcheck, destination_root)
    return installed_path
