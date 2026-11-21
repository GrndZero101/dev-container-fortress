"""Tests for rendering the devcontainer definitions from ft's runtime data."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ft.cli import app
from ft.container_runtime import HOMEBREW_PREFIX, PERSISTED_MOUNT_PATHS
from ft.devcontainer import (
    BROWSER_BRIDGE_HOST_DIR,
    DEFINITIONS,
    dockerfile_arg_defaults,
    local_env,
    render_all,
    render_definition,
    stale_definitions,
)
from ft.workbench import guardrail_violations
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _definition(target: str, *, volume_flow: bool = False):
    """Return the committed definition for one target and code flow.

    Args:
        target: The container target name.
        volume_flow: Whether to pick the volume-flow definition.

    Returns:
        The matching definition.
    """
    return next(
        d for d in DEFINITIONS if d.target == target and d.volume_flow == volume_flow
    )


def test_committed_definitions_match_a_fresh_render() -> None:
    """The committed devcontainer files are exactly the renderer's output."""
    assert stale_definitions(REPO_ROOT) == []


def test_local_env_rejects_a_colon_in_the_default() -> None:
    """The devcontainer CLI would cut such a default at its first colon."""
    assert local_env("A") == "${localEnv:A}"
    assert local_env("A", "") == "${localEnv:A}"
    assert local_env("A", "main") == "${localEnv:A:main}"
    with pytest.raises(ValueError, match="cannot hold ':'"):
        local_env("A", "https://example.com")


def test_build_args_carry_dockerfile_defaults_without_colons() -> None:
    """Defaults come from the Dockerfile, except those a colon would truncate."""
    content = render_definition(_definition("ubuntu"), REPO_ROOT)
    args = content["build"]["args"]
    assert args["SHELL_CONFIG_BRANCH"] == (
        "${localEnv:DEV_CONTAINER_FORTRESS_SHELL_CONFIG_BRANCH:main}"
    )
    assert args["SHELL_CONFIG_PROFILE_DEFAULT"].endswith(
        ":zsh-tll-citadel-dev-fortress}"
    )
    assert args["SHELL_CONFIG_REPO_URL"] == (
        "${localEnv:DEV_CONTAINER_FORTRESS_SHELL_CONFIG_REPO_URL}"
    )


def test_dockerfile_arg_defaults_keep_the_first_declaration(tmp_path: Path) -> None:
    """A later stage's redeclaration does not override the global default."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        'ARG A="one"\nARG B\nFROM scratch\nARG A="two"\n', encoding="utf-8"
    )
    assert dockerfile_arg_defaults(dockerfile) == {"A": "one", "B": ""}


def test_render_fails_when_a_dockerfile_lacks_a_forwarded_arg(
    tmp_path: Path,
) -> None:
    """A renamed Dockerfile argument is caught rather than forwarded blank."""
    shutil.copytree(REPO_ROOT / "containers", tmp_path / "containers")
    dockerfile = tmp_path / "containers" / "ubuntu" / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text(encoding="utf-8").replace(
            "SHELL_CONFIG_BRANCH", "SHELL_CONFIG_REF"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHELL_CONFIG_BRANCH"):
        render_all(tmp_path)


@pytest.mark.parametrize(
    ("target", "homebrew"), [("ubuntu", True), ("arch", True), ("alpine", False)]
)
def test_mounts_and_start_steps_follow_the_shared_table(
    target: str, homebrew: bool
) -> None:
    """Homebrew targets add the forge and brew volumes and the floor step."""
    content = render_definition(_definition(target), REPO_ROOT)
    targets = {mount["target"] for mount in content["mounts"]}
    for name in ("state", "zoxide", "atuin", "claude", "claude-versions"):
        assert PERSISTED_MOUNT_PATHS[name] in targets
    for path in (PERSISTED_MOUNT_PATHS["gh"], HOMEBREW_PREFIX):
        assert (path in targets) is homebrew
    steps = content["postStartCommand"].split(" && ")
    assert steps[-1] == "ft-ensure-claude-code --if-selected"
    assert ("ft-brew-floor" in steps) is homebrew
    assert ("postCreateCommand" in content) is not homebrew


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda d: d.path)
def test_every_definition_wires_the_browser_bridge(definition) -> None:
    """Each definition starts the host broker and mounts its socket folder."""
    content = render_definition(definition, REPO_ROOT)
    command = content["initializeCommand"]
    assert command.startswith(f'mkdir -p "{BROWSER_BRIDGE_HOST_DIR}" && ')
    assert f'ft devcontainer browser-bridge "{BROWSER_BRIDGE_HOST_DIR}"' in command
    assert {
        "source": BROWSER_BRIDGE_HOST_DIR,
        "target": "/tmp/dev-fortress-host-services",
        "type": "bind",
    } in content["mounts"]
    environment = content["containerEnv"]
    assert environment["BROWSER"] == "/usr/local/bin/ft-host-browser-open"
    assert environment["GH_BROWSER"] == "/usr/local/bin/ft-host-browser-open"
    assert environment["DEV_FORTRESS_HOST_BROWSER_SOCKET"] == (
        "/tmp/dev-fortress-host-services/browser-open.sock"
    )
    assert guardrail_violations(content) == []


@pytest.mark.parametrize("target", ["alpine", "arch", "ubuntu"])
def test_every_image_ships_the_browser_helper(target: str) -> None:
    """BROWSER points at a helper that each target's image installs."""
    dockerfile = (REPO_ROOT / "containers" / target / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "/usr/local/bin/ft-host-browser-open" in dockerfile


def test_volume_flow_image_default_survives_substitution() -> None:
    """The published image's tag sits outside any localEnv default."""
    content = render_definition(_definition("ubuntu", volume_flow=True), REPO_ROOT)
    assert content["image"] == (
        "${localEnv:DEV_FORTRESS_IMAGE_REPO:ghcr.io/grndzero101/dev-container-fortress}"
        ":${localEnv:DEV_FORTRESS_IMAGE_TAG:ubuntu}"
    )
    assert "build" not in content


def test_render_command_writes_and_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`render` writes missing files and `--check` then passes; drift fails it."""
    shutil.copytree(REPO_ROOT / "containers", tmp_path / "containers")
    monkeypatch.setattr("ft.cli._repo_root", lambda: tmp_path)

    result = runner.invoke(app, ["devcontainer", "render", "--check"])
    assert result.exit_code == 1
    assert "stale: .devcontainer/ubuntu/devcontainer.json" in result.output

    result = runner.invoke(app, ["devcontainer", "render"])
    assert result.exit_code == 0
    assert "wrote devcontainer/volume/devcontainer.json" in result.output
    assert runner.invoke(app, ["devcontainer", "render", "--check"]).exit_code == 0

    edited = tmp_path / ".devcontainer" / "arch" / "devcontainer.json"
    edited.write_text(edited.read_text(encoding="utf-8") + " ", encoding="utf-8")
    result = runner.invoke(app, ["devcontainer", "render", "--check"])
    assert result.exit_code == 1
    assert "stale: .devcontainer/arch/devcontainer.json" in result.output
