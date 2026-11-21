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

from ft import browser_bridge
from ft.container_runtime import (
    DEVCONTAINER_MOUNTS,
    HOMEBREW_PREFIX,
    HOMEBREW_TOOL_MOUNTS,
    OPTION_ENV,
    OPTION_MOUNTS,
    PERSISTED_MOUNT_PATHS,
    START_STEPS,
)
from ft.container_targets import CONTAINER_TARGETS
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


def build_args(dockerfile: Path) -> dict[str, str]:
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


def mount_paths(
    *,
    homebrew: bool,
    option_names: tuple[str, ...],
    extra: tuple[str, ...] = (),
) -> dict[str, str]:
    """Return the persisted mounts of one definition, in render order.

    Args:
        homebrew: Whether the target's userland comes from Homebrew.
        option_names: The options whose mounts to include.
        extra: Further persisted mount names, such as a profile's.

    Returns:
        Mount names mapped to container paths; ``brew`` is the Homebrew
        prefix.
    """
    names = list(DEVCONTAINER_MOUNTS)
    names.extend(name for name in extra if name not in names)
    for option_name in option_names:
        names.extend(name for name in OPTION_MOUNTS[option_name] if name not in names)
    if homebrew:
        names.extend(name for name in HOMEBREW_TOOL_MOUNTS if name not in names)
    paths = {name: PERSISTED_MOUNT_PATHS[name] for name in names}
    if homebrew:
        paths["brew"] = HOMEBREW_PREFIX
    return paths


def volume_mounts(paths: dict[str, str], source: str) -> list[dict[str, str]]:
    """Return named-volume mount entries.

    Args:
        paths: Mount names mapped to container paths.
        source: The volume name pattern, with ``{name}`` for the mount name.

    Returns:
        ``devcontainer.json`` mount entries.
    """
    return [
        {"source": source.format(name=name), "target": path, "type": "volume"}
        for name, path in paths.items()
    ]


# The host folder that holds the browser bridge socket. One broker serves every
# devcontainer, so the path is fixed rather than per definition. It sits below
# home but is not home itself, which the workbench guardrails allow.
BROWSER_BRIDGE_HOST_DIR = (
    "${localEnv:HOME}/.local/state/dev-container-fortress/browser-bridge"
)


def browser_bridge_settings() -> dict[str, object]:
    """Return the settings that give a devcontainer the host browser bridge.

    VS Code opens host browser links only while a window is attached, so CLI
    terminal mode relies on the bridge. ``initializeCommand`` runs on the host
    before the container starts: it creates the socket folder, which the bind
    mount needs, and asks ``ft`` to start the broker. A host without ``ft``, or
    with an ``ft`` too old to have the command, still starts the container;
    the helper then falls back to the in-container openers.

    Returns:
        ``initializeCommand``, the bind mount, and the container environment.
    """
    folder = f'"{BROWSER_BRIDGE_HOST_DIR}"'
    return {
        "initializeCommand": (
            f"mkdir -p {folder} && if command -v ft >/dev/null 2>&1; "
            f"then ft devcontainer browser-bridge {folder} || true; fi"
        ),
        "mount": {
            "source": BROWSER_BRIDGE_HOST_DIR,
            "target": browser_bridge.CONTAINER_BRIDGE_DIR,
            "type": "bind",
        },
        "containerEnv": {
            **dict.fromkeys(
                browser_bridge.BROWSER_ENV_NAMES, browser_bridge.CONTAINER_OPEN_COMMAND
            ),
            browser_bridge.SOCKET_ENV: browser_bridge.CONTAINER_SOCKET,
        },
    }


def vscode_customizations(extra_extensions: tuple[str, ...] = ()) -> dict[str, object]:
    """Return the VS Code customizations every definition carries.

    Args:
        extra_extensions: Extensions to add after the defaults.

    Returns:
        The ``customizations`` mapping.
    """
    extensions = list(VSCODE_EXTENSIONS)
    extensions.extend(name for name in extra_extensions if name not in extensions)
    return {
        "vscode": {
            "settings": {"terminal.integrated.defaultProfile.linux": "zsh"},
            "extensions": extensions,
        }
    }


def to_json(content: dict[str, object]) -> str:
    """Return a rendered mapping as committed JSON text.

    Args:
        content: The mapping to serialise.

    Returns:
        Two-space indented JSON with a trailing newline.
    """
    return json.dumps(content, indent=2) + "\n"


def render_definition(
    definition: DevcontainerDefinition, repo_root: Path
) -> dict[str, object]:
    """Return one devcontainer definition as a JSON-ready mapping.

    Every option's mounts and environment are included, because a static
    definition cannot read the selection; an unused volume costs nothing, and
    option-gated start steps check ``DEV_CONTAINER_FORTRESS_OPTIONS`` instead.

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
            "args": build_args(repo_root / "containers" / target.name / "Dockerfile"),
        }
    bridge = browser_bridge_settings()
    content["initializeCommand"] = bridge["initializeCommand"]
    content["remoteUser"] = "vscode"
    content["containerUser"] = "vscode"
    content["containerEnv"] = {OPTIONS_ENV: local_env(OPTIONS_ENV)}
    for option_env in OPTION_ENV.values():
        content["containerEnv"].update(option_env)
    content["containerEnv"].update(bridge["containerEnv"])
    paths = mount_paths(homebrew=target.homebrew, option_names=tuple(OPTION_MOUNTS))
    content["mounts"] = [
        *volume_mounts(paths, "dev-fortress-{name}-${{devcontainerId}}"),
        bridge["mount"],
    ]
    if not definition.volume_flow:
        content["customizations"] = vscode_customizations()
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
        repo_root / definition.path: to_json(render_definition(definition, repo_root))
        for definition in DEFINITIONS
    }


def stale_files(files: dict[Path, str]) -> list[Path]:
    """Return the rendered files whose copy on disk is missing or different.

    Args:
        files: Output paths mapped to their rendered text.

    Returns:
        The stale paths, in render order.
    """
    return [
        path
        for path, text in files.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != text
    ]


def write_files(files: dict[Path, str]) -> list[Path]:
    """Write the rendered files that are stale, creating parent directories.

    Args:
        files: Output paths mapped to their rendered text.

    Returns:
        The paths written.
    """
    written = stale_files(files)
    for path in written:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(files[path], encoding="utf-8")
    return written


def stale_definitions(repo_root: Path) -> list[Path]:
    """Return the committed definitions that differ from a fresh render.

    Args:
        repo_root: The repository root.

    Returns:
        Paths that are missing or out of date, in render order.
    """
    return stale_files(render_all(repo_root))
