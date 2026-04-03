"""Environment-backed runtime settings for ft."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class FtSettings(BaseSettings):
    """Runtime settings resolved from environment variables.

    Attributes:
        manifest: Default manifest path.
        target: Optional named target context.
        system: Optional system override.
        architecture: Optional architecture override.
        install_root: Optional install root override.
        healthcheck: Whether install healthchecks should run.
    """

    model_config = SettingsConfigDict(
        env_prefix="FT_",
        extra="ignore",
    )

    manifest: Path = Path("ft/tools/tools.toml")
    target: str = "ubuntu"
    system: str | None = None
    architecture: str | None = None
    install_root: Path | None = None
    healthcheck: bool = True
