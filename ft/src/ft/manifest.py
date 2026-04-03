"""Manifest loading helpers for ft."""

from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import ValidationError

from ft.models import ToolManifest


def load_manifest(path: Path) -> ToolManifest:
    """Load the downloader manifest from disk."""
    with path.open("rb") as handle:
        raw_manifest = tomllib.load(handle)

    if "tools" not in raw_manifest:
        raise ValueError("manifest must define a non-empty [tools] table")

    try:
        return ToolManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise ValueError(str(error)) from error
