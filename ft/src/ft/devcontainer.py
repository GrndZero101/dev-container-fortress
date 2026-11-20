"""Render the repository's devcontainer definitions from ``ft``'s own data.

The committed ``devcontainer.json`` files are generated output: their mounts,
start steps, and option environment come from :mod:`ft.container_runtime`,
which ``ft workspace`` reads too, and their build-arg defaults come from the
target Dockerfiles. ``ft devcontainer render`` rewrites them, and its
``--check`` mode fails in pre-commit and CI when they drift.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ft.container_runtime import (
    DEVCONTAINER_MOUNTS,
    HOMEBREW_PREFIX,
    HOMEBREW_TOOL_MOUNTS,
    OPTION_ENV,
    OPTION_MOUNTS,
    PERSISTED_MOUNT_PATHS,
    START_STEPS,
)
from ft.container_targets import CONTAINER_TARGETS, ContainerTarget
from ft.options import OPTIONS_ENV

PUBLISHED_IMAGE_REPO = "ghcr.io/grndzero101/dev-container-fortress"
DOWNLOADER_MANIFEST = (
    "/home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml"
)
VSCODE_EXTENSIONS = (
    "ms-python.python",
    "ms-azuretools.vscode-docker",
    "hashicorp.terraform",
    "tamasfe.even-better-toml",
)
# Dockerfile build arguments a devcontainer build forwards, each read from a
# host environment variable.
BUILD_ARG_ENV: tuple[tuple[str, str], ...] = (
    ("CORPORATE_CA_CERT_DIR", "DEV_CONTAINER_FORTRESS_CA_CERT_DIR"),
    ("SHELL_CONFIG_SOURCE", "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_SOURCE"),
    ("SHELL_CONFIG_REPO_URL", "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_REPO_URL"),
    ("SHELL_CONFIG_BRANCH", "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_BRANCH"),
    ("SHELL_CONFIG_LOCAL_DIR", "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_LOCAL_DIR"),
    (
        "SHELL_CONFIG_PROFILE_DEFAULT",
        "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_PROFILE_DEFAULT",
    ),
    ("SHELL_CONFIG_INSTALL_ZINIT", "DEV_CONTAINER_FORTRESS_SHELL_CONFIG_INSTALL_ZINIT"),
)


@dataclass(frozen=True)
class DevcontainerDefinition:
    """One committed devcontainer definition.

    Attributes:
        path: Repository-relative path of the ``devcontainer.json``.
        target: The container target it runs.
        volume_flow: Whether it runs the published image with the code in a
            named volume, rather than building the image around a bind mount.
    """

    path: str
    target: str
    volume_flow: bool = False


DEFINITIONS: tuple[DevcontainerDefinition, ...] = (
    DevcontainerDefinition(".devcontainer/alpine/devcontainer.json", "alpine"),
    DevcontainerDefinition(".devcontainer/arch/devcontainer.json", "arch"),
    DevcontainerDefinition(".devcontainer/ubuntu/devcontainer.json", "ubuntu"),
    # Outside .devcontainer/ so VS Code does not offer it on reopen.
    DevcontainerDefinition(
        "devcontainer/volume/devcontainer.json", "ubuntu", volume_flow=True
    ),
)


def local_env(name: str, default: str | None = None) -> str:
    """Return a devcontainer ``${localEnv:...}`` reference.

    Args:
        name: The host environment variable.
        default: The value used when the variable is unset, if any.

    Returns:
        The substitution string.

    Raises:
        ValueError: When the default contains ``:``. The devcontainer CLI
            splits the reference on every colon, so it would keep only the
            text before the first one.
    """
    if not default:
        return f"${{localEnv:{name}}}"
    if ":" in default:
        raise ValueError(f"localEnv default for {name} cannot hold ':': {default}")
    return f"${{localEnv:{name}:{default}}}"


def dockerfile_arg_defaults(dockerfile: Path) -> dict[str, str]:
    """Return each build argument's first declared default in a Dockerfile.

    Args:
        dockerfile: The Dockerfile to read.

    Returns:
        Argument names mapped to their defaults, with quotes removed; an
        argument declared without a default maps to an empty string.
    """
    defaults: dict[str, str] = {}
    pattern = re.compile(r"^ARG\s+([A-Za-z_][A-Za-z0-9_]*)(?:=(.*))?$")
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match and match.group(1) not in defaults:
            defaults[match.group(1)] = (match.group(2) or "").strip().strip("\"'")
    return defaults


def _build_args(dockerfile: Path) -> dict[str, str]:
    """Return the forwarded build arguments for one Dockerfile.

    A default that holds ``:`` cannot survive ``${localEnv:...}``, so it is
    left out; the image's installers fall back to it when the argument
    arrives empty.

    Args:
        dockerfile: The target Dockerfile.

    Returns:
        Build argument names mapped to their ``${localEnv:...}`` references.

    Raises:
        ValueError: When the Dockerfile does not declare a forwarded argument.
    """
    defaults = dockerfile_arg_defaults(dockerfile)
    args: dict[str, str] = {}
    for arg_name, env_name in BUILD_ARG_ENV:
        if arg_name not in defaults:
            raise ValueError(f"{dockerfile} does not declare ARG {arg_name}")
        default = defaults[arg_name]
        args[arg_name] = local_env(env_name, None if ":" in default else default)
    return args


def _mounts(target: ContainerTarget) -> list[dict[str, str]]:
    """Return the named-volume mounts for one target.

    Every option's mounts are included, because a static definition cannot
    branch on the selection; an unused volume costs nothing.

    Args:
        target: The container target.

    Returns:
        Mount entries keyed per definition by ``${devcontainerId}``.
    """
    names = list(DEVCONTAINER_MOUNTS)
    for option_mounts in OPTION_MOUNTS.values():
        names.extend(name for name in option_mounts if name not in names)
    paths = {name: PERSISTED_MOUNT_PATHS[name] for name in names}
    if target.homebrew:
        paths.update(
            (name, PERSISTED_MOUNT_PATHS[name]) for name in HOMEBREW_TOOL_MOUNTS
        )
        paths["brew"] = HOMEBREW_PREFIX
    return [
        {
            "source": f"dev-fortress-{name}-${{devcontainerId}}",
            "target": path,
            "type": "volume",
        }
        for name, path in paths.items()
    ]


def render_definition(
    definition: DevcontainerDefinition, repo_root: Path
) -> dict[str, object]:
    """Return one devcontainer definition as a JSON-ready mapping.

    Args:
        definition: The definition to render.
        repo_root: The repository root, for reading the target Dockerfile.

    Returns:
        The ``devcontainer.json`` content, keys in their committed order.
    """
    target = CONTAINER_TARGETS[definition.target]
    content: dict[str, object] = {}
    if definition.volume_flow:
        content["name"] = "Dev Container Fortress (volume)"
        content["image"] = (
            f"{local_env('DEV_FORTRESS_IMAGE_REPO', PUBLISHED_IMAGE_REPO)}:"
            f"{local_env('DEV_FORTRESS_IMAGE_TAG', target.name)}"
        )
        # Keyed on the host folder: the CLI does not expand ${devcontainerId}
        # in workspaceMount.
        content["workspaceMount"] = (
            "type=volume,source=dev-fortress-src-${localWorkspaceFolderBasename},"
            "target=/workspaces"
        )
        content["workspaceFolder"] = "/workspaces"
    else:
        content["name"] = f"Dev Container Fortress ({target.name.capitalize()})"
        content["build"] = {
            "dockerfile": f"../../containers/{target.name}/Dockerfile",
            "context": "../..",
            "args": _build_args(repo_root / "containers" / target.name / "Dockerfile"),
        }
    content["remoteUser"] = "vscode"
    content["containerUser"] = "vscode"
    content["containerEnv"] = {OPTIONS_ENV: local_env(OPTIONS_ENV)}
    for option_env in OPTION_ENV.values():
        content["containerEnv"].update(option_env)
    content["mounts"] = _mounts(target)
    if not definition.volume_flow:
        content["customizations"] = {
            "vscode": {
                "settings": {"terminal.integrated.defaultProfile.linux": "zsh"},
                "extensions": list(VSCODE_EXTENSIONS),
            }
        }
        if not target.homebrew:
            content["postCreateCommand"] = (
                f"ft plan --manifest {DOWNLOADER_MANIFEST} --target {target.name}"
            )
    content["postStartCommand"] = " && ".join(
        step.devcontainer_command()
        for step in START_STEPS
        if step.applies(homebrew=target.homebrew)
    )
    return content


def render_all(repo_root: Path) -> dict[Path, str]:
    """Render every committed devcontainer definition.

    Args:
        repo_root: The repository root.

    Returns:
        Absolute output paths mapped to their file text.
    """
    return {
        repo_root / definition.path: json.dumps(
            render_definition(definition, repo_root), indent=2
        )
        + "\n"
        for definition in DEFINITIONS
    }


def stale_definitions(repo_root: Path) -> list[Path]:
    """Return the committed definitions that differ from a fresh render.

    Args:
        repo_root: The repository root.

    Returns:
        Paths that are missing or out of date, in render order.
    """
    stale = []
    for path, text in render_all(repo_root).items():
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(path)
    return stale
