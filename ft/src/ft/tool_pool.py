"""Tool-pool manifest helpers."""

from __future__ import annotations

from pathlib import Path
import tomllib

from ft.models import ToolPoolManifest


def load_tool_pool_manifest(path: Path) -> ToolPoolManifest:
    """Load the canonical tool-pool manifest from TOML.

    Args:
        path: Path to the tool-pool TOML file.

    Returns:
        Parsed tool-pool manifest.
    """
    raw_manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    return ToolPoolManifest.model_validate(raw_manifest)


def default_tool_pool_manifest_path(repo_root: Path) -> Path:
    """Return the default canonical tool-pool manifest path."""
    return repo_root / "ft" / "tools" / "tool-pool.toml"
