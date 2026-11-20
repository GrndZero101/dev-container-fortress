"""Tests for the bash helpers that ship in the container images."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENSURE_CLAUDE_CODE = REPO_ROOT / "containers" / "common" / "ensure-claude-code.sh"


def _fake_version(versions_dir: Path, name: str, mtime: int) -> None:
    """Write one fake Claude Code version that prints its own name.

    Args:
        versions_dir: The persisted versions directory.
        name: The version file name.
        mtime: The modification time to give the file.
    """
    path = versions_dir / name
    path.write_text(f"#!/bin/sh\necho '{name} (Claude Code)'\n", encoding="utf-8")
    path.chmod(0o755)
    os.utime(path, (mtime, mtime))


def test_ensure_claude_code_relinks_the_highest_version(tmp_path: Path) -> None:
    """A replaced container relinks by version, not by modification time.

    ``claude update`` to a version already on disk does not rewrite it, so an
    older version reinstalled later can be the newest file.
    """
    versions_dir = tmp_path / ".local" / "share" / "claude" / "versions"
    versions_dir.mkdir(parents=True)
    _fake_version(versions_dir, "2.1.329", mtime=1_000)
    _fake_version(versions_dir, "2.1.99", mtime=2_000)
    _fake_version(versions_dir, "2.1.303", mtime=3_000)
    _fake_version(versions_dir, "2.1.400.partial", mtime=4_000)

    result = subprocess.run(
        ["bash", str(ENSURE_CLAUDE_CODE)],
        env={"HOME": str(tmp_path), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )

    launcher = tmp_path / ".local" / "bin" / "claude"
    assert launcher.readlink() == versions_dir / "2.1.329"
    assert "relinked persisted version 2.1.329" in result.stdout
    assert result.stdout.strip().endswith("2.1.329 (Claude Code)")
