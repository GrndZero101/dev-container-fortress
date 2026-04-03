"""Pydantic models for the ft manifest."""

from __future__ import annotations

from pathlib import Path

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
    enabled: bool = True
    install_root: Path
    healthcheck: list[str] = Field(default_factory=list)
    integrity: IntegrityConfig = Field(default_factory=IntegrityConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    assets: list[ToolAsset]

    @model_validator(mode="after")
    def validate_assets(self) -> "ToolDefinition":
        if not self.assets:
            raise ValueError("tool assets must be a non-empty array of tables")
        return self

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

    def enabled_tools(self) -> list[tuple[str, ToolDefinition]]:
        """Return enabled tools in deterministic order."""
        return [
            (name, self.tools[name])
            for name in sorted(self.tools)
            if self.tools[name].enabled
        ]
