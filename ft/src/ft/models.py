"""Pydantic models for the ft manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IntegrityConfig(BaseModel):
    """Integrity metadata for a downloadable asset set."""

    checksum_url: str | None = None
    checksum_url_template: str | None = None
    checksum_format: str = "sha256sum"
    signature_url: str | None = None
    signature_url_template: str | None = None
    certificate_url: str | None = None
    certificate_url_template: str | None = None


class ToolAsset(BaseModel):
    """A downloadable tool asset for a concrete OS and architecture."""

    model_config = ConfigDict(extra="forbid")

    os: str
    arch: str
    target: str | None = None
    url: str | None = None
    url_template: str | None = None
    filename: str | None = None
    archive: str
    binary_path: str
    support_paths: list[str] = Field(default_factory=list)
    checksum_asset: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_download_source(self) -> "ToolAsset":
        if self.url is None and self.url_template is None:
            raise ValueError("tool assets must define either url or url_template")
        return self


class ToolDefinition(BaseModel):
    """Tool metadata used to resolve and install one command-line tool."""

    model_config = ConfigDict(extra="forbid")

    description: str
    version: str
    version_source: Literal["pinned", "github_latest"] = "pinned"
    release_tag_prefix: str = ""
    enabled: bool = True
    enabled_targets: list[str] = Field(default_factory=list)
    install_root: Path
    healthcheck: list[str] = Field(default_factory=list)
    integrity: IntegrityConfig = Field(default_factory=IntegrityConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    assets: list[ToolAsset]

    @model_validator(mode="after")
    def validate_assets(self) -> "ToolDefinition":
        if not self.assets:
            raise ValueError("tool assets must be a non-empty array of tables")
        if len(self.enabled_targets) != len(set(self.enabled_targets)):
            raise ValueError("enabled_targets must be unique within each tool")
        return self

    def enabled_for(self, target: str | None = None) -> bool:
        """Return whether this tool should be managed for the requested target."""
        if not self.enabled:
            return False
        if not self.enabled_targets:
            return True
        if target is None:
            return False
        return target in self.enabled_targets

    def asset_for(
        self,
        *,
        os_name: str,
        architecture: str,
        target: str | None = None,
    ) -> ToolAsset:
        """Return the matching asset for the requested platform and target."""
        targeted_match: ToolAsset | None = None
        generic_match: ToolAsset | None = None
        for asset in self.assets:
            if asset.os != os_name or asset.arch != architecture:
                continue
            if target is not None and asset.target == target:
                targeted_match = asset
                break
            if asset.target is None and generic_match is None:
                generic_match = asset
        if targeted_match is not None:
            return targeted_match
        if generic_match is not None:
            return generic_match
        if target is None:
            raise ValueError(f"tool has no asset for platform {os_name}/{architecture}")
        raise ValueError(
            f"tool has no asset for platform {os_name}/{architecture} with target {target!r}"
        )


class ToolManifest(BaseModel):
    """Parsed downloader manifest."""

    model_config = ConfigDict(extra="forbid")

    tools: dict[str, ToolDefinition]

    @model_validator(mode="after")
    def validate_tools(self) -> "ToolManifest":
        if not self.tools:
            raise ValueError("manifest must define a non-empty [tools] table")
        return self

    def enabled_tools(self, *, target: str | None = None) -> list[tuple[str, ToolDefinition]]:
        """Return enabled tools in deterministic order."""
        return [
            (name, self.tools[name])
            for name in sorted(self.tools)
            if self.tools[name].enabled_for(target)
        ]


class ToolPoolGroup(BaseModel):
    """One platform-specific tool-pool group."""

    model_config = ConfigDict(extra="forbid")

    formulae: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_formulae(self) -> "ToolPoolGroup":
        """Ensure formula lists stay deterministic and duplicate-free."""
        if len(self.formulae) != len(set(self.formulae)):
            raise ValueError("tool-pool formulae must be unique within each group")
        return self


class HomebrewToolPool(BaseModel):
    """Homebrew-oriented shared tool-pool definition."""

    model_config = ConfigDict(extra="forbid")

    common: ToolPoolGroup
    linux: ToolPoolGroup = Field(default_factory=ToolPoolGroup)
    wsl: ToolPoolGroup = Field(default_factory=ToolPoolGroup)
    macos: ToolPoolGroup = Field(default_factory=ToolPoolGroup)

    def formulae_for(self, platform: str) -> list[str]:
        """Return the effective formula list for the requested platform.

        Args:
            platform: Tool-pool platform key such as ``linux`` or ``macos``.

        Returns:
            Effective formula list with common entries followed by platform additions.
        """
        if platform not in {"linux", "wsl", "macos"}:
            raise ValueError(f"unsupported tool-pool platform: {platform}")
        platform_group = getattr(self, platform)
        return self.common.formulae + platform_group.formulae


class DownloaderToolPoolGroup(BaseModel):
    """Downloader-managed tool-pool metadata for one platform group."""

    model_config = ConfigDict(extra="forbid")

    target_tools: list[str] = Field(default_factory=list)
    implemented_tools: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tools(self) -> "DownloaderToolPoolGroup":
        """Keep downloader tool lists deterministic and duplicate-free."""
        if len(self.target_tools) != len(set(self.target_tools)):
            raise ValueError("target downloader tools must be unique within each group")
        if len(self.implemented_tools) != len(set(self.implemented_tools)):
            raise ValueError(
                "implemented downloader tools must be unique within each group"
            )
        if not set(self.implemented_tools).issubset(self.target_tools):
            raise ValueError(
                "implemented downloader tools must be a subset of target_tools"
            )
        return self


class DownloaderToolPool(BaseModel):
    """Downloader-oriented shared tool-pool definition."""

    model_config = ConfigDict(extra="forbid")

    common: DownloaderToolPoolGroup
    linux: DownloaderToolPoolGroup = Field(default_factory=DownloaderToolPoolGroup)
    wsl: DownloaderToolPoolGroup = Field(default_factory=DownloaderToolPoolGroup)
    macos: DownloaderToolPoolGroup = Field(default_factory=DownloaderToolPoolGroup)

    def target_tools_for(self, platform: str) -> list[str]:
        """Return the effective target downloader list for one platform."""
        if platform not in {"linux", "wsl", "macos"}:
            raise ValueError(f"unsupported tool-pool platform: {platform}")
        platform_group = getattr(self, platform)
        return self.common.target_tools + platform_group.target_tools

    def implemented_tools_for(self, platform: str) -> list[str]:
        """Return the effective implemented downloader list for one platform."""
        if platform not in {"linux", "wsl", "macos"}:
            raise ValueError(f"unsupported tool-pool platform: {platform}")
        platform_group = getattr(self, platform)
        return self.common.implemented_tools + platform_group.implemented_tools


class ContainerCommandToolPool(BaseModel):
    """Container validation command expectations."""

    model_config = ConfigDict(extra="forbid")

    command_checks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_command_checks(self) -> "ContainerCommandToolPool":
        """Keep command checks deterministic and duplicate-free."""
        if len(self.command_checks) != len(set(self.command_checks)):
            raise ValueError("container command checks must be unique within each group")
        return self


class ContainerToolPool(BaseModel):
    """Container-oriented shared tool-pool definition."""

    model_config = ConfigDict(extra="forbid")

    common: ContainerCommandToolPool
    ubuntu: ContainerCommandToolPool = Field(default_factory=ContainerCommandToolPool)
    alpine: ContainerCommandToolPool = Field(default_factory=ContainerCommandToolPool)

    def command_checks_for(self, target: str) -> list[str]:
        """Return the effective command checks for one container target."""
        if target not in {"ubuntu", "alpine"}:
            raise ValueError(f"unsupported container tool-pool target: {target}")
        target_group = getattr(self, target)
        return self.common.command_checks + target_group.command_checks


class ToolPoolManifest(BaseModel):
    """Parsed canonical tool-pool manifest."""

    model_config = ConfigDict(extra="forbid")

    homebrew: HomebrewToolPool
    downloader: DownloaderToolPool
    containers: ContainerToolPool


class HostTargetDefinition(BaseModel):
    """One named Dev Fortress host target."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    connection: str = "ssh"
    host: str | None = None
    user: str | None = None
    port: int = 22
    auth_method: str = "ssh_key"
    ssh_key_name: str | None = None
    ansible_python_interpreter: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> "HostTargetDefinition":
        if self.connection not in {"ssh", "local"}:
            raise ValueError("host targets must use ssh or local connection")
        if self.auth_method not in {"ssh_key", "local"}:
            raise ValueError("host targets must use ssh_key or local auth_method")
        if self.connection == "local":
            if self.auth_method != "local":
                raise ValueError("local host targets must use local auth_method")
            return self
        if not self.host:
            raise ValueError("ssh host targets must define host")
        if not self.user:
            raise ValueError("ssh host targets must define user")
        if self.auth_method != "ssh_key":
            raise ValueError("ssh host targets currently require ssh_key auth_method")
        return self

    def resolved_ssh_key_name(self) -> str:
        """Return the stable SSH key name for this target."""
        return self.ssh_key_name or self.name


class HostTargetManifest(BaseModel):
    """Parsed Dev Fortress host-target manifest."""

    model_config = ConfigDict(extra="forbid")

    targets: list[HostTargetDefinition]

    @model_validator(mode="after")
    def validate_targets(self) -> "HostTargetManifest":
        if not self.targets:
            raise ValueError("host target manifest must define at least one target")
        names = [target.name for target in self.targets]
        if len(names) != len(set(names)):
            raise ValueError("host target names must be unique")
        return self

    def by_name(self) -> dict[str, HostTargetDefinition]:
        """Return host targets keyed by name."""
        return {target.name: target for target in self.targets}


class WorkspaceProfileDefinition(BaseModel):
    """One named Dev Fortress daily-driver workspace profile."""

    model_config = ConfigDict(extra="forbid")

    description: str
    container_target: Literal["ubuntu", "alpine"] = "ubuntu"
    working_directory: str = "/workspace/dev-container-fortress"
    persisted_mounts: list[str] = Field(default_factory=list)
    tool_layers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lists(self) -> "WorkspaceProfileDefinition":
        """Keep profile list fields deterministic and duplicate-free."""
        if len(self.persisted_mounts) != len(set(self.persisted_mounts)):
            raise ValueError("workspace persisted_mounts must be unique")
        if len(self.tool_layers) != len(set(self.tool_layers)):
            raise ValueError("workspace tool_layers must be unique")
        return self


class WorkspaceToolLayerDefinition(BaseModel):
    """One named workspace tool-layer contract."""

    model_config = ConfigDict(extra="forbid")

    description: str
    mode: Literal["state_only", "image_build"] = "state_only"
    build_arg: str | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "WorkspaceToolLayerDefinition":
        """Keep build-arg usage aligned with the layer mode."""
        if self.mode == "state_only" and self.build_arg is not None:
            raise ValueError("state_only workspace layers may not define build_arg")
        if self.mode == "image_build" and not self.build_arg:
            raise ValueError("image_build workspace layers must define build_arg")
        return self


class WorkspaceProfileManifest(BaseModel):
    """Parsed Dev Fortress workspace-profile manifest."""

    model_config = ConfigDict(extra="forbid")

    tool_layers: dict[str, WorkspaceToolLayerDefinition] = Field(default_factory=dict)
    profiles: dict[str, WorkspaceProfileDefinition]

    @model_validator(mode="after")
    def validate_profiles(self) -> "WorkspaceProfileManifest":
        if not self.profiles:
            raise ValueError("workspace profile manifest must define profiles")
        unknown_layers = sorted(
            {
                layer_name
                for profile in self.profiles.values()
                for layer_name in profile.tool_layers
                if layer_name not in self.tool_layers
            }
        )
        if unknown_layers:
            raise ValueError(
                "workspace profiles reference undefined tool_layers: "
                + ", ".join(unknown_layers)
            )
        return self
