"""Pydantic models for the ft manifest."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IntegrityConfig(BaseModel):
    """Integrity metadata for a downloadable asset set."""

    checksum_url: str | None = None
    checksum_format: str = "sha256sum"
    signature_url: str | None = None
    certificate_url: str | None = None


class ToolAsset(BaseModel):
    """A downloadable tool asset for a concrete OS and architecture."""

    os: str
    arch: str
    url: str
    archive: str
    binary_path: str
    checksum_asset: str | None = None


class ToolDefinition(BaseModel):
    """Tool metadata used to resolve and install one command-line tool."""

    model_config = ConfigDict(extra="forbid")

    description: str
    version: str
    enabled: bool = True
    install_root: Path
    healthcheck: list[str] = Field(default_factory=list)
    integrity: IntegrityConfig = Field(default_factory=IntegrityConfig)
    assets: list[ToolAsset]

    @model_validator(mode="after")
    def validate_assets(self) -> "ToolDefinition":
        if not self.assets:
            raise ValueError("tool assets must be a non-empty array of tables")
        return self

    def asset_for(self, *, os_name: str, architecture: str) -> ToolAsset:
        """Return the matching asset for the requested platform."""
        for asset in self.assets:
            if asset.os == os_name and asset.arch == architecture:
                return asset
        raise ValueError(f"tool has no asset for platform {os_name}/{architecture}")


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
