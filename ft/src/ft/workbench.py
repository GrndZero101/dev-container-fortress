"""Workbenches: multi-repo devcontainers that users define for their own repos.

A workbench is described by one TOML file under
``${XDG_CONFIG_HOME}/dev-container-fortress/workbenches/<name>.toml``, which
users own and may keep in their dotfiles. ``ft workbench render`` turns it
into a folder that holds only regenerable output plus clones::

    <directory>/
      .devcontainer/devcontainer.json
      <name>.code-workspace
      repos/<repo>/

The rendered definition uses the same runtime table as ``ft workspace`` and
the repository's own devcontainers (:mod:`ft.container_runtime`), so mounts,
start steps, and option environment are declared once.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ft.container_runtime import (
    OPTION_ENV,
    OPTION_MOUNTS,
    PERSISTED_MOUNT_PATHS,
    START_STEPS,
)
from ft.container_targets import CONTAINER_TARGETS
from ft.devcontainer import (
    browser_bridge_settings,
    build_args,
    mount_paths,
    to_json,
    volume_mounts,
    vscode_customizations,
)
from ft.models import WorkspaceProfileManifest
from ft.options import OPTIONS_ENV, parse_option_names

DEFAULT_PROFILE = "ubuntu-base"
WORKBENCH_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*$"

# Sockets that hand the container the host's container runtime, and with it
# root on the host. Other sockets, such as an SSH agent, stay allowed.
RUNTIME_SOCKET_NAMES = frozenset(
    {"docker.sock", "podman.sock", "containerd.sock", "crio.sock", "dockershim.sock"}
)
# Spellings of the host home directory in a mount source. Devcontainers often
# join two, as ``${localEnv:HOME}${localEnv:USERPROFILE}``, for Linux and Windows.
HOST_HOME_TOKENS = re.compile(
    r"\$\{localEnv:(HOME|USERPROFILE)\}|\$\{HOME\}|\$HOME\b|^~(?=/|$)"
)
HOST_HOME_PATTERN = re.compile(r"^(/home/[^/]+|/Users/[^/]+|/root)$")
WINDOWS_DRIVE_PATTERN = re.compile(r"^(/mnt/[a-zA-Z]|[a-zA-Z]:)([/\\]|$)")
# runArgs flags whose value follows as ``--flag value`` or ``--flag=value``.
RUN_ARG_VALUE_FLAGS = frozenset({"-v", "--volume", "--mount", "--network", "--net"})


def workbench_config_dir() -> Path:
    """Return the directory that holds the user's workbench definitions.

    Returns:
        ``${XDG_CONFIG_HOME}/dev-container-fortress/workbenches``.
    """
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg_config_home / "dev-container-fortress" / "workbenches"


def repo_dir_name(url: str) -> str:
    """Return the folder name a repository clones into.

    Args:
        url: An HTTPS, SSH, or ``scp``-style Git URL, or a local path.

    Returns:
        The last path segment without a ``.git`` suffix, as ``git clone``
        would name it.
    """
    segment = re.split(r"[/:]", url.rstrip("/"))[-1]
    return segment.removesuffix(".git")


class WorkbenchDefinition(BaseModel):
    """One user-defined workbench, as written in its TOML file.

    Attributes:
        name: The workbench name; also names its volumes and workspace file.
        directory: Where the rendered folder lives. A relative path resolves
            against the TOML file's folder; unset means
            ``~/workbenches/<name>``.
        profile: The ``ft workspace`` profile that supplies the target, tool
            layers, persisted mounts, and published image.
        local_build: A Dev Fortress checkout to build the image from instead
            of pulling the profile's published image. A relative path
            resolves against the workbench folder, so
            ``repos/dev-container-fortress`` builds from a clone.
        trust: The trust level; only ``full`` exists until ``M5d``.
        options: Optional components to install, such as ``claude-code``.
        mounts: Persisted mounts to add to the profile's.
        extensions: VS Code extensions to add to the defaults.
        repos: Git URLs to clone into ``repos/``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=WORKBENCH_NAME_PATTERN)
    directory: str | None = None
    profile: str = DEFAULT_PROFILE
    local_build: str | None = None
    trust: Literal["full"] = "full"
    options: list[str] = Field(default_factory=list)
    mounts: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        """Accept only catalog options that a container installs.

        Args:
            value: The option names.

        Returns:
            The names in catalog order.

        Raises:
            ValueError: For an unknown or host-only option.
        """
        names = parse_option_names(value) if value else ()
        host_only = [name for name in names if name not in OPTION_MOUNTS]
        if host_only:
            raise ValueError(f"host-only options cannot apply: {', '.join(host_only)}")
        return list(names)

    @field_validator("mounts")
    @classmethod
    def validate_mounts(cls, value: list[str]) -> list[str]:
        """Accept only known persisted mounts.

        Args:
            value: The mount names.

        Returns:
            The names unchanged.

        Raises:
            ValueError: For an unknown mount.
        """
        unknown = [name for name in value if name not in PERSISTED_MOUNT_PATHS]
        if unknown:
            known = ", ".join(PERSISTED_MOUNT_PATHS)
            raise ValueError(f"unknown mounts {', '.join(unknown)}; known: {known}")
        return value

    @model_validator(mode="after")
    def validate_repos(self) -> WorkbenchDefinition:
        """Require repos to clone into distinct folders.

        Returns:
            The definition.

        Raises:
            ValueError: When two repos share a folder name.
        """
        names = [repo_dir_name(url) for url in self.repos]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(
                f"repos clone into the same folder: {', '.join(duplicates)}"
            )
        return self


def workbench_path(name_or_path: str) -> Path:
    """Resolve a workbench argument to its TOML file.

    Args:
        name_or_path: A workbench name, or a path to a ``.toml`` file.

    Returns:
        The TOML file path.
    """
    if name_or_path.endswith(".toml") or "/" in name_or_path:
        return Path(name_or_path).expanduser().resolve()
    return workbench_config_dir() / f"{name_or_path}.toml"


def load_workbench(path: Path) -> WorkbenchDefinition:
    """Load and validate one workbench file.

    Args:
        path: The TOML file.

    Returns:
        The definition; ``name`` defaults to the file name without ``.toml``.

    Raises:
        OSError: When the file cannot be read.
        ValueError: When the file is not valid TOML or not a valid workbench.
    """
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    data.setdefault("name", path.stem)
    try:
        return WorkbenchDefinition.model_validate(data)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def workbench_directory(definition: WorkbenchDefinition, toml_path: Path) -> Path:
    """Return the folder a workbench renders into.

    Args:
        definition: The workbench.
        toml_path: Its TOML file, against which a relative directory resolves.

    Returns:
        The absolute folder path.
    """
    if definition.directory is None:
        return Path.home() / "workbenches" / definition.name
    directory = Path(definition.directory).expanduser()
    if not directory.is_absolute():
        directory = toml_path.parent / directory
    return directory.resolve()


def _build_path(path: Path, directory: Path) -> str:
    """Return a build path as ``devcontainer.json`` should hold it.

    Args:
        path: An absolute path for the build.
        directory: The workbench folder.

    Returns:
        A path relative to ``.devcontainer/`` when ``path`` is inside the
        workbench folder, so the folder can move; otherwise ``path`` itself.
    """
    if path.is_relative_to(directory):
        return os.path.relpath(path, directory / ".devcontainer")
    return str(path)


def _toml_list(values: list[str]) -> str:
    """Return a TOML array of strings.

    Args:
        values: The strings.

    Returns:
        A one-line array, or one item per line when there are several.
    """
    if len(values) < 2:
        return "[" + ", ".join(json.dumps(value) for value in values) + "]"
    return "[\n" + "".join(f"  {json.dumps(value)},\n" for value in values) + "]"


def workbench_toml(definition: WorkbenchDefinition) -> str:
    """Return a workbench as commented TOML text.

    Args:
        definition: The workbench.

    Returns:
        The file text, with unset settings left as commented examples.
    """

    def setting(key: str, value: str | None, example: str) -> str:
        """Return one optional string setting, or its commented example."""
        if value is None:
            return f"# {key} = {json.dumps(example)}\n"
        return f"{key} = {json.dumps(value)}\n"

    return (
        "# Dev Fortress workbench. Edit it, then run `ft workbench render` to\n"
        "# regenerate its folder; see docs/guides/workbench-usage.md in dev-container-fortress.\n"
        f"name = {json.dumps(definition.name)}\n"
        + setting("directory", definition.directory, f"~/workbenches/{definition.name}")
        + f"profile = {json.dumps(definition.profile)}\n"
        + setting("local_build", definition.local_build, "~/src/dev-container-fortress")
        + f"trust = {json.dumps(definition.trust)}\n"
        + f"options = {_toml_list(definition.options)}\n"
        + f"mounts = {_toml_list(definition.mounts)}\n"
        + f"extensions = {_toml_list(definition.extensions)}\n"
        + f"repos = {_toml_list(definition.repos)}\n"
    )


def _mount_fields(spec: str) -> dict[str, str]:
    """Parse a ``key=value,...`` mount string, as Docker and devcontainers use.

    Args:
        spec: The mount string, such as ``source=/a,target=/b,type=bind``.

    Returns:
        Keys mapped to values, with ``src`` and ``dst`` folded into
        ``source`` and ``target``.
    """
    aliases = {"src": "source", "dst": "target", "destination": "target"}
    fields: dict[str, str] = {}
    for part in spec.split(","):
        key, _, value = part.partition("=")
        key = key.strip().lower()
        fields[aliases.get(key, key)] = value.strip()
    return fields


def _bind_source(mount: object) -> str | None:
    """Return the host path a mount binds, or None for a volume or tmpfs.

    Args:
        mount: A ``devcontainer.json`` mount: an object or a mount string.

    Returns:
        The bind source, or None when the mount does not bind a host path.
    """
    if isinstance(mount, dict):
        fields = {str(key).lower(): str(value) for key, value in mount.items()}
    elif isinstance(mount, str):
        fields = _mount_fields(mount)
    else:
        return None
    if fields.get("type", "bind") != "bind":
        return None
    return fields.get("source") or None


def _volume_source(spec: str) -> str | None:
    """Return the host path a ``-v`` value binds, or None for a named volume.

    Args:
        spec: A ``-v``/``--volume`` value: ``source:target[:options]``.

    Returns:
        The source when it is a path rather than a volume name.
    """
    source = spec.split(":", 1)[0]
    if source.startswith(("/", "~", "$", ".")) or WINDOWS_DRIVE_PATTERN.match(spec):
        return source
    return None


def _source_violation(source: str) -> str | None:
    """Return why a bind source breaks a guardrail, or None when it is allowed.

    Args:
        source: A host path from a bind mount.

    Returns:
        The reason, or None.
    """
    path = source.replace("\\", "/").rstrip("/") or "/"
    if path.rsplit("/", 1)[-1] in RUNTIME_SOCKET_NAMES:
        return f"mounts a container-runtime socket: {source}"
    if path == "/":
        return "mounts the host root filesystem: /"
    if WINDOWS_DRIVE_PATTERN.match(path):
        return f"mounts a Windows drive: {source}"
    home = str(Path.home())
    if (
        not HOST_HOME_TOKENS.sub("", path).strip("/")
        or path == home
        or HOST_HOME_PATTERN.match(path)
    ):
        return f"mounts the host home directory: {source}"
    return None


def _run_arg_pairs(run_args: list[object]) -> list[tuple[str, str | None]]:
    """Split ``runArgs`` into flags with their values.

    Args:
        run_args: The ``runArgs`` list.

    Returns:
        ``(flag, value)`` pairs; ``value`` is None for a flag that takes none.
    """
    pairs: list[tuple[str, str | None]] = []
    items = [str(item) for item in run_args]
    index = 0
    while index < len(items):
        flag, equals, value = items[index].partition("=")
        if equals:
            pairs.append((flag, value))
        elif flag in RUN_ARG_VALUE_FLAGS and index + 1 < len(items):
            index += 1
            pairs.append((flag, items[index]))
        else:
            pairs.append((flag, None))
        index += 1
    return pairs


def guardrail_violations(content: dict[str, object]) -> list[str]:
    """Return the filesystem guardrails a devcontainer definition breaks.

    A ``full`` workbench keeps the host filesystem out of the container's
    reach, so its definition must not mount a container-runtime socket, the
    host home directory, the host root, or a Windows drive, and must not run
    privileged, add capabilities, or join the host network.

    Args:
        content: A parsed ``devcontainer.json``.

    Returns:
        One reason per violation; empty when the definition is allowed.
    """
    sources: list[str] = []
    mounts = content.get("mounts")
    for mount in mounts if isinstance(mounts, list) else []:
        source = _bind_source(mount)
        if source:
            sources.append(source)
    workspace_mount = content.get("workspaceMount")
    if isinstance(workspace_mount, str):
        source = _bind_source(workspace_mount)
        if source:
            sources.append(source)

    violations: list[str] = []
    if content.get("privileged") is True:
        violations.append("runs privileged: privileged is true")
    if content.get("capAdd"):
        violations.append(f"adds capabilities: capAdd {content['capAdd']}")
    run_args = content.get("runArgs")
    for flag, value in _run_arg_pairs(run_args if isinstance(run_args, list) else []):
        if flag == "--privileged" and value in (None, "true"):
            violations.append("runs privileged: --privileged")
        elif flag == "--cap-add":
            violations.append(f"adds capabilities: --cap-add {value}")
        elif flag in ("--network", "--net") and value == "host":
            violations.append(f"joins the host network: {flag} host")
        elif flag in ("-v", "--volume") and value:
            source = _volume_source(value)
            if source:
                sources.append(source)
        elif flag == "--mount" and value:
            source = _bind_source(value)
            if source:
                sources.append(source)
    for source in sources:
        reason = _source_violation(source)
        if reason:
            violations.append(reason)
    return violations


def rendered_guardrail_violations(directory: Path) -> list[str]:
    """Check the ``devcontainer.json`` already written in a workbench folder.

    Args:
        directory: The workbench folder.

    Returns:
        The guardrails the file on disk breaks; empty when it is missing or
        is not plain JSON, which the stale check reports instead.
    """
    path = directory / ".devcontainer" / "devcontainer.json"
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return []
    return guardrail_violations(content) if isinstance(content, dict) else []


def render_workbench(
    definition: WorkbenchDefinition,
    toml_path: Path,
    profiles: WorkspaceProfileManifest,
) -> dict[Path, str]:
    """Render a workbench's devcontainer definition and workspace file.

    Args:
        definition: The workbench.
        toml_path: Its TOML file.
        profiles: The workspace profile manifest.

    Returns:
        Absolute output paths mapped to their file text.

    Raises:
        ValueError: For an unknown profile, a profile with no published image
            and no ``local_build``, a ``local_build`` checkout without the
            target's Dockerfile, or a definition that breaks a filesystem
            guardrail (see :func:`guardrail_violations`).
    """
    if definition.profile not in profiles.profiles:
        known = ", ".join(sorted(profiles.profiles))
        raise ValueError(f"unknown profile {definition.profile!r}; known: {known}")
    profile = profiles.profiles[definition.profile]
    target = CONTAINER_TARGETS[profile.container_target]
    directory = workbench_directory(definition, toml_path)
    devcontainer_dir = directory / ".devcontainer"

    content: dict[str, object] = {"name": f"{definition.name} workbench"}
    if definition.local_build is not None:
        checkout = Path(definition.local_build).expanduser()
        if not checkout.is_absolute():
            checkout = directory / checkout
        checkout = checkout.resolve()
        dockerfile = checkout / "containers" / target.name / "Dockerfile"
        if not dockerfile.is_file():
            raise ValueError(
                f"local_build has no {target.name} Dockerfile: {dockerfile}"
            )
        args = build_args(dockerfile)
        for layer_name in profile.tool_layers:
            layer = profiles.tool_layers[layer_name]
            if layer.build_arg:
                args[layer.build_arg] = "1"
        if profile.os_release and target.release_build_arg:
            args[target.release_build_arg] = profile.os_release
        content["build"] = {
            "dockerfile": _build_path(dockerfile, directory),
            "context": _build_path(checkout, directory),
            "args": args,
        }
    elif profile.published_image is None:
        raise ValueError(
            f"profile {definition.profile!r} has no published image; "
            "set local_build to build it from a Dev Fortress checkout"
        )
    else:
        content["image"] = profile.published_image

    options = tuple(definition.options)
    bridge = browser_bridge_settings()
    content["initializeCommand"] = bridge["initializeCommand"]
    content["remoteUser"] = "vscode"
    content["containerUser"] = "vscode"
    environment = {OPTIONS_ENV: ",".join(options)}
    for option_name in options:
        environment.update(OPTION_ENV.get(option_name, {}))
    environment.update(bridge["containerEnv"])
    content["containerEnv"] = environment
    extra = tuple(profile.persisted_mounts) + tuple(definition.mounts)
    paths = mount_paths(homebrew=target.homebrew, option_names=options, extra=extra)
    # Named after the workbench, not ${devcontainerId}, so moving or
    # re-rendering the folder keeps its state.
    content["mounts"] = [
        *volume_mounts(paths, f"dev-fortress-wb-{definition.name}-{{name}}"),
        bridge["mount"],
    ]
    content["customizations"] = vscode_customizations(tuple(definition.extensions))
    steps = [
        step.command
        for step in START_STEPS
        if step.applies(homebrew=target.homebrew)
        and (step.option is None or step.option in options)
    ]
    if steps:
        content["postStartCommand"] = " && ".join(steps)
    violations = guardrail_violations(content)
    if violations:
        raise ValueError("workbench guardrails: " + "; ".join(violations))

    workspace = {
        "folders": [{"path": "."}]
        + [{"path": f"repos/{repo_dir_name(url)}"} for url in definition.repos],
        "settings": {"terminal.integrated.defaultProfile.linux": "zsh"},
    }
    return {
        devcontainer_dir / "devcontainer.json": to_json(content),
        directory / f"{definition.name}.code-workspace": to_json(workspace),
    }
