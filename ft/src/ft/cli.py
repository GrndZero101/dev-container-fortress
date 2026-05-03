"""Typer CLI for ft."""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import Annotated

from rich.console import Console
from rich.table import Table
import typer

from ft.installer import InstallPlan, build_plan, install_tool
from ft.manifest import load_manifest
from ft.models import (
    HostTargetDefinition,
    HostTargetManifest,
    ToolDefinition,
    ToolManifest,
    WorkspaceProfileDefinition,
    WorkspaceProfileManifest,
    WorkspaceToolLayerDefinition,
)
from ft.platforms import detect_architecture, detect_system
from ft.settings import FtSettings
from ft.tool_pool import default_tool_pool_manifest_path, load_tool_pool_manifest

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help=(
        "Operator CLI for Dev Fortress provisioning, tool installation, "
        "and environment validation."
    ),
)
tool_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Manage tool installation plans and installs from the shared manifest."
    ),
)
container_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Operate and validate Dev Fortress disposable container targets for "
        "human and future agentic workflows."
    ),
)
host_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Model, inspect, and render SSH-oriented Dev Fortress host targets for "
        "future provisioning workflows."
    ),
)
workspace_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Operate mounted Dev Fortress daily-driver workspace containers for "
        "day-to-day development."
    ),
)
workspace_auth_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Inspect auth and persisted-state handoff points for mounted Dev Fortress "
        "workspace containers."
    ),
)
infra_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Run thin Terraform-backed infrastructure workflows that feed the "
        "existing Dev Fortress host loop."
    ),
)
aws_disposable_ubuntu_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Operate the disposable Ubuntu AWS Terraform stack with Dev Fortress "
        "managed SSH keys and host-target import wiring."
    ),
)
completion_app = typer.Typer(
    no_args_is_help=False,
    help=(
        "Generate and install shell completion artifacts for Dev Fortress CLIs "
        "into XDG-managed runtime paths."
    ),
)
app.add_typer(tool_app, name="tool")
app.add_typer(container_app, name="container")
app.add_typer(host_app, name="host")
app.add_typer(workspace_app, name="workspace")
workspace_app.add_typer(workspace_auth_app, name="auth")
app.add_typer(infra_app, name="infra")
infra_app.add_typer(aws_disposable_ubuntu_app, name="aws-disposable-ubuntu")
app.add_typer(completion_app, name="completion")

console = Console()
KNOWN_CONTAINER_TARGETS = ("ubuntu", "alpine")
SUPPORTED_SHELL_CONFIG_SOURCES = ("github", "local")
ANSIBLE_PLAY_RECAP_PATTERN = re.compile(
    r"^(?:.*\|\s*)?(?P<target>[^\n:|]+?)\s*:\s*"
    r"ok=(?P<ok>\d+)\s+"
    r"changed=(?P<changed>\d+)\s+"
    r"unreachable=(?P<unreachable>\d+)\s+"
    r"failed=(?P<failed>\d+)\s+"
    r"skipped=(?P<skipped>\d+)\s+"
    r"rescued=(?P<rescued>\d+)\s+"
    r"ignored=(?P<ignored>\d+)\s*$",
    re.MULTILINE,
)


@app.callback(invoke_without_command=True)
def root_callback(context: typer.Context) -> None:
    """Render root help and grouped commands when no subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@tool_app.callback(invoke_without_command=True)
def tool_callback(context: typer.Context) -> None:
    """Render tool-group help when no tool subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@container_app.callback(invoke_without_command=True)
def container_callback(context: typer.Context) -> None:
    """Render container-group help when no container subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@host_app.callback(invoke_without_command=True)
def host_callback(context: typer.Context) -> None:
    """Render host-group help when no host subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@workspace_app.callback(invoke_without_command=True)
def workspace_callback(context: typer.Context) -> None:
    """Render workspace-group help when no workspace subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@workspace_auth_app.callback(invoke_without_command=True)
def workspace_auth_callback(context: typer.Context) -> None:
    """Render workspace-auth help when no subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@infra_app.callback(invoke_without_command=True)
def infra_callback(context: typer.Context) -> None:
    """Render infra-group help when no infra subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@aws_disposable_ubuntu_app.callback(invoke_without_command=True)
def aws_disposable_ubuntu_callback(context: typer.Context) -> None:
    """Render disposable-Ubuntu infra help when no subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


@completion_app.callback(invoke_without_command=True)
def completion_callback(context: typer.Context) -> None:
    """Render completion-group help when no completion subcommand is passed."""
    if context.invoked_subcommand is None:
        console.print(context.get_help())
        raise typer.Exit()


def _is_writable_directory(path: Path) -> bool:
    """Return whether the directory exists or can be created by the current user."""
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent, os.W_OK)


def _default_user_install_root() -> Path:
    """Return the fallback user-local binary directory."""
    return Path.home() / ".local" / "bin"


def _effective_install_root(
    tool_install_root: Path,
    override_install_root: Path | None,
) -> Path:
    """Return the install root to use for the current execution context."""
    if override_install_root is not None:
        return override_install_root
    if _is_writable_directory(tool_install_root):
        return tool_install_root
    return _default_user_install_root()


def _resolve_runtime_options(
    *,
    manifest: Path | None,
    target: str | None,
    system_name: str | None,
    architecture: str | None,
    install_root: Path | None,
    healthcheck: bool | None,
) -> dict[str, object]:
    """Resolve CLI options with environment-backed defaults."""
    settings = FtSettings()
    return {
        "manifest": manifest or settings.manifest,
        "target": target or settings.target,
        "system_name": system_name or settings.system or detect_system(),
        "architecture": architecture or settings.architecture or detect_architecture(),
        "install_root": install_root or settings.install_root,
        "healthcheck": settings.healthcheck if healthcheck is None else healthcheck,
    }


def _selected_tools(
    manifest: ToolManifest,
    requested_tool: str | None,
    *,
    target: str | None,
) -> list[tuple[str, ToolDefinition]]:
    """Resolve the tool subset requested by the user."""
    if requested_tool is None:
        return manifest.enabled_tools(target=target)
    if requested_tool not in manifest.tools:
        raise typer.BadParameter(f"unknown tool: {requested_tool}", param_hint="--tool")
    if not manifest.tools[requested_tool].enabled_for(target):
        target_detail = f" for target {target}" if target else ""
        raise typer.BadParameter(
            f"tool {requested_tool} is not downloader-managed{target_detail}",
            param_hint="--tool",
        )
    return [(requested_tool, manifest.tools[requested_tool])]


def _render_plan(
    plan: InstallPlan,
    *,
    target: str,
    install_root: Path | None,
) -> None:
    """Render one resolved plan to the console."""
    effective_install_root = _effective_install_root(
        plan.tool.install_root, install_root
    )

    table = Table(title=f"{plan.name} plan", show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    table.add_row("target", target)
    table.add_row("version", plan.resolved_version or plan.tool.version)
    table.add_row("platform", f"{plan.os_name}/{plan.architecture}")
    table.add_row("url", plan.asset.url)
    table.add_row("archive", plan.asset.archive)
    table.add_row("install_root", str(effective_install_root))
    if plan.integrity.checksum_url:
        table.add_row("checksums", plan.integrity.checksum_url)
    if plan.integrity.signature_url:
        table.add_row("signature", plan.integrity.signature_url)

    console.print(table)


def _container_name_for_target(target: str) -> str:
    """Return the deterministic test-container name for one target."""
    return f"dev-fortress-{target}-test"


def _container_host_ssh_target_name(target: str) -> str | None:
    """Return the default host-target name for one SSH-capable disposable target."""
    if target == "ubuntu":
        return "dev-fortress-ubuntu"
    if target == "alpine":
        return "dev-fortress-alpine"
    return None


def _container_target_for_host_ssh_target_name(host_target_name: str) -> str | None:
    """Return the disposable container target for one SSH host-target name."""
    for target in KNOWN_CONTAINER_TARGETS:
        if _container_host_ssh_target_name(target) == host_target_name:
            return target
    return None


def _container_host_ssh_port(target: str) -> int | None:
    """Return the forwarded host SSH port for one SSH-capable disposable target."""
    if target == "ubuntu":
        return 2222
    if target == "alpine":
        return 2223
    return None


def _container_host_ssh_public_key_path(target: str) -> Path | None:
    """Return the managed public key path for one SSH-capable disposable target."""
    host_target_name = _container_host_ssh_target_name(target)
    if host_target_name is None:
        return None
    return (
        _dev_fortress_state_root()
        / "ssh"
        / host_target_name
        / f"{_managed_ssh_key_basename()}.pub"
    )


def _dockerfile_for_target(target: str) -> Path:
    """Return the repo-local Dockerfile path for one known target."""
    return _repo_root() / "containers" / target / "Dockerfile"


def _image_tag_for_target(target: str) -> str:
    """Return the deterministic local image tag for one target."""
    return f"dev-container-fortress:{target}-test"


def _repo_root() -> Path:
    """Return the repository root that contains the ft package directory."""
    return Path(__file__).resolve().parents[3]


def _managed_ssh_key_basename() -> str:
    """Return the basename used for Dev Fortress-managed SSH keypairs."""
    return "dev_fortress_ed25519"


def _dev_fortress_completion_root() -> Path:
    """Return the XDG-managed directory root for Dev Fortress completion artifacts."""
    xdg_data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return xdg_data_home / "dev-container-fortress" / "completions"


def _completion_directory(shell_name: str) -> Path:
    """Return the shell-specific completion directory for one supported shell."""
    return _dev_fortress_completion_root() / shell_name


def _completion_output_path(shell_name: str, *, command_name: str = "ft") -> Path:
    """Return the installed completion artifact path for one command and shell."""
    return _completion_directory(shell_name) / f"_{command_name}"


def _default_shell_config_stage_dir() -> Path:
    """Return the repo-local staging directory used for local shell-config builds."""
    return _repo_root() / ".local" / "sources" / "shell-config"


def _require_supported_shell_config_source(source: str) -> str:
    """Validate one shell-config source mode for container builds."""
    if source not in SUPPORTED_SHELL_CONFIG_SOURCES:
        supported = ", ".join(SUPPORTED_SHELL_CONFIG_SOURCES)
        raise typer.BadParameter(
            f"unsupported shell-config source: {source!r} (supported: {supported})",
            param_hint="--shell-config-source",
        )
    return source


def _relative_build_context_path(path: Path) -> str:
    """Return one repo-relative path suitable for the Docker build-context mount."""
    resolved_path = path.resolve()
    repo_root = _repo_root().resolve()
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError as error:
        raise typer.BadParameter(
            "local shell-config staging path must live inside the dev-container-fortress repo",
            param_hint="--shell-config-local-dir",
        ) from error


def _stage_local_shell_config(source_path: Path, destination_path: Path) -> Path:
    """Stage one local shell-config checkout into the repo build context."""
    resolved_source = source_path.resolve()
    if not resolved_source.is_absolute():
        raise typer.BadParameter(
            "local shell-config source path must be absolute",
            param_hint="--shell-config-stage-from",
        )
    if not resolved_source.is_dir():
        raise typer.BadParameter(
            f"local shell-config source does not exist: {resolved_source}",
            param_hint="--shell-config-stage-from",
        )
    if not (resolved_source / "scripts" / "csm").is_file():
        raise typer.BadParameter(
            f"local shell-config source does not look like a shell-config checkout: {resolved_source}",
            param_hint="--shell-config-stage-from",
        )

    resolved_destination = destination_path.resolve()
    resolved_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(resolved_destination, ignore_errors=True)
    shutil.copytree(
        resolved_source,
        resolved_destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".cache",
            ".local",
            ".zsh_history",
            ".DS_Store",
            "__pycache__",
        ),
    )
    return resolved_destination


def _require_supported_completion_shell(shell_name: str) -> str:
    """Validate one shell name for completion generation."""
    if shell_name != "zsh":
        raise typer.BadParameter(
            f"unsupported shell: {shell_name!r} (supported: zsh)",
            param_hint="shell",
        )
    return shell_name


def _generate_ft_completion_source(shell_name: str) -> str:
    """Generate shell completion source for the current ft CLI."""
    _require_supported_completion_shell(shell_name)
    # Typer's bundled zsh template still emits the older _TYPER_COMPLETE_ARGS
    # flow, while Click 8.3's zsh completion backend now expects COMP_WORDS and
    # COMP_CWORD. Keep the instruction format on Typer's side (`complete_zsh`)
    # but feed the env vars Click's ZshComplete class now reads.
    return """#compdef ft

_ft_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[ft] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _FT_COMPLETE=complete_zsh ft)}")

    for type key descr in ${response}; do
        if [[ "$type" == "plain" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions+=("$key")
            else
                completions_with_descriptions+=("$key":"$descr")
            fi
        elif [[ "$type" == "dir" ]]; then
            _path_files -/
        elif [[ "$type" == "file" ]]; then
            _path_files -f
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _ft_completion ft
"""


def _default_host_config_path() -> Path:
    """Return the default XDG-aligned host-target config path."""
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg_config_home / "dev-container-fortress" / "hosts.toml"


def _example_host_config_path() -> Path:
    """Return the repo-local example host-target manifest path."""
    return _repo_root() / "ft" / "targets" / "hosts.example.toml"


def _dev_fortress_state_root() -> Path:
    """Return the XDG-aligned Dev Fortress state root."""
    xdg_state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    )
    return xdg_state_home / "dev-container-fortress"


def _workspace_profile_manifest_path() -> Path:
    """Return the repo-local workspace-profile manifest path."""
    return _repo_root() / "ft" / "workspaces" / "profiles.toml"


def _workspace_state_root() -> Path:
    """Return the XDG-aligned state root for workspace containers."""
    return _dev_fortress_state_root() / "workspaces"


def _load_workspace_profile_manifest() -> WorkspaceProfileManifest:
    """Load and validate the repo-local workspace-profile manifest."""
    manifest_path = _workspace_profile_manifest_path()
    with manifest_path.open("rb") as handle:
        return WorkspaceProfileManifest.model_validate(tomllib.load(handle))


def _resolve_workspace_profile(
    profile_name: str,
) -> tuple[str, WorkspaceProfileDefinition]:
    """Resolve exactly one named workspace profile from the repo manifest."""
    manifest = _load_workspace_profile_manifest()
    if profile_name not in manifest.profiles:
        available = ", ".join(sorted(manifest.profiles))
        raise typer.BadParameter(
            f"unknown workspace profile: {profile_name!r} (available: {available})",
            param_hint="profile",
        )
    return profile_name, manifest.profiles[profile_name]


def _workspace_profile_names() -> list[str]:
    """Return workspace profile names in deterministic order."""
    return sorted(_load_workspace_profile_manifest().profiles)


def _workspace_tool_layer_definitions(
    profile: WorkspaceProfileDefinition,
) -> list[tuple[str, WorkspaceToolLayerDefinition]]:
    """Return resolved tool-layer definitions for one workspace profile."""
    manifest = _load_workspace_profile_manifest()
    return [
        (layer_name, manifest.tool_layers[layer_name]) for layer_name in profile.tool_layers
    ]


def _workspace_image_build_layers(
    profile: WorkspaceProfileDefinition,
) -> list[tuple[str, WorkspaceToolLayerDefinition]]:
    """Return workspace layers that would change image build behavior."""
    return [
        (layer_name, layer_definition)
        for layer_name, layer_definition in _workspace_tool_layer_definitions(profile)
        if layer_definition.mode == "image_build"
    ]


def _workspace_state_only_layers(
    profile: WorkspaceProfileDefinition,
) -> list[tuple[str, WorkspaceToolLayerDefinition]]:
    """Return workspace layers that are state and contract markers only."""
    return [
        (layer_name, layer_definition)
        for layer_name, layer_definition in _workspace_tool_layer_definitions(profile)
        if layer_definition.mode == "state_only"
    ]


def _workspace_container_name(profile_name: str) -> str:
    """Return the deterministic Docker container name for one workspace profile."""
    return f"dev-fortress-workspace-{profile_name}"


def _workspace_image_tag(profile_name: str) -> str:
    """Return the deterministic Docker image tag for one workspace profile."""
    return f"dev-container-fortress:workspace-{profile_name}"


def _workspace_default_shell_config_checkout() -> Path | None:
    """Return the default sibling shell-config checkout path when present."""
    candidate = _repo_root().parent / "shell-config"
    return candidate if candidate.is_dir() else None


def _workspace_runtime_shell_config_checkout(
    shell_config_checkout: Path | None,
) -> Path | None:
    """Resolve the optional shell-config checkout used for live bind mounts."""
    if shell_config_checkout is not None:
        return shell_config_checkout
    return _workspace_default_shell_config_checkout()


def _workspace_shell_config_resolution(
    shell_config_checkout: Path | None,
) -> dict[str, object]:
    """Describe how the workspace shell-config checkout was resolved."""
    if shell_config_checkout is not None:
        return {
            "requested_path": str(shell_config_checkout),
            "resolved_path": str(shell_config_checkout),
            "source": "explicit",
            "available": True,
            "detail": "using --shell-config-checkout",
        }

    default_checkout = _workspace_default_shell_config_checkout()
    if default_checkout is not None:
        return {
            "requested_path": None,
            "resolved_path": str(default_checkout),
            "source": "sibling_default",
            "available": True,
            "detail": "using sibling ../shell-config checkout",
        }

    return {
        "requested_path": None,
        "resolved_path": None,
        "source": "none",
        "available": False,
        "detail": "no sibling ../shell-config checkout found; pass --shell-config-checkout /absolute/path/to/shell-config to mount it live",
    }


def _workspace_persisted_host_path(profile_name: str, mount_name: str) -> Path:
    """Return the host-side persisted path for one named workspace mount."""
    mapping = {
        "cache": _workspace_state_root() / profile_name / "cache",
        "share": _workspace_state_root() / profile_name / "share",
        "gh": _workspace_state_root() / profile_name / "config-gh",
        "glab": _workspace_state_root() / profile_name / "config-glab",
        "aws": Path.home() / ".aws",
        "azure": _workspace_state_root() / profile_name / "azure",
    }
    if mount_name not in mapping:
        raise ValueError(f"unsupported workspace persisted mount: {mount_name}")
    return mapping[mount_name]


def _workspace_persisted_container_path(mount_name: str) -> str:
    """Return the in-container path for one named workspace persisted mount."""
    mapping = {
        "cache": "/home/vscode/.cache",
        "share": "/home/vscode/.local/share",
        "gh": "/home/vscode/.config/gh",
        "glab": "/home/vscode/.config/glab",
        "aws": "/home/vscode/.aws",
        "azure": "/home/vscode/.azure",
    }
    if mount_name not in mapping:
        raise ValueError(f"unsupported workspace persisted mount: {mount_name}")
    return mapping[mount_name]


def _host_proc_version_text() -> str:
    """Return the host kernel version text when readable."""
    try:
        return Path("/proc/version").read_text(encoding="utf-8")
    except OSError:
        return ""


def _host_runs_under_wsl() -> bool:
    """Return whether the current host runtime appears to be WSL-backed."""
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    return "microsoft" in _host_proc_version_text().lower()


def _workspace_wsl_windows_system_path() -> Path:
    """Return the host-side Windows System32 path used for WSL browser interop."""
    return Path("/mnt/c/Windows/System32")


def _workspace_wsl_interop_root() -> Path:
    """Return the host-side WSL interop runtime directory."""
    return Path("/run/WSL")


def _workspace_wsl_init_path() -> Path:
    """Return the host-side WSL init binary used by Windows interop."""
    return Path("/init")


def _workspace_host_browser_open_command() -> str:
    """Return the in-container helper used to reach the host browser."""
    return "/usr/local/bin/ft-host-browser-open"


def _workspace_host_browser_bridge_dir(profile_name: str) -> Path:
    """Return the host-side directory used for browser bridge runtime state."""
    return _workspace_state_root() / profile_name / "host-browser"


def _workspace_container_host_browser_bridge_dir() -> str:
    """Return the in-container directory used for host browser bridge mounts."""
    return "/tmp/dev-fortress-host-services"


def _workspace_container_host_browser_socket() -> str:
    """Return the in-container Unix socket path for host browser bridge traffic."""
    return (
        f"{_workspace_container_host_browser_bridge_dir()}/browser-open.sock"
    )


def _workspace_host_browser_opener_command() -> list[str] | None:
    """Resolve the preferred host-side browser opener command."""
    override = os.environ.get("DEV_FORTRESS_HOST_BROWSER_OPENER")
    if override:
        return shlex.split(override)
    if _host_runs_under_wsl() and shutil.which("wslview"):
        return ["wslview"]
    browser = os.environ.get("BROWSER")
    if browser:
        return shlex.split(browser)
    if shutil.which("xdg-open"):
        return ["xdg-open"]
    return None


def _workspace_pid_is_alive(pid: int) -> bool:
    """Return whether one process id is currently alive."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _ensure_workspace_host_browser_bridge(profile_name: str) -> Path | None:
    """Ensure the host-side browser bridge broker is running and return its socket."""
    opener_command = _workspace_host_browser_opener_command()
    if opener_command is None:
        return None

    bridge_dir = _workspace_host_browser_bridge_dir(profile_name)
    bridge_dir.mkdir(parents=True, exist_ok=True)
    socket_path = bridge_dir / "browser-open.sock"
    pid_path = bridge_dir / "browser-open.pid"
    command_path = bridge_dir / "browser-open.command"
    opener_signature = json.dumps(opener_command)

    if pid_path.is_file():
        try:
            existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
        except ValueError:
            existing_pid = 0
        existing_signature = ""
        if command_path.is_file():
            existing_signature = command_path.read_text(encoding="utf-8").strip()
        if existing_pid > 0 and socket_path.exists() and _workspace_pid_is_alive(
            existing_pid
        ) and existing_signature == opener_signature:
            return socket_path
        if existing_pid > 0 and _workspace_pid_is_alive(existing_pid):
            try:
                os.kill(existing_pid, signal.SIGTERM)
            except OSError:
                pass

    if socket_path.exists():
        socket_path.unlink()

    command = [
        sys.executable,
        "-m",
        "ft.browser_bridge",
        str(socket_path),
        *opener_command,
    ]
    process = subprocess.Popen(
        command,
        cwd=str(_repo_root() / "ft"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    command_path.write_text(f"{opener_signature}\n", encoding="utf-8")

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if socket_path.exists():
            return socket_path
        if process.poll() is not None:
            break
        time.sleep(0.05)
    return None


def _workspace_host_checkout_mounts(
    shell_config_checkout: Path | None,
) -> list[tuple[Path, str]]:
    """Return required and optional host checkout mounts for one workspace."""
    mounts: list[tuple[Path, str]] = [
        (_repo_root(), "/workspace/dev-container-fortress"),
    ]
    resolved_shell_config = _workspace_runtime_shell_config_checkout(
        shell_config_checkout
    )
    if resolved_shell_config is not None:
        mounts.append((resolved_shell_config, "/workspace/shell-config"))
    return mounts


def _workspace_mount_plan(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> list[tuple[Path, str]]:
    """Return the complete host-to-container mount plan for one workspace profile."""
    mounts = _workspace_host_checkout_mounts(shell_config_checkout)
    for mount_name in profile.persisted_mounts:
        mounts.append(
            (
                _workspace_persisted_host_path(profile_name, mount_name),
                _workspace_persisted_container_path(mount_name),
            )
        )
    return mounts


def _workspace_mount_plan_payload(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> dict[str, object]:
    """Return a machine-readable mount plan payload for one workspace profile."""
    mounts = _workspace_mount_plan(
        profile_name,
        profile,
        shell_config_checkout=shell_config_checkout,
    )
    shell_config = _workspace_shell_config_resolution(shell_config_checkout)
    return {
        "profile": profile_name,
        "target": profile.container_target,
        "working_directory": profile.working_directory,
        "tool_layers": [
            {
                "name": layer_name,
                "mode": layer_definition.mode,
                "description": layer_definition.description,
                "build_arg": layer_definition.build_arg,
            }
            for layer_name, layer_definition in _workspace_tool_layer_definitions(profile)
        ],
        "image_build_layers": [
            layer_name for layer_name, _ in _workspace_image_build_layers(profile)
        ],
        "state_only_layers": [
            layer_name for layer_name, _ in _workspace_state_only_layers(profile)
        ],
        "shell_config": shell_config,
        "shell_config_checkout": shell_config["resolved_path"],
        "mounts": [
            {
                "host_path": str(host_path),
                "container_path": container_path,
            }
            for host_path, container_path in mounts
        ],
    }


def _workspace_auth_checks(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
) -> list[dict[str, str]]:
    """Return structured auth and persisted-state checks for one workspace profile."""
    checks: list[dict[str, str]] = []

    def add_check(*, stat: str, check: str, detail: str) -> None:
        checks.append({"stat": stat, "check": check, "detail": detail})

    ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
    if ssh_auth_sock:
        ssh_auth_sock_path = Path(ssh_auth_sock)
        passed = ssh_auth_sock_path.exists()
        add_check(
            stat="OK" if passed else "WARN",
            check="ssh_agent",
            detail=str(ssh_auth_sock_path)
            if passed
            else f"missing {ssh_auth_sock_path}",
        )
    else:
        add_check(
            stat="WARN",
            check="ssh_agent",
            detail="SSH_AUTH_SOCK not set; SSH agent forwarding will be unavailable",
        )

    gh_browser = os.environ.get("GH_BROWSER")
    browser = os.environ.get("BROWSER")
    if gh_browser:
        add_check(
            stat="OK",
            check="gh_browser_env",
            detail=gh_browser,
        )
    elif browser:
        add_check(
            stat="OK",
            check="browser_env",
            detail=browser,
        )
    else:
        add_check(
            stat="INFO",
            check="browser_env",
            detail=(
                "BROWSER and GH_BROWSER are not set; gh will rely on in-container "
                "browser opener discovery and may fall back to device code"
            ),
        )

    if _host_runs_under_wsl():
        windows_system_path = _workspace_wsl_windows_system_path()
        if windows_system_path.is_dir():
            add_check(
                stat="OK",
                check="browser_strategy",
                detail=(
                    "WSL host detected; workspace will mount "
                    f"{windows_system_path} and forward WSL interop runtime paths; "
                    "default browser launch will go through "
                    f"{_workspace_host_browser_open_command()} when no explicit "
                    "browser env is set"
                ),
            )
        else:
            add_check(
                stat="WARN",
                check="browser_strategy",
                detail=(
                    "WSL host detected but /mnt/c/Windows/System32 is unavailable; "
                    "container browser launch may fall back to device code"
                ),
            )
    else:
        add_check(
            stat="INFO",
            check="browser_strategy",
            detail="standard Linux browser opener flow",
        )

    browser_bridge_opener = _workspace_host_browser_opener_command()
    if browser_bridge_opener is not None:
        add_check(
            stat="OK",
            check="host_browser_bridge",
            detail="host browser opener available",
        )
    else:
        add_check(
            stat="INFO",
            check="host_browser_bridge",
            detail="not available; container will rely on in-container opener behavior",
        )

    mount_checks: list[tuple[str, str]] = [
        ("gh", "github_cli_state"),
        ("glab", "gitlab_cli_state"),
        ("aws", "aws_cli_state"),
        ("azure", "azure_cli_state"),
    ]
    for mount_name, check_name in mount_checks:
        if mount_name not in profile.persisted_mounts:
            add_check(
                stat="INFO",
                check=check_name,
                detail=f"not part of profile {profile_name}",
            )
            continue
        host_path = _workspace_persisted_host_path(profile_name, mount_name)
        add_check(
            stat="OK" if host_path.is_dir() else "WARN",
            check=check_name,
            detail=str(host_path) if host_path.is_dir() else f"missing {host_path}",
        )

    if "secrets" in profile.tool_layers:
        add_check(
            stat="WARN",
            check="secrets_baseline",
            detail="workspace secrets baseline is not implemented yet; see M7a",
        )
    else:
        add_check(
            stat="INFO",
            check="secrets_baseline",
            detail=f"not part of profile {profile_name}",
        )

    return checks


def _workspace_layer_command_checks(
    profile: WorkspaceProfileDefinition,
) -> list[str]:
    """Return runtime command checks implied by the workspace image-build layers."""
    checks: list[str] = []
    for layer_name, _ in _workspace_image_build_layers(profile):
        if layer_name == "gitforge":
            checks.extend(["gh", "glab", "xdg-open"])
        if layer_name == "aws":
            checks.append("aws")
    return checks


def _build_workspace_auth_doctor_report(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
) -> dict[str, object]:
    """Build a structured auth-handoff report for one workspace profile."""
    checks = _workspace_auth_checks(profile_name, profile)
    overall_success = all(check["stat"] not in {"FAIL", "WARN"} for check in checks)
    next_step = (
        "start the workspace with `ft workspace up "
        f"{profile_name}` after any missing auth or state paths are addressed."
    )
    return {
        "success": overall_success,
        "profile": profile_name,
        "target": profile.container_target,
        "tool_layers": [
            {
                "name": layer_name,
                "mode": layer_definition.mode,
                "description": layer_definition.description,
            }
            for layer_name, layer_definition in _workspace_tool_layer_definitions(profile)
        ],
        "checks": checks,
        "next_step": next_step,
    }


def _render_workspace_auth_doctor_report(report: dict[str, object]) -> None:
    """Render one workspace auth-doctor report in the standard human-readable format."""
    console.print("[bold]workspace auth checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )
    console.print(f"next: {report['next_step']}")


def _run_workspace_auth_doctor(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    json_output: bool = False,
) -> bool:
    """Render an auth-handoff report for one workspace profile."""
    report = _build_workspace_auth_doctor_report(profile_name, profile)
    if json_output:
        _json_dump(report)
    else:
        _render_workspace_auth_doctor_report(report)
    return bool(report["success"])


def _validate_workspace_auth_runtime(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
) -> dict[str, object]:
    """Validate runtime auth helpers and selected auth-oriented CLIs in one workspace."""
    container_name = _workspace_container_name(profile_name)
    checks: list[dict[str, str]] = []
    success = True

    def add_result(*, stat: str, check: str, detail: str) -> None:
        checks.append({"stat": stat, "check": check, "detail": detail})

    inspect_result = _run_command(["docker", "container", "inspect", container_name])
    if inspect_result.returncode != 0:
        add_result(
            stat="FAIL",
            check="workspace",
            detail=f"workspace not found: {container_name}",
        )
        return {
            "profile": profile_name,
            "container": container_name,
            "success": False,
            "checks": checks,
        }

    runtime_checks = [
        (
            "browser_helper",
            "test -x /usr/local/bin/ft-host-browser-open && print -r -- ready",
        ),
        (
            "browser_env",
            (
                'if [ -n "${BROWSER:-}" ]; then print -r -- "${BROWSER}"; '
                'elif [ -n "${GH_BROWSER:-}" ]; then print -r -- "${GH_BROWSER}"; '
                "else print -r -- unset; fi"
            ),
        ),
        (
            "host_browser_socket",
            (
                'socket_path="${DEV_FORTRESS_HOST_BROWSER_SOCKET:-}"; '
                'if [ -z "${socket_path}" ]; then print -r -- unset; '
                'elif [ -S "${socket_path}" ]; then print -r -- "${socket_path}"; '
                'else print -r -- "missing ${socket_path}"; exit 1; fi'
            ),
        ),
    ]

    for check_name, command in runtime_checks:
        ok, output = _shell_text(container_name, command)
        normalized_output = _last_non_empty_line(output)
        if check_name == "browser_helper":
            passed = ok and normalized_output == "ready"
            if passed:
                add_result(stat="OK", check=check_name, detail=normalized_output)
                continue
            add_result(
                stat="FAIL",
                check=check_name,
                detail=normalized_output or output or "check failed",
            )
            success = False
            continue
        if check_name == "browser_env":
            add_result(
                stat="OK" if normalized_output != "unset" else "INFO",
                check=check_name,
                detail=(
                    normalized_output
                    if normalized_output != "unset"
                    else "not configured in running workspace"
                ),
            )
            continue
        if check_name == "host_browser_socket":
            if ok and normalized_output:
                add_result(stat="OK", check=check_name, detail=normalized_output)
                continue
            if normalized_output == "unset":
                add_result(
                    stat="INFO",
                    check=check_name,
                    detail="not configured in running workspace",
                )
                continue
            add_result(
                stat="FAIL",
                check=check_name,
                detail=normalized_output or output or "check failed",
            )
            success = False

    for command_name in _workspace_layer_command_checks(profile):
        ok, output = _shell_text(container_name, f"command -v -- '{command_name}'")
        normalized_output = _last_non_empty_line(output)
        add_result(
            stat="OK" if ok else "FAIL",
            check=f"{command_name}_command",
            detail=normalized_output or "command not found",
        )
        success = success and ok

    if "gitforge" in profile.tool_layers:
        for check_name, command in (
            (
                "gh_login_state",
                "gh auth status >/dev/null 2>&1 && print -r -- logged-in || print -r -- not-logged-in",
            ),
            (
                "glab_login_state",
                "glab auth status >/dev/null 2>&1 && print -r -- logged-in || print -r -- not-logged-in",
            ),
        ):
            ok, output = _shell_text(container_name, command)
            normalized_output = _last_non_empty_line(output)
            add_result(
                stat="OK" if ok and normalized_output == "logged-in" else "INFO",
                check=check_name,
                detail=normalized_output or "unknown",
            )

    if "aws" in profile.tool_layers:
        add_result(
            stat="INFO",
            check="aws_login_mode",
            detail=(
                "browser launch is supported in workspace containers, but "
                "localhost callback OAuth is not guaranteed; prefer "
                "`aws sso login --use-device-code` for plain Docker workspaces"
            ),
        )
        for check_name, command, expected in (
            (
                "aws_state",
                (
                    'if [ -f "${HOME}/.aws/config" ] || [ -f "${HOME}/.aws/credentials" ]; '
                    'then print -r -- configured; else print -r -- missing; fi'
                ),
                "configured",
            ),
            (
                "aws_sso_cache",
                (
                    'if [ -d "${HOME}/.aws/sso/cache" ]; '
                    'then print -r -- present; else print -r -- missing; fi'
                ),
                "present",
            ),
        ):
            ok, output = _shell_text(container_name, command)
            normalized_output = _last_non_empty_line(output)
            add_result(
                stat="OK" if ok and normalized_output == expected else "INFO",
                check=check_name,
                detail=normalized_output or "unknown",
            )

    if "azure" in profile.tool_layers:
        add_result(
            stat="INFO",
            check="azure_login_mode",
            detail=(
                "browser launch is supported in workspace containers, but "
                "localhost callback OAuth is not guaranteed; prefer device-code "
                "or equivalent non-localhost flows when available"
            ),
        )
        ok, output = _shell_text(
            container_name,
            (
                'if [ -d "${HOME}/.azure" ] && [ "$(ls -A "${HOME}/.azure" 2>/dev/null)" ]; '
                'then print -r -- configured; else print -r -- missing; fi'
            ),
        )
        normalized_output = _last_non_empty_line(output)
        add_result(
            stat="OK" if ok and normalized_output == "configured" else "INFO",
            check="azure_state",
            detail=normalized_output or "unknown",
        )

    return {
        "profile": profile_name,
        "container": container_name,
        "success": success,
        "checks": checks,
    }


def _validate_workspace_profile(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> dict[str, object]:
    """Validate one mounted workspace container profile and return structured results."""
    container_name = _workspace_container_name(profile_name)
    checks: list[dict[str, str]] = []
    success = True

    def add_result(*, stat: str, check: str, detail: str) -> None:
        checks.append({"stat": stat, "check": check, "detail": detail})

    inspect_result = _run_command(["docker", "container", "inspect", container_name])
    if inspect_result.returncode != 0:
        add_result(
            stat="FAIL",
            check="workspace",
            detail=f"workspace not found: {container_name}",
        )
        return {
            "profile": profile_name,
            "container": container_name,
            "success": False,
            "checks": checks,
        }

    shell_checks = [
        ("runtime_user", "whoami", "vscode"),
        ("working_directory", "pwd", profile.working_directory),
        (
            "active_profile",
            'print -r -- "${SHELL_CONFIG_PROFILE:-}"',
            "zsh-tll-citadel-dev-fortress",
        ),
        ("path_local_bin", 'print -r -- "$PATH"', "/home/vscode/.local/bin"),
        (
            "workspace_repo_mount",
            'test -d /workspace/dev-container-fortress && print -r -- mounted',
            "mounted",
        ),
    ]

    shell_config = _workspace_shell_config_resolution(shell_config_checkout)
    if bool(shell_config["available"]):
        shell_checks.append(
            (
                "shell_config_mount",
                'test -d /workspace/shell-config && print -r -- mounted',
                "mounted",
            )
        )
    else:
        add_result(
            stat="INFO",
            check="shell_config_mount",
            detail=str(shell_config["detail"]),
        )

    for check_name, command, expected in shell_checks:
        ok, output = _shell_text(container_name, command)
        if not ok:
            add_result(stat="FAIL", check=check_name, detail=output)
            success = False
            continue
        if check_name == "path_local_bin":
            passed = f":{expected}:" in f":{output}:"
            detail = expected if passed else f"missing {expected}"
        else:
            normalized_output = _last_non_empty_line(output)
            passed = normalized_output == expected
            detail = (
                normalized_output
                if passed
                else f"expected {expected}, got {normalized_output or output}"
            )
        add_result(
            stat="OK" if passed else "FAIL",
            check=check_name,
            detail=detail,
        )
        success = success and passed

    for command_name in _workspace_layer_command_checks(profile):
        ok, output = _shell_text(container_name, f"command -v -- '{command_name}'")
        normalized_output = _last_non_empty_line(output)
        add_result(
            stat="OK" if ok else "FAIL",
            check=command_name,
            detail=normalized_output or "command not found",
        )
        success = success and ok

    return {
        "profile": profile_name,
        "container": container_name,
        "success": success,
        "checks": checks,
    }


def _workspace_status_value(profile_name: str) -> str:
    """Return the current Docker status value for one managed workspace container."""
    result = _run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Status}}",
            _workspace_container_name(profile_name),
        ]
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "missing"


def _workspace_exists(profile_name: str) -> bool:
    """Return whether the managed workspace container currently exists."""
    result = _run_command(
        ["docker", "container", "inspect", _workspace_container_name(profile_name)]
    )
    return result.returncode == 0


def _render_workspace_status(profile_names: list[str]) -> None:
    """Render a simple status table for one or more managed workspace profiles."""
    manifest = _load_workspace_profile_manifest()
    table = Table(title="dev-container-fortress workspaces")
    table.add_column("profile", style="cyan")
    table.add_column("target", style="white")
    table.add_column("container", style="white")
    table.add_column("image", style="white")
    table.add_column("status", style="white")

    for profile_name in profile_names:
        profile = manifest.profiles[profile_name]
        table.add_row(
            profile_name,
            profile.container_target,
            _workspace_container_name(profile_name),
            _workspace_image_tag(profile_name),
            _workspace_status_value(profile_name),
        )

    console.print(table)


def _configured_host_config_path(config_path: Path | None) -> Path:
    """Return the resolved host-target config path for the current invocation."""
    if config_path is not None:
        return config_path
    settings = FtSettings()
    if settings.host_config is not None:
        return settings.host_config
    return _default_host_config_path()


def _load_host_target_manifest(
    config_path: Path | None = None,
) -> tuple[Path, HostTargetManifest]:
    """Load and validate the configured host-target manifest."""
    if config_path is None:
        settings = FtSettings()
        if settings.host_config is None:
            example_path = _example_host_config_path()
            default_path = _default_host_config_path()
            base_manifest: HostTargetManifest | None = None
            if example_path.is_file():
                with example_path.open("rb") as handle:
                    base_manifest = HostTargetManifest.model_validate(
                        tomllib.load(handle)
                    )
            if default_path.is_file():
                with default_path.open("rb") as handle:
                    user_manifest = HostTargetManifest.model_validate(
                        tomllib.load(handle)
                    )
                merged_manifest = _upsert_host_targets(
                    base_manifest, user_manifest.targets
                )
                return default_path, merged_manifest
            if base_manifest is not None:
                return example_path, base_manifest

    resolved_path = _configured_host_config_path(config_path)
    if not resolved_path.is_file():
        raise typer.BadParameter(
            (
                f"host target config not found: {resolved_path}. "
                f"Start from {_example_host_config_path()}."
            ),
            param_hint="--config",
        )

    with resolved_path.open("rb") as handle:
        manifest_data = tomllib.load(handle)
    return resolved_path, HostTargetManifest.model_validate(manifest_data)


def _load_optional_host_target_manifest(
    config_path: Path | None = None,
) -> tuple[Path, HostTargetManifest | None]:
    """Load a host-target manifest when present, otherwise return the resolved path."""
    resolved_path = _configured_host_config_path(config_path)
    if not resolved_path.is_file():
        return resolved_path, None
    with resolved_path.open("rb") as handle:
        manifest_data = tomllib.load(handle)
    return resolved_path, HostTargetManifest.model_validate(manifest_data)


def _toml_quote(value: str) -> str:
    """Return one TOML-safe quoted string."""
    return json.dumps(value)


def _toml_inline_list(values: list[str]) -> str:
    """Render one simple TOML inline string list."""
    return "[" + ", ".join(_toml_quote(value) for value in values) + "]"


def _host_target_manifest_toml(manifest: HostTargetManifest) -> str:
    """Render a host-target manifest in a small deterministic TOML shape."""
    lines: list[str] = []
    for index, target in enumerate(manifest.targets):
        if index > 0:
            lines.append("")
        lines.append("[[targets]]")
        lines.append(f"name = {_toml_quote(target.name)}")
        lines.append(f"kind = {_toml_quote(target.kind)}")
        if target.connection != "ssh":
            lines.append(f"connection = {_toml_quote(target.connection)}")
        if target.host is not None:
            lines.append(f"host = {_toml_quote(target.host)}")
        if target.user is not None:
            lines.append(f"user = {_toml_quote(target.user)}")
        if target.port != 22:
            lines.append(f"port = {target.port}")
        if target.auth_method != "ssh_key":
            lines.append(f"auth_method = {_toml_quote(target.auth_method)}")
        if target.ssh_key_name is not None:
            lines.append(f"ssh_key_name = {_toml_quote(target.ssh_key_name)}")
        if target.ansible_python_interpreter is not None:
            lines.append(
                "ansible_python_interpreter = "
                f"{_toml_quote(target.ansible_python_interpreter)}"
            )
        lines.append(f"tags = {_toml_inline_list(target.tags)}")
    lines.append("")
    return "\n".join(lines)


def _upsert_host_targets(
    existing_manifest: HostTargetManifest | None,
    imported_targets: list[HostTargetDefinition],
) -> HostTargetManifest:
    """Upsert imported targets into an existing manifest by target name."""
    merged_targets: list[HostTargetDefinition] = []
    imported_by_name = {target.name: target for target in imported_targets}
    if existing_manifest is not None:
        for target in existing_manifest.targets:
            replacement = imported_by_name.pop(target.name, None)
            merged_targets.append(replacement or target)
    merged_targets.extend(imported_by_name[name] for name in sorted(imported_by_name))
    return HostTargetManifest.model_validate({"targets": merged_targets})


def _default_disposable_ubuntu_terraform_dir() -> Path:
    """Return the repo-local Terraform directory for the disposable Ubuntu host."""
    return _repo_root() / "infra" / "aws-disposable-ubuntu"


def _default_disposable_ubuntu_seed_config_path() -> Path:
    """Return the repo-local seed host manifest for the disposable Ubuntu stack."""
    return _default_disposable_ubuntu_terraform_dir() / "hosts.seed.toml"


def _terraform_output_payload(terraform_dir: Path) -> dict[str, object]:
    """Return parsed `terraform output -json` for one Terraform working directory."""
    if shutil.which("terraform") is None:
        raise typer.BadParameter(
            "terraform not found in PATH",
            param_hint="--terraform-dir",
        )
    if not terraform_dir.is_dir():
        raise typer.BadParameter(
            f"terraform directory not found: {terraform_dir}",
            param_hint="--terraform-dir",
        )

    result = _run_command(
        ["terraform", "-chdir=" + str(terraform_dir), "output", "-json"]
    )
    if result.returncode != 0:
        detail = (
            _last_non_empty_line(result.stderr or result.stdout)
            or "terraform output -json failed"
        )
        console.print(detail)
        raise typer.Exit(code=1)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise typer.BadParameter(
            "terraform output did not return valid JSON",
            param_hint="--terraform-dir",
        ) from error
    if not isinstance(payload, dict):
        raise typer.BadParameter(
            "terraform output payload was not a JSON object",
            param_hint="--terraform-dir",
        )
    return payload


def _terraform_host_target_manifest(terraform_dir: Path) -> HostTargetManifest:
    """Parse the host-target manifest emitted by Terraform outputs."""
    payload = _terraform_output_payload(terraform_dir)
    fragment_record = payload.get("host_target_toml_fragment")
    if not isinstance(fragment_record, dict) or "value" not in fragment_record:
        raise typer.BadParameter(
            "terraform output is missing host_target_toml_fragment",
            param_hint="--terraform-dir",
        )
    fragment_value = fragment_record["value"]
    if not isinstance(fragment_value, str):
        raise typer.BadParameter(
            "terraform host_target_toml_fragment value must be a TOML string",
            param_hint="--terraform-dir",
        )
    try:
        manifest_data = tomllib.loads(fragment_value)
    except tomllib.TOMLDecodeError as error:
        raise typer.BadParameter(
            "terraform host_target_toml_fragment is not valid TOML",
            param_hint="--terraform-dir",
        ) from error
    return HostTargetManifest.model_validate(manifest_data)


def _import_terraform_host_targets(
    terraform_dir: Path, config_path: Path | None
) -> dict[str, object]:
    """Import Terraform-emitted host targets into the configured hosts.toml."""
    imported_manifest = _terraform_host_target_manifest(terraform_dir)
    resolved_path, existing_manifest = _load_optional_host_target_manifest(config_path)
    merged_manifest = _upsert_host_targets(existing_manifest, imported_manifest.targets)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        _host_target_manifest_toml(merged_manifest), encoding="utf-8"
    )
    return {
        "config": str(resolved_path),
        "terraform_dir": str(terraform_dir),
        "imported_targets": [target.name for target in imported_manifest.targets],
        "total_targets": len(merged_manifest.targets),
    }


def _resolve_host_targets(
    selector: str, manifest: HostTargetManifest
) -> list[HostTargetDefinition]:
    """Resolve one exact, wildcard, or all-style host target selector."""
    targets_by_name = manifest.by_name()
    names = list(targets_by_name)
    if selector == "all":
        return [targets_by_name[name] for name in names]
    if selector in targets_by_name:
        return [targets_by_name[selector]]

    matches = [
        targets_by_name[name] for name in names if fnmatch.fnmatch(name, selector)
    ]
    if matches:
        return matches

    supported = ", ".join(names)
    raise typer.BadParameter(
        f"selector {selector!r} matched no known host targets (supported: {supported})",
        param_hint="target",
    )


def _interactive_select_host_targets(
    targets: list[HostTargetDefinition],
) -> list[HostTargetDefinition]:
    """Interactively select one or more host targets with prompt-toolkit."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise typer.BadParameter(
            "--interactive requires an interactive terminal",
            param_hint="--interactive",
        )
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import TextArea
    except ImportError as error:
        raise typer.BadParameter(
            "prompt-toolkit is not installed; run `uv sync` first",
            param_hint="--interactive",
        ) from error

    if not targets:
        return []

    selected_names: set[str] = set()
    cursor_index = 0
    result: list[HostTargetDefinition] = []
    query_field = TextArea(
        text="",
        multiline=False,
        prompt=[("class:prompt.label", "filter"), ("class:prompt.sep", "> ")],
        focus_on_click=True,
        style="class:prompt.input",
    )
    selector_style = Style.from_dict(
        {
            "frame.title": "bold #8be9fd",
            "frame.subtitle": "#6272a4",
            "prompt.label": "bold #50fa7b",
            "prompt.sep": "bold #8be9fd",
            "prompt.input": "#f8f8f2 bg:#1f2335",
            "divider": "#3b4261",
            "pointer": "bold #8be9fd",
            "checkbox.on": "bold #50fa7b",
            "checkbox.off": "#6272a4",
            "target.name": "bold #f8f8f2",
            "target.meta": "#a9b1d6",
            "target.count": "#7aa2f7",
            "target.empty": "#6272a4 italic",
            "target.active.pointer": "bold #1f2335 bg:#7aa2f7",
            "target.active.checkbox.on": "bold #1f2335 bg:#7aa2f7",
            "target.active.checkbox.off": "bold #1f2335 bg:#7aa2f7",
            "target.active.name": "bold #1f2335 bg:#7aa2f7",
            "target.active.meta": "#1f2335 bg:#7aa2f7",
            "footer": "#6272a4",
            "footer.key": "bold #8be9fd",
        }
    )

    def filtered_targets() -> list[HostTargetDefinition]:
        query = query_field.text.strip().lower()
        if not query:
            return targets
        return [
            target
            for target in targets
            if query in target.name.lower()
            or query in target.kind.lower()
            or any(query in tag.lower() for tag in target.tags)
        ]

    def clamp_cursor() -> None:
        nonlocal cursor_index
        matches = filtered_targets()
        if not matches:
            cursor_index = 0
            return
        cursor_index = max(0, min(cursor_index, len(matches) - 1))

    def render_target_list() -> list[tuple[str, str]]:
        matches = filtered_targets()
        if not matches:
            return [
                ("class:target.empty", "  no targets match the current filter"),
            ]

        fragments: list[tuple[str, str]] = []
        for index, target in enumerate(matches):
            is_active = index == cursor_index
            pointer = ">" if is_active else " "
            checkbox = "[x]" if target.name in selected_names else "[ ]"
            tags = ", ".join(target.tags)
            detail = f"{target.kind}"
            if tags:
                detail = f"{detail} | {tags}"
            prefix = "target.active" if is_active else "target"
            checkbox_style = (
                "checkbox.on" if target.name in selected_names else "checkbox.off"
            )
            fragments.extend(
                [
                    (f"class:{prefix}.pointer", f"{pointer} "),
                    (f"class:{prefix}.{checkbox_style}", f"{checkbox} "),
                    (f"class:{prefix}.name", target.name),
                    (f"class:{prefix}.meta", f"  {detail}\n"),
                ]
            )
        return fragments

    def render_header() -> list[tuple[str, str]]:
        return [
            ("class:frame.title", "Dev Fortress Target Selector"),
            (
                "class:frame.subtitle",
                f"  {len(filtered_targets())}/{len(targets)} visible",
            ),
        ]

    def render_footer() -> list[tuple[str, str]]:
        return [
            ("class:footer.key", "Up/Down"),
            ("class:footer", " move  "),
            ("class:footer.key", "Space"),
            ("class:footer", " toggle  "),
            ("class:footer.key", "Enter"),
            ("class:footer", " confirm  "),
            ("class:footer.key", "Esc"),
            ("class:footer", " cancel"),
        ]

    instructions = Window(
        FormattedTextControl(render_header),
        height=1,
    )
    result_window = Window(
        FormattedTextControl(render_target_list),
        always_hide_cursor=True,
    )
    footer = Window(
        FormattedTextControl(render_footer),
        height=1,
    )

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _move_up(event: object) -> None:
        nonlocal cursor_index
        if filtered_targets():
            cursor_index = max(0, cursor_index - 1)

    @kb.add("down")
    @kb.add("j")
    def _move_down(event: object) -> None:
        nonlocal cursor_index
        matches = filtered_targets()
        if matches:
            cursor_index = min(len(matches) - 1, cursor_index + 1)

    @kb.add("space")
    def _toggle_current(event: object) -> None:
        matches = filtered_targets()
        if not matches:
            return
        target = matches[cursor_index]
        if target.name in selected_names:
            selected_names.remove(target.name)
        else:
            selected_names.add(target.name)

    @kb.add("enter")
    def _accept(event: object) -> None:
        matches = filtered_targets()
        if not matches:
            return
        if not selected_names:
            selected_names.add(matches[cursor_index].name)
        selected_lookup = set(selected_names)
        result.extend([target for target in targets if target.name in selected_lookup])
        event.app.exit(result=result)

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: object) -> None:
        event.app.exit(result=[])

    @query_field.buffer.on_text_changed.add_handler
    def _on_text_changed(_: object) -> None:
        clamp_cursor()

    layout = Layout(
        HSplit(
            [
                instructions,
                query_field,
                Window(height=1, char="-", style="class:divider"),
                result_window,
                Window(height=1, char="-", style="class:divider"),
                footer,
            ]
        ),
        focused_element=query_field,
    )
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=selector_style,
        full_screen=False,
        mouse_support=False,
        refresh_interval=0.1,
    )
    selected = app.run()
    if not selected:
        raise typer.Exit(code=1)
    return selected


def _resolve_single_host_target(
    selector: str,
    manifest: HostTargetManifest,
    *,
    command_name: str,
) -> HostTargetDefinition:
    """Resolve exactly one host target for non-fan-out host commands."""
    resolved_targets = _resolve_host_targets(selector, manifest)
    if len(resolved_targets) == 1:
        return resolved_targets[0]

    raise typer.BadParameter(
        f"{command_name} requires exactly one target, but {selector!r} matched "
        f"{', '.join(target.name for target in resolved_targets)}",
        param_hint="target",
    )


def _interactive_select_single_host_target(
    targets: list[HostTargetDefinition], *, command_name: str
) -> HostTargetDefinition:
    """Interactively resolve exactly one host target for one command."""
    resolved_targets = _interactive_select_host_targets(targets)
    if len(resolved_targets) == 1:
        return resolved_targets[0]
    raise typer.BadParameter(
        f"{command_name} requires exactly one target, but interactive selection "
        f"returned {len(resolved_targets)} targets",
        param_hint="--interactive",
    )


def _host_ssh_private_key_path(target: HostTargetDefinition) -> Path | None:
    """Return the expected private SSH key path for one host target."""
    if target.connection != "ssh" or target.auth_method != "ssh_key":
        return None
    return (
        _dev_fortress_state_root()
        / "ssh"
        / target.resolved_ssh_key_name()
        / _managed_ssh_key_basename()
    )


def _host_ssh_public_key_path(target: HostTargetDefinition) -> Path | None:
    """Return the expected public SSH key path for one host target."""
    private_path = _host_ssh_private_key_path(target)
    if private_path is None:
        return None
    return private_path.with_name(f"{private_path.name}.pub")


def _seed_host_target_for_name(
    target_name: str,
    seed_config_path: Path,
) -> HostTargetDefinition:
    """Return one seed host target definition for managed key generation."""
    _, manifest = _load_host_target_manifest(seed_config_path)
    return _resolve_single_host_target(
        target_name,
        manifest,
        command_name="infra aws-disposable-ubuntu",
    )


def _ensure_managed_ssh_public_key_for_name(
    target_name: str,
    seed_config_path: Path,
) -> Path:
    """Ensure the managed SSH public key exists for one future host target name."""
    target = _seed_host_target_for_name(target_name, seed_config_path)
    _ensure_managed_host_ssh_key(target)
    public_key_path = _host_ssh_public_key_path(target)
    assert public_key_path is not None
    return public_key_path


def _terraform_env_for_disposable_ubuntu(
    *,
    target_name: str,
    seed_config_path: Path,
) -> dict[str, str]:
    """Build the Terraform environment for the disposable Ubuntu stack."""
    public_key_path = _ensure_managed_ssh_public_key_for_name(
        target_name, seed_config_path
    )
    public_key_text = public_key_path.read_text(encoding="utf-8").strip()
    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_VAR_name"] = target_name
    env["TF_VAR_ssh_public_key"] = public_key_text
    return env


def _run_disposable_ubuntu_terraform(
    terraform_args: list[str],
    *,
    terraform_dir: Path,
    target_name: str,
    seed_config_path: Path,
) -> int:
    """Run one Terraform command for the disposable Ubuntu stack."""
    if shutil.which("terraform") is None:
        console.print("terraform not found in PATH")
        raise typer.Exit(code=1)
    if not terraform_dir.is_dir():
        raise typer.BadParameter(
            f"terraform directory not found: {terraform_dir}",
            param_hint="--terraform-dir",
        )

    env = _terraform_env_for_disposable_ubuntu(
        target_name=target_name,
        seed_config_path=seed_config_path,
    )
    command = ["terraform", "-chdir=" + str(terraform_dir), *terraform_args]
    return _run_streaming_command(command, env=env).returncode


def _host_known_hosts_path(target: HostTargetDefinition) -> Path | None:
    """Return the managed known-hosts path for one SSH host target."""
    if target.connection != "ssh":
        return None
    return _dev_fortress_state_root() / "known_hosts" / target.name


def _uses_managed_known_hosts(target: HostTargetDefinition) -> bool:
    """Return whether the target should use the Dev Fortress managed known-hosts file."""
    return target.kind in {"docker", "cloud"}


def _refresh_managed_known_host(target: HostTargetDefinition) -> Path | None:
    """Refresh the managed known-hosts entry for one disposable SSH target."""
    known_hosts_path = _host_known_hosts_path(target)
    if known_hosts_path is None:
        return None
    if not _uses_managed_known_hosts(target):
        return known_hosts_path
    if shutil.which("ssh-keyscan") is None:
        console.print("ssh-keyscan not found in PATH")
        raise typer.Exit(code=1)

    known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        known_hosts_path.parent.chmod(0o700)
    except PermissionError:
        pass

    result = _run_command(
        [
            "ssh-keyscan",
            "-p",
            str(target.port),
            str(target.host),
        ]
    )
    if result.returncode != 0 or not (result.stdout or "").strip():
        detail = (
            _last_non_empty_line(result.stderr or result.stdout) or "ssh-keyscan failed"
        )
        console.print(detail)
        raise typer.Exit(code=1)

    known_hosts_path.write_text(result.stdout, encoding="utf-8")
    return known_hosts_path


def _host_ansible_ssh_common_args(target: HostTargetDefinition) -> str | None:
    """Return extra Ansible SSH args for ephemeral or disposable targets."""
    known_hosts_path = _host_known_hosts_path(target)
    if target.connection != "ssh" or known_hosts_path is None:
        return None
    if _uses_managed_known_hosts(target):
        return f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts_path}"
    return None


def _host_ssh_command(target: HostTargetDefinition) -> list[str]:
    """Return the interactive SSH command for one configured SSH host target."""
    if target.connection != "ssh":
        raise typer.BadParameter(
            f"target {target.name!r} does not use ssh transport",
            param_hint="target",
        )
    if shutil.which("ssh") is None:
        console.print("ssh not found in PATH")
        raise typer.Exit(code=1)

    private_key_path = _host_ssh_private_key_path(target)
    if target.auth_method == "ssh_key":
        if private_key_path is None or not private_key_path.is_file():
            console.print(
                f"missing managed ssh key for {target.name}: {private_key_path}"
            )
            console.print(
                "Run `ft host ssh-key <target>` or rerun with a workflow that "
                "ensures managed keys first."
            )
            raise typer.Exit(code=1)

    known_hosts_path = _refresh_managed_known_host(target)

    command = ["ssh", "-p", str(target.port)]
    if target.auth_method == "ssh_key" and private_key_path is not None:
        command.extend(["-i", str(private_key_path)])
    if known_hosts_path is not None and _uses_managed_known_hosts(target):
        command.extend(
            [
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                f"UserKnownHostsFile={known_hosts_path}",
            ]
        )
    command.append(f"{target.user}@{target.host}")
    return command


def _ssh_single_host_target(target: HostTargetDefinition) -> int:
    """Open one interactive SSH session for one configured host target."""
    if not _ensure_host_target_runtime_ready(target):
        console.print(f"failed to prepare runtime for {target.name} before SSH")
        return 1
    return _run_streaming_command(_host_ssh_command(target)).returncode


def _ensure_host_target_runtime_ready(target: HostTargetDefinition) -> bool:
    """Ensure any target-specific runtime prerequisites exist before SSH operations."""
    if target.kind != "docker":
        return True
    container_target = _container_target_for_host_ssh_target_name(target.name)
    if container_target is None:
        return True
    if not _up_single_container_target(container_target):
        return False
    return _wait_for_target_ssh_service(target)


def _wait_for_target_ssh_service(
    target: HostTargetDefinition,
    *,
    attempts: int = 10,
    delay_seconds: float = 1.0,
) -> bool:
    """Wait for one SSH target to start accepting keyscan connections."""
    if shutil.which("ssh-keyscan") is None:
        return True

    for attempt in range(attempts):
        result = _run_command(
            [
                "ssh-keyscan",
                "-T",
                "2",
                "-p",
                str(target.port),
                str(target.host),
            ]
        )
        if result.returncode == 0 and (result.stdout or "").strip():
            return True
        if attempt < attempts - 1:
            time.sleep(delay_seconds)
    return False


def _host_playbook_path() -> Path:
    """Return the repo-local host bootstrap playbook path."""
    return _repo_root() / "ansible" / "playbooks" / "host.yml"


def _ansible_config_path() -> Path:
    """Return the repo-local Ansible configuration path."""
    return _repo_root() / "ansible" / "ansible.cfg"


def _ensure_managed_host_ssh_key(target: HostTargetDefinition) -> tuple[bool, Path]:
    """Ensure the expected managed SSH key exists for one SSH host target."""
    key_path = _host_ssh_private_key_path(target)
    if key_path is None:
        raise typer.BadParameter(
            f"target {target.name!r} does not use a managed ssh key",
            param_hint="target",
        )
    if key_path.exists():
        return False, key_path

    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        key_path.parent.chmod(0o700)
    except PermissionError:
        pass

    result = _run_command(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key_path)]
    )
    if result.returncode != 0:
        detail = (
            _last_non_empty_line(result.stderr or result.stdout) or "ssh-keygen failed"
        )
        console.print(detail)
        raise typer.Exit(code=1)
    return True, key_path


def _enroll_managed_host_ssh_key(target: HostTargetDefinition) -> Path:
    """Enroll one managed public key into the target authorized_keys file."""
    private_key_path = _host_ssh_private_key_path(target)
    public_key_path = _host_ssh_public_key_path(target)
    if private_key_path is None or public_key_path is None:
        raise typer.BadParameter(
            f"target {target.name!r} does not use a managed ssh key",
            param_hint="target",
        )
    if shutil.which("ssh") is None:
        console.print("ssh not found in PATH")
        raise typer.Exit(code=1)

    _ensure_managed_host_ssh_key(target)
    known_hosts_path = _refresh_managed_known_host(target)
    public_key_text = public_key_path.read_text(encoding="utf-8").strip()
    remote_command = (
        "umask 077 && mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && "
        "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && "
        "IFS= read -r key_line && "
        '(grep -qxF "$key_line" ~/.ssh/authorized_keys || '
        "printf '%s\\n' \"$key_line\" >> ~/.ssh/authorized_keys)"
    )
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-i",
        str(private_key_path),
        "-p",
        str(target.port),
        f"{target.user}@{target.host}",
        "sh",
        "-lc",
        remote_command,
    ]
    if known_hosts_path is not None:
        command[5:5] = [
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_path}",
        ]
    result = _run_command_with_input(command, f"{public_key_text}\n")
    if result.returncode != 0:
        detail = (
            _last_non_empty_line(result.stderr or result.stdout)
            or "ssh public key enrollment failed"
        )
        console.print(detail)
        raise typer.Exit(code=1)
    return public_key_path


def _bootstrap_host_targets(
    targets: list[HostTargetDefinition],
    *,
    ensure_ssh_keys: bool,
    check: bool,
    ask_become_pass: bool,
) -> int:
    """Run the host bootstrap playbook for one or more configured targets.

    Args:
        targets: Host targets to bootstrap.
        ensure_ssh_keys: Whether to create managed SSH keys instead of running Ansible.
        check: Whether to run Ansible in check mode.
        ask_become_pass: Whether to pass ``-K`` to ``ansible-playbook``.

    Returns:
        Process exit code from the underlying bootstrap action.
    """
    return int(
        _bootstrap_host_targets_with_result(
            targets,
            ensure_ssh_keys=ensure_ssh_keys,
            check=check,
            ask_become_pass=ask_become_pass,
            capture_recap=False,
        )["returncode"]
    )


def _bootstrap_host_targets_with_result(
    targets: list[HostTargetDefinition],
    *,
    ensure_ssh_keys: bool,
    check: bool,
    ask_become_pass: bool,
    capture_recap: bool,
) -> dict[str, object]:
    """Run the host bootstrap playbook and return execution metadata.

    Args:
        targets: Host targets to bootstrap.
        ensure_ssh_keys: Whether to create managed SSH keys instead of running Ansible.
        check: Whether to run Ansible in check mode.
        ask_become_pass: Whether to pass ``-K`` to ``ansible-playbook``.
        capture_recap: Whether to parse ``PLAY RECAP`` counters from the Ansible log.

    Returns:
        Execution metadata containing the bootstrap exit code and any parsed recap.
    """
    playbook_path = _host_playbook_path()
    ansible_config_path = _ansible_config_path()
    if not playbook_path.is_file():
        console.print(f"missing playbook: {playbook_path}")
        return {"returncode": 1, "target_recaps": {}}
    if not ansible_config_path.is_file():
        console.print(f"missing ansible config: {ansible_config_path}")
        return {"returncode": 1, "target_recaps": {}}
    if shutil.which("ansible-playbook") is None:
        console.print("ansible-playbook not found in PATH")
        return {"returncode": 1, "target_recaps": {}}

    for target in targets:
        key_path = _host_ssh_private_key_path(target)
        if key_path is None:
            continue
        if ensure_ssh_keys:
            created, ensured_path = _ensure_managed_host_ssh_key(target)
            if created:
                console.print(f"generated ssh key: {ensured_path}")
            continue
        if not key_path.exists():
            console.print(
                f"missing managed ssh key for {target.name}: {key_path}. "
                f"Run `ft host ssh-key {target.name}` or use --ensure-ssh-keys."
            )
            return {"returncode": 1, "target_recaps": {}}

    inventory = _build_host_inventory(targets)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".yml", delete=False
    ) as handle:
        handle.write(_yaml_dump(inventory))
        inventory_path = Path(handle.name)

    command = ["ansible-playbook", "-i", str(inventory_path), str(playbook_path)]
    if ask_become_pass:
        command.append("-K")
    if check:
        command.append("--check")
    ansible_env = os.environ.copy()
    ansible_env["ANSIBLE_CONFIG"] = str(ansible_config_path)
    log_path: Path | None = None
    if capture_recap:
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as log_handle:
            log_path = Path(log_handle.name)
        ansible_env["ANSIBLE_LOG_PATH"] = str(log_path)

    try:
        result = _run_streaming_command(command, env=ansible_env)
        target_recaps: dict[str, dict[str, int]] = {}
        if capture_recap and log_path is not None and log_path.exists():
            target_recaps = _parse_ansible_play_recap(
                log_path.read_text(encoding="utf-8", errors="replace")
            )
        return {"returncode": result.returncode, "target_recaps": target_recaps}
    finally:
        inventory_path.unlink(missing_ok=True)
        if log_path is not None:
            log_path.unlink(missing_ok=True)


def _probe_ssh_target(target: HostTargetDefinition) -> tuple[bool, str]:
    """Attempt a small non-interactive SSH probe for one configured target."""
    key_path = _host_ssh_private_key_path(target)
    if key_path is None:
        return False, "target does not use a managed ssh key"
    known_hosts_path = _refresh_managed_known_host(target)
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-i",
        str(key_path),
        "-p",
        str(target.port),
        f"{target.user}@{target.host}",
        "true",
    ]
    if known_hosts_path is not None:
        command[5:5] = [
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_path}",
        ]
    result = _run_command(command)
    if result.returncode == 0:
        return True, "ssh probe succeeded"
    return False, _last_non_empty_line(
        result.stderr or result.stdout
    ) or "ssh probe failed"


def _build_host_doctor_report(
    targets: list[HostTargetDefinition],
    *,
    config_path: Path,
    probe: bool,
) -> dict[str, object]:
    """Build a structured readiness report for configured host targets."""
    overall_success = True
    host_checks: list[dict[str, str]] = []
    target_checks: list[dict[str, str]] = []

    host_checks.append(
        {
            "stat": "OK",
            "check": "host_config",
            "detail": str(config_path),
        }
    )

    ansible_playbook = shutil.which("ansible-playbook")
    host_checks.append(
        {
            "stat": "OK" if ansible_playbook else "FAIL",
            "check": "ansible_playbook",
            "detail": ansible_playbook or "ansible-playbook not found in PATH",
        }
    )
    overall_success = overall_success and bool(ansible_playbook)

    ssh_command = shutil.which("ssh")
    if any(target.connection == "ssh" for target in targets):
        host_checks.append(
            {
                "stat": "OK" if ssh_command else "FAIL",
                "check": "ssh_client",
                "detail": ssh_command or "ssh not found in PATH",
            }
        )
        overall_success = overall_success and bool(ssh_command)

    for target in targets:
        if target.connection == "local":
            target_checks.append(
                {
                    "stat": "OK",
                    "check": f"{target.name}_connection",
                    "detail": "local target uses ansible_connection=local",
                }
            )
            continue

        key_path = _host_ssh_private_key_path(target)
        key_present = key_path is not None and key_path.exists()
        target_checks.append(
            {
                "stat": "OK" if key_present else "FAIL",
                "check": f"{target.name}_ssh_key",
                "detail": str(key_path) if key_present else f"missing {key_path}",
            }
        )
        overall_success = overall_success and key_present

        if not probe:
            target_checks.append(
                {
                    "stat": "WARN",
                    "check": f"{target.name}_ssh_probe",
                    "detail": "skipped (use --probe to test SSH reachability)",
                }
            )
            continue
        if not ssh_command or not key_present:
            target_checks.append(
                {
                    "stat": "FAIL",
                    "check": f"{target.name}_ssh_probe",
                    "detail": "probe skipped because ssh client or key is missing",
                }
            )
            overall_success = False
            continue
        if not _ensure_host_target_runtime_ready(target):
            target_checks.append(
                {
                    "stat": "FAIL",
                    "check": f"{target.name}_runtime",
                    "detail": "failed to prepare target runtime before SSH probe",
                }
            )
            overall_success = False
            continue

        probe_ok, probe_detail = _probe_ssh_target(target)
        target_checks.append(
            {
                "stat": "OK" if probe_ok else "FAIL",
                "check": f"{target.name}_ssh_probe",
                "detail": probe_detail,
            }
        )
        overall_success = overall_success and probe_ok

    if not ansible_playbook:
        next_step = "install Ansible, then rerun `ft host doctor`."
    elif any(
        check["stat"] == "FAIL" and check["check"].endswith("_ssh_key")
        for check in target_checks
    ):
        next_step = "generate missing keys with `ft host ssh-key <target>` or rerun with `ft host bootstrap --ensure-ssh-keys`."
    elif probe and any(
        check["stat"] == "FAIL" and check["check"].endswith("_ssh_probe")
        for check in target_checks
    ):
        next_step = "verify SSH reachability, host addresses, and remote authorized_keys before rerunning `ft host doctor --probe`."
    else:
        next_step = "use `ft host bootstrap <target>` when the target looks ready."

    return {
        "success": overall_success,
        "config": str(config_path),
        "targets": [target.name for target in targets],
        "probe": probe,
        "host_checks": host_checks,
        "target_checks": target_checks,
        "next_step": next_step,
    }


def _run_host_doctor(
    targets: list[HostTargetDefinition],
    *,
    config_path: Path,
    probe: bool,
    json_output: bool,
) -> bool:
    """Render one host readiness report for humans or agentic callers."""
    report = _build_host_doctor_report(targets, config_path=config_path, probe=probe)
    if json_output:
        _json_dump(report)
        return bool(report["success"])

    console.print("[bold]host checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["host_checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )

    console.print("[bold]target checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["target_checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )

    console.print(f"next: {report['next_step']}")
    return bool(report["success"])


def _validate_host_target(
    target: HostTargetDefinition,
    *,
    config_path: Path,
    json_output: bool,
    ask_become_pass: bool,
) -> bool:
    """Run the standard doctor/bootstrap convergence loop for one host target."""
    results: list[dict[str, object]] = []
    success = _run_host_doctor(
        [target], config_path=config_path, probe=True, json_output=json_output
    )
    results.append({"step": "doctor_probe", "success": success})

    if success:
        success = (
            _bootstrap_host_targets(
                [target],
                ensure_ssh_keys=False,
                check=True,
                ask_become_pass=ask_become_pass,
            )
            == 0
        )
        results.append({"step": "bootstrap_check", "success": success})

    if success:
        success = (
            _bootstrap_host_targets(
                [target],
                ensure_ssh_keys=False,
                check=False,
                ask_become_pass=ask_become_pass,
            )
            == 0
        )
        results.append({"step": "bootstrap_apply", "success": success})

    if success:
        converge_result = _bootstrap_host_targets_with_result(
            [target],
            ensure_ssh_keys=False,
            check=False,
            ask_become_pass=ask_become_pass,
            capture_recap=True,
        )
        converge_success = int(converge_result["returncode"]) == 0
        target_recaps = converge_result["target_recaps"]
        recap = (
            target_recaps[target.name]
            if isinstance(target_recaps, dict) and target.name in target_recaps
            else None
        )
        recap_changed = recap["changed"] if isinstance(recap, dict) else None
        if converge_success and recap_changed is None:
            console.print(
                f"final bootstrap pass for {target.name} did not produce a parseable PLAY RECAP; unable to verify convergence"
            )
            converge_success = False
        if converge_success and recap_changed != 0:
            console.print(
                f"final bootstrap pass for {target.name} did not converge cleanly: changed={recap_changed}"
            )
            converge_success = False
        results.append(
            {
                "step": "bootstrap_converge",
                "success": converge_success,
                "changed": recap_changed,
            }
        )
        success = converge_success

    if json_output:
        _json_dump(
            {
                "target": target.name,
                "config": str(config_path),
                "success": success,
                "steps": results,
            }
        )
    return success


def _host_target_record(target: HostTargetDefinition) -> dict[str, object]:
    """Return one structured host-target record for rendering or JSON output."""
    record: dict[str, object] = {
        "name": target.name,
        "kind": target.kind,
        "connection": target.connection,
        "auth_method": target.auth_method,
        "tags": target.tags,
    }
    if target.host is not None:
        record["host"] = target.host
    if target.user is not None:
        record["user"] = target.user
    if target.connection == "ssh":
        record["port"] = target.port
    if target.ansible_python_interpreter is not None:
        record["ansible_python_interpreter"] = target.ansible_python_interpreter
    private_path = _host_ssh_private_key_path(target)
    public_path = _host_ssh_public_key_path(target)
    if private_path is not None:
        record["ssh_private_key"] = str(private_path)
    if public_path is not None:
        record["ssh_public_key"] = str(public_path)
    known_hosts_path = _host_known_hosts_path(target)
    if known_hosts_path is not None:
        record["known_hosts"] = str(known_hosts_path)
    return record


def _render_host_target_list(targets: list[HostTargetDefinition]) -> None:
    """Render a concise table of known host targets."""
    table = Table(title="Dev Fortress host targets")
    table.add_column("name", style="cyan")
    table.add_column("kind", style="white")
    table.add_column("connection", style="white")
    table.add_column("auth", style="white")
    table.add_column("address", style="white")
    table.add_column("user", style="white")
    table.add_column("tags", style="white")

    for target in targets:
        address = (
            "local" if target.connection == "local" else f"{target.host}:{target.port}"
        )
        table.add_row(
            target.name,
            target.kind,
            target.connection,
            target.auth_method,
            address,
            target.user or "-",
            ", ".join(target.tags) or "-",
        )

    console.print(table)


def _render_host_target_details(target: HostTargetDefinition) -> None:
    """Render a detailed table for one host target."""
    table = Table(title=f"{target.name} host target", show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    for key, value in _host_target_record(target).items():
        if key == "tags":
            display = ", ".join(value) if value else "-"
        else:
            display = str(value)
        table.add_row(key, display)
    console.print(table)


def _build_host_inventory(targets: list[HostTargetDefinition]) -> dict[str, object]:
    """Return an Ansible inventory payload for one or more host targets."""
    hosts: dict[str, dict[str, object]] = {}

    for target in targets:
        host_record: dict[str, object] = {
            "dev_fortress_target_kind": target.kind,
            "dev_fortress_target_tags": target.tags,
        }
        if target.connection == "local":
            host_record["ansible_connection"] = "local"
        else:
            host_record.update(
                {
                    "ansible_connection": "ssh",
                    "ansible_host": target.host,
                    "ansible_port": target.port,
                    "ansible_user": target.user,
                }
            )
            if target.ansible_python_interpreter is not None:
                host_record["ansible_python_interpreter"] = (
                    target.ansible_python_interpreter
                )
            private_path = _host_ssh_private_key_path(target)
            if private_path is not None:
                host_record["ansible_ssh_private_key_file"] = str(private_path)
            ssh_common_args = _host_ansible_ssh_common_args(target)
            if ssh_common_args is not None:
                host_record["ansible_ssh_common_args"] = ssh_common_args
        hosts[target.name] = host_record

    return {
        "all": {
            "children": {
                "dev_fortress": {
                    "hosts": hosts,
                }
            }
        }
    }


def _yaml_scalar(value: object) -> str:
    """Render one YAML-safe scalar for simple inventory output."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _yaml_lines(value: object, *, indent: int = 0) -> list[str]:
    """Render a small YAML subset for dict and list inventory structures."""
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, nested_value in value.items():
            if isinstance(nested_value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(nested_value, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(nested_value)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_dump(value: object) -> str:
    """Render one small YAML document string."""
    return "\n".join(_yaml_lines(value)) + "\n"


def _resolve_container_targets(selector: str) -> list[str]:
    """Resolve one exact, wildcard, or all-style container target selector."""
    if selector == "all":
        return list(KNOWN_CONTAINER_TARGETS)
    if selector in KNOWN_CONTAINER_TARGETS:
        return [selector]

    matches = [
        target
        for target in KNOWN_CONTAINER_TARGETS
        if fnmatch.fnmatch(target, selector)
    ]
    if matches:
        return matches

    supported = ", ".join(KNOWN_CONTAINER_TARGETS)
    raise typer.BadParameter(
        f"selector {selector!r} matched no known targets (supported: {supported})",
        param_hint="target",
    )


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one external command and capture text output."""
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _run_command_with_input(
    command: list[str], input_text: str
) -> subprocess.CompletedProcess[str]:
    """Run one external command with stdin text and capture output."""
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
    )


def _run_streaming_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one external command while inheriting the current terminal streams."""
    return subprocess.run(command, check=False, text=True, env=env)


def _parse_ansible_play_recap(log_text: str) -> dict[str, dict[str, int]]:
    """Parse Ansible ``PLAY RECAP`` counters from one log stream.

    Args:
        log_text: Full Ansible log text.

    Returns:
        Mapping of inventory host name to recap counters.
    """
    recaps: dict[str, dict[str, int]] = {}
    for match in ANSIBLE_PLAY_RECAP_PATTERN.finditer(log_text):
        recaps[match.group("target").strip()] = {
            "ok": int(match.group("ok")),
            "changed": int(match.group("changed")),
            "unreachable": int(match.group("unreachable")),
            "failed": int(match.group("failed")),
            "skipped": int(match.group("skipped")),
            "rescued": int(match.group("rescued")),
            "ignored": int(match.group("ignored")),
        }
    return recaps


def _resolve_single_container_target(selector: str, *, command_name: str) -> str:
    """Resolve exactly one target for commands that cannot sensibly fan out."""
    resolved_targets = _resolve_container_targets(selector)
    if len(resolved_targets) == 1:
        return resolved_targets[0]

    raise typer.BadParameter(
        f"{command_name} requires exactly one target, but {selector!r} matched "
        f"{', '.join(resolved_targets)}",
        param_hint="target",
    )


def _shell_text(container_name: str, shell_command: str) -> tuple[bool, str]:
    """Run one zsh login command in the container and return success plus stdout."""
    result = _run_command(
        ["docker", "exec", container_name, "zsh", "-ilc", shell_command]
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stderr or result.stdout).strip()


def _last_non_empty_line(output: str) -> str:
    """Return the last non-empty text line from command output."""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _emit_validation_result(
    *,
    stat: str,
    check: str,
    detail: str,
) -> None:
    """Print one validation result row."""
    console.print(f"{stat:<4} {check:<24} {detail}")


def _json_dump(payload: dict[str, object]) -> None:
    """Render one JSON payload with stable formatting."""
    console.print_json(json.dumps(payload, sort_keys=True))


def _docker_available() -> tuple[bool, str]:
    """Return whether Docker is callable plus a short status detail."""
    result = _run_command(["docker", "version", "--format", "{{.Server.Version}}"])
    if result.returncode == 0:
        return True, _last_non_empty_line(result.stdout) or "available"

    detail = (
        _last_non_empty_line(result.stderr or result.stdout) or "docker unavailable"
    )
    return False, detail


def _doctor_manifest_path() -> Path:
    """Return the default repo-local tool manifest path used by ft."""
    return _repo_root() / "ft" / "tools" / "tools.toml"


def _tool_pool_manifest_path() -> Path:
    """Return the default repo-local canonical tool-pool manifest path."""
    return default_tool_pool_manifest_path(_repo_root())


def _build_doctor_report(targets: list[str]) -> dict[str, object]:
    """Build a structured host-and-container health report for one or more targets."""
    overall_success = True
    host_checks: list[dict[str, str]] = []
    container_checks: list[dict[str, str]] = []

    repo_root = _repo_root()
    repo_present = repo_root.is_dir()
    host_checks.append(
        {
            "stat": "OK" if repo_present else "FAIL",
            "check": "repo_root",
            "detail": str(repo_root) if repo_present else f"missing {repo_root}",
        }
    )
    overall_success = overall_success and repo_present

    manifest_path = _doctor_manifest_path()
    manifest_present = manifest_path.is_file()
    host_checks.append(
        {
            "stat": "OK" if manifest_present else "FAIL",
            "check": "tool_manifest",
            "detail": str(manifest_path)
            if manifest_present
            else f"missing {manifest_path}",
        }
    )
    overall_success = overall_success and manifest_present

    docker_ok, docker_detail = _docker_available()
    host_checks.append(
        {
            "stat": "OK" if docker_ok else "FAIL",
            "check": "docker",
            "detail": docker_detail,
        }
    )
    overall_success = overall_success and docker_ok

    missing_images: list[str] = []
    missing_containers: list[str] = []

    for target in targets:
        container_name = _container_name_for_target(target)
        image_tag = _image_tag_for_target(target)
        image_present = (
            _run_command(["docker", "image", "inspect", image_tag]).returncode == 0
        )
        container_status = _container_status_value(target)

        if not image_present:
            missing_images.append(target)
        if container_status == "missing":
            missing_containers.append(target)

        container_checks.append(
            {
                "stat": "OK" if image_present else "WARN",
                "check": f"{target}_image",
                "detail": image_tag if image_present else f"missing {image_tag}",
            }
        )
        container_checks.append(
            {
                "stat": "OK" if container_status != "missing" else "WARN",
                "check": f"{target}_container",
                "detail": f"{container_name} ({container_status})",
            }
        )

    if not docker_ok:
        next_step = "install Docker or start the Docker daemon, then rerun `ft doctor`."
    elif missing_images:
        selector = missing_images[0] if len(missing_images) == 1 else "all"
        next_step = f"build missing targets with `ft container build {selector}` or one target at a time."
    elif missing_containers:
        selector = missing_containers[0] if len(missing_containers) == 1 else "all"
        next_step = f"start targets with `ft container up {selector}` or use `ft container enter <target>`."
    else:
        next_step = "use `ft container validate <target>` for a deeper shell and toolchain pass."

    return {
        "success": overall_success,
        "targets": targets,
        "host_checks": host_checks,
        "container_checks": container_checks,
        "next_step": next_step,
    }


def _render_doctor_report(report: dict[str, object]) -> None:
    """Render a doctor report in the standard human-readable format."""
    console.print("[bold]host checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["host_checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )

    console.print("[bold]container checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["container_checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )

    console.print(f"next: {report['next_step']}")


def _run_doctor(targets: list[str], *, json_output: bool = False) -> bool:
    """Render a small host-and-container health report for one or more targets."""
    report = _build_doctor_report(targets)
    if json_output:
        _json_dump(report)
    else:
        _render_doctor_report(report)
    return bool(report["success"])


def _validate_single_container_target(target: str) -> dict[str, object]:
    """Validate one disposable test container target and return structured results."""
    container_name = _container_name_for_target(target)
    checks: list[dict[str, str]] = []
    success = True

    def add_result(*, stat: str, check: str, detail: str) -> None:
        checks.append({"stat": stat, "check": check, "detail": detail})

    inspect_result = _run_command(["docker", "container", "inspect", container_name])
    if inspect_result.returncode != 0:
        add_result(
            stat="FAIL",
            check="container",
            detail=f"container not found: {container_name}",
        )
        return {
            "target": target,
            "container": container_name,
            "success": False,
            "checks": checks,
        }

    shell_checks = [
        ("runtime_user", "whoami", "vscode"),
        (
            "active_profile",
            'print -r -- "${SHELL_CONFIG_PROFILE:-}"',
            "zsh-tll-citadel-dev-fortress",
        ),
        ("path_local_bin", 'print -r -- "$PATH"', "/home/vscode/.local/bin"),
    ]

    for check_name, command, expected in shell_checks:
        ok, output = _shell_text(container_name, command)
        if not ok:
            add_result(stat="FAIL", check=check_name, detail=output)
            success = False
            continue
        if check_name == "path_local_bin":
            passed = f":{expected}:" in f":{output}:"
            detail = expected if passed else f"missing {expected}"
        else:
            normalized_output = _last_non_empty_line(output)
            passed = normalized_output == expected
            detail = (
                normalized_output
                if passed
                else f"expected {expected}, got {normalized_output or output}"
            )
        add_result(
            stat="OK" if passed else "FAIL",
            check=check_name,
            detail=detail,
        )
        success = success and passed

    for command_name in load_tool_pool_manifest(
        _tool_pool_manifest_path()
    ).containers.command_checks_for(target):
        ok, output = _shell_text(container_name, f"command -v -- '{command_name}'")
        normalized_output = _last_non_empty_line(output)
        add_result(
            stat="OK" if ok else "FAIL",
            check=command_name,
            detail=normalized_output or "command not found",
        )
        success = success and ok

    ok, hud_output = _shell_text(container_name, "fortress-hud")
    add_result(
        stat="OK" if ok else "FAIL",
        check="fortress_hud",
        detail="command succeeded" if ok else hud_output,
    )
    success = success and ok

    if ok:
        for expected_line in (
            "[settings] prompt_engine_resolved: starship",
            "[tools] starship: available",
            "[tools] atuin: available",
            "[tools] zoxide: available",
            "[tools] fzf: available",
        ):
            passed = expected_line in hud_output
            add_result(
                stat="OK" if passed else "FAIL",
                check="hud_expectation",
                detail=expected_line if passed else f"missing {expected_line}",
            )
            success = success and passed

    return {
        "target": target,
        "container": container_name,
        "success": success,
        "checks": checks,
    }


def _build_single_container_target(
    target: str,
    *,
    image_tag: str | None = None,
    extra_build_args: list[str] | None = None,
    shell_config_source: str,
    shell_config_repo_url: str,
    shell_config_branch: str,
    shell_config_local_dir: str | None,
    shell_config_stage_from: Path | None,
    no_cache: bool,
) -> bool:
    """Build one disposable container image target from the repo Dockerfile."""
    dockerfile_path = _dockerfile_for_target(target)
    resolved_image_tag = image_tag or _image_tag_for_target(target)

    if not dockerfile_path.is_file():
        console.print(f"[red]missing Dockerfile:[/red] {dockerfile_path}")
        return False

    build_command = [
        "docker",
        "buildx",
        "build",
        "--load",
    ]
    if no_cache:
        build_command.append("--no-cache")

    normalized_source = _require_supported_shell_config_source(shell_config_source)
    build_command.extend(
        [
            "--build-arg",
            f"SHELL_CONFIG_SOURCE={normalized_source}",
        ]
    )
    if normalized_source == "github":
        build_command.extend(
            [
                "--build-arg",
                f"SHELL_CONFIG_REPO_URL={shell_config_repo_url}",
                "--build-arg",
                f"SHELL_CONFIG_BRANCH={shell_config_branch}",
            ]
        )
    else:
        local_stage_dir = (
            _default_shell_config_stage_dir()
            if shell_config_local_dir is None
            else (_repo_root() / shell_config_local_dir).resolve()
        )
        if shell_config_stage_from is not None:
            staged_path = _stage_local_shell_config(
                shell_config_stage_from, local_stage_dir
            )
            console.print(f"[cyan]staged local shell-config:[/cyan] {staged_path}")
        local_dir_for_build = _relative_build_context_path(local_stage_dir)
        build_command.extend(
            [
                "--build-arg",
                f"SHELL_CONFIG_LOCAL_DIR={local_dir_for_build}",
            ]
        )
    if extra_build_args:
        for build_arg in extra_build_args:
            build_command.extend(["--build-arg", build_arg])

    build_command.extend(
        [
            "-f",
            str(dockerfile_path),
            "-t",
            resolved_image_tag,
            str(_repo_root()),
        ]
    )
    result = _run_streaming_command(build_command)
    return result.returncode == 0


def _build_workspace_profile(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_source: str,
    shell_config_repo_url: str,
    shell_config_branch: str,
    shell_config_local_dir: str | None,
    shell_config_stage_from: Path | None,
    no_cache: bool,
) -> bool:
    """Build one workspace image from the profile's underlying container target."""
    image_build_layers = _workspace_image_build_layers(profile)
    state_only_layers = _workspace_state_only_layers(profile)

    if state_only_layers:
        console.print(
            "workspace layer markers that do not currently change the image: "
            + ", ".join(layer_name for layer_name, _ in state_only_layers)
        )
    if image_build_layers:
        console.print(
            "workspace layers that change image build behavior: "
            + ", ".join(layer_name for layer_name, _ in image_build_layers)
        )
    extra_build_args = [
        f"{layer_definition.build_arg}=1"
        for _, layer_definition in image_build_layers
        if layer_definition.build_arg is not None
    ]

    return _build_single_container_target(
        profile.container_target,
        image_tag=_workspace_image_tag(profile_name),
        extra_build_args=extra_build_args or None,
        shell_config_source=shell_config_source,
        shell_config_repo_url=shell_config_repo_url,
        shell_config_branch=shell_config_branch,
        shell_config_local_dir=shell_config_local_dir,
        shell_config_stage_from=shell_config_stage_from,
        no_cache=no_cache,
    )


def _container_status_value(target: str) -> str:
    """Return the current Docker status value for one managed container target."""
    result = _run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Status}}",
            _container_name_for_target(target),
        ]
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "missing"


def _render_container_status(targets: list[str]) -> None:
    """Render a simple status table for one or more managed container targets."""
    table = Table(title="dev-container-fortress containers")
    table.add_column("target", style="cyan")
    table.add_column("container", style="white")
    table.add_column("image", style="white")
    table.add_column("status", style="white")

    for target in targets:
        table.add_row(
            target,
            _container_name_for_target(target),
            _image_tag_for_target(target),
            _container_status_value(target),
        )

    console.print(table)


def _container_exists(target: str) -> bool:
    """Return whether the managed container for one target currently exists."""
    result = _run_command(
        ["docker", "container", "inspect", _container_name_for_target(target)]
    )
    return result.returncode == 0


def _logs_single_container_target(target: str) -> int:
    """Follow logs for one managed disposable container target."""
    container_name = _container_name_for_target(target)
    if not _container_exists(target):
        console.print(f"[red]container not found:[/red] {container_name}")
        return 1

    result = _run_streaming_command(["docker", "logs", "--follow", container_name])
    return result.returncode


def _exec_single_container_target(target: str, command: list[str]) -> int:
    """Run one command inside one managed disposable container target."""
    container_name = _container_name_for_target(target)
    if not _container_exists(target):
        console.print(f"[red]container not found:[/red] {container_name}")
        return 1

    effective_command = (
        command
        if command
        else ["zsh", "-lc", "whoami && echo $HOME && printenv SHELL_CONFIG_PROFILE"]
    )
    result = _run_streaming_command(
        ["docker", "exec", "-it", container_name, *effective_command]
    )
    return result.returncode


def _shell_single_container_target(target: str) -> int:
    """Open one interactive zsh login shell in one managed disposable container target."""
    return _exec_single_container_target(target, ["zsh", "-il"])


def _refresh_single_container_target(
    target: str,
    *,
    shell_config_source: str,
    shell_config_repo_url: str,
    shell_config_branch: str,
    shell_config_local_dir: str | None,
    shell_config_stage_from: Path | None,
    no_cache: bool,
) -> bool:
    """Rebuild one target image and replace its managed disposable container."""
    if not _build_single_container_target(
        target,
        shell_config_source=shell_config_source,
        shell_config_repo_url=shell_config_repo_url,
        shell_config_branch=shell_config_branch,
        shell_config_local_dir=shell_config_local_dir,
        shell_config_stage_from=shell_config_stage_from,
        no_cache=no_cache,
    ):
        return False
    return _up_single_container_target(target)


def _enter_single_container_target(target: str) -> int:
    """Ensure one target is ready, then open an interactive shell inside it."""
    if not _up_single_container_target(target):
        return 1
    return _shell_single_container_target(target)


def _up_single_container_target(target: str) -> bool:
    """Start or replace one managed disposable container target."""
    image_tag = _image_tag_for_target(target)
    container_name = _container_name_for_target(target)

    image_result = _run_command(["docker", "image", "inspect", image_tag])
    if image_result.returncode != 0 and not _build_single_container_target(target):
        return False

    container_result = _run_command(["docker", "container", "inspect", container_name])
    if container_result.returncode == 0:
        console.print(f"replacing existing container {container_name}")
        remove_result = _run_command(["docker", "rm", "-f", container_name])
        if remove_result.returncode != 0:
            console.print(
                f"[red]failed to remove existing container:[/red] {container_name}"
            )
            return False

    run_command = [
        "docker",
        "run",
        "--detach",
        "--name",
        container_name,
        "--hostname",
        container_name,
    ]
    ssh_host_target_name = _container_host_ssh_target_name(target)
    ssh_host_port = _container_host_ssh_port(target)
    if ssh_host_target_name is not None and ssh_host_port is not None:
        public_key_path = _container_host_ssh_public_key_path(target)
        run_command.extend(["--publish", f"127.0.0.1:{ssh_host_port}:2222"])
        if public_key_path is not None and public_key_path.is_file():
            run_command.extend(
                [
                    "--volume",
                    f"{public_key_path}:/tmp/dev-fortress-authorized-key:ro",
                ]
            )
        else:
            console.print(
                "managed SSH public key not present for "
                f"{ssh_host_target_name}; run `ft host ssh-key {ssh_host_target_name}` "
                "before starting the disposable SSH target."
            )
        run_command.extend(
            [
                image_tag,
                "sudo",
                "/usr/local/bin/start-test-target",
                "sshd",
                "/tmp/dev-fortress-authorized-key",
            ]
        )
    else:
        run_command.extend([image_tag, "sleep", "infinity"])

    run_result = _run_command(run_command)
    if run_result.returncode == 0:
        console.print(f"started {container_name}")
        return True

    console.print(
        (
            run_result.stderr
            or run_result.stdout
            or f"failed to start {container_name}"
        ).strip()
    )
    return False


def _down_single_container_target(target: str) -> bool:
    """Stop and remove one managed disposable container target when present."""
    container_name = _container_name_for_target(target)
    inspect_result = _run_command(["docker", "container", "inspect", container_name])

    if inspect_result.returncode != 0:
        console.print(f"container already absent: {container_name}")
        return True

    remove_result = _run_command(["docker", "rm", "-f", container_name])
    if remove_result.returncode == 0:
        console.print(f"removed {container_name}")
        return True

    console.print(
        (
            remove_result.stderr
            or remove_result.stdout
            or f"failed to remove {container_name}"
        ).strip()
    )
    return False


def _reset_single_container_target(target: str) -> bool:
    """Remove one managed disposable container target and its tagged image."""
    image_tag = _image_tag_for_target(target)
    success = _down_single_container_target(target)

    image_result = _run_command(["docker", "image", "inspect", image_tag])
    if image_result.returncode != 0:
        console.print(f"image already absent: {image_tag}")
        return success

    remove_result = _run_command(["docker", "image", "rm", "-f", image_tag])
    if remove_result.returncode == 0:
        console.print(f"removed image {image_tag}")
        return success

    console.print(
        (
            remove_result.stderr
            or remove_result.stdout
            or f"failed to remove image {image_tag}"
        ).strip()
    )
    return False


def _build_workspace_doctor_report(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> dict[str, object]:
    """Build a structured health report for one workspace profile."""
    overall_success = True
    checks: list[dict[str, str]] = []

    def add_check(*, stat: str, check: str, detail: str) -> None:
        checks.append({"stat": stat, "check": check, "detail": detail})

    docker_ok, docker_detail = _docker_available()
    add_check(
        stat="OK" if docker_ok else "FAIL",
        check="docker",
        detail=docker_detail,
    )
    overall_success = overall_success and docker_ok

    image_tag = _workspace_image_tag(profile_name)
    image_present = _run_command(["docker", "image", "inspect", image_tag]).returncode == 0
    add_check(
        stat="OK" if image_present else "WARN",
        check="image",
        detail=image_tag if image_present else f"missing {image_tag}",
    )

    container_name = _workspace_container_name(profile_name)
    container_status = _workspace_status_value(profile_name)
    add_check(
        stat="OK" if container_status != "missing" else "WARN",
        check="container",
        detail=f"{container_name} ({container_status})",
    )

    dev_repo_path = _repo_root()
    add_check(
        stat="OK" if dev_repo_path.is_dir() else "FAIL",
        check="dev_repo_checkout",
        detail=str(dev_repo_path) if dev_repo_path.is_dir() else f"missing {dev_repo_path}",
    )
    overall_success = overall_success and dev_repo_path.is_dir()

    shell_config = _workspace_shell_config_resolution(shell_config_checkout)
    if not bool(shell_config["available"]):
        add_check(
            stat="WARN",
            check="shell_config_checkout",
            detail=str(shell_config["detail"]),
        )
    else:
        add_check(
            stat="OK",
            check="shell_config_checkout",
            detail=str(shell_config["resolved_path"]),
        )
        overall_success = overall_success and True

    if not docker_ok:
        next_step = (
            "install Docker or start the Docker daemon, then rerun "
            f"`ft workspace doctor {profile_name}`."
        )
    elif not image_present:
        next_step = f"build the workspace image with `ft workspace build {profile_name}`."
    elif container_status == "missing":
        next_step = f"start the workspace with `ft workspace up {profile_name}`."
    else:
        next_step = f"enter the workspace with `ft workspace enter {profile_name}`."

    return {
        "success": overall_success,
        "profile": profile_name,
        "target": profile.container_target,
        "checks": checks,
        "next_step": next_step,
    }


def _render_workspace_doctor_report(report: dict[str, object]) -> None:
    """Render one workspace doctor report in the standard human-readable format."""
    console.print("[bold]workspace checks[/bold]")
    console.print(f"{'stat':<4} {'check':<24} detail")
    for check in report["checks"]:
        _emit_validation_result(
            stat=str(check["stat"]),
            check=str(check["check"]),
            detail=str(check["detail"]),
        )
    console.print(f"next: {report['next_step']}")


def _run_workspace_doctor(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
    json_output: bool = False,
) -> bool:
    """Render a small health report for one workspace profile."""
    report = _build_workspace_doctor_report(
        profile_name,
        profile,
        shell_config_checkout=shell_config_checkout,
    )
    if json_output:
        _json_dump(report)
    else:
        _render_workspace_doctor_report(report)
    return bool(report["success"])


def _up_workspace_profile(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> bool:
    """Start or replace one managed workspace container profile."""
    image_tag = _workspace_image_tag(profile_name)
    container_name = _workspace_container_name(profile_name)

    image_result = _run_command(["docker", "image", "inspect", image_tag])
    if image_result.returncode != 0 and not _build_workspace_profile(
        profile_name,
        profile,
        shell_config_source="github",
        shell_config_repo_url="https://github.com/GrndZero101/shell-config.git",
        shell_config_branch="main",
        shell_config_local_dir=None,
        shell_config_stage_from=None,
        no_cache=False,
    ):
        return False

    container_result = _run_command(["docker", "container", "inspect", container_name])
    if container_result.returncode == 0:
        console.print(f"replacing existing workspace {container_name}")
        remove_result = _run_command(["docker", "rm", "-f", container_name])
        if remove_result.returncode != 0:
            console.print(
                f"[red]failed to remove existing workspace:[/red] {container_name}"
            )
            return False

    mount_plan = _workspace_mount_plan(
        profile_name,
        profile,
        shell_config_checkout=shell_config_checkout,
    )
    browser_bridge_socket = _ensure_workspace_host_browser_bridge(profile_name)
    for host_path, _ in mount_plan:
        host_path.mkdir(parents=True, exist_ok=True)

    run_command = [
        "docker",
        "run",
        "--detach",
        "--init",
        "--name",
        container_name,
        "--hostname",
        container_name,
        "--workdir",
        profile.working_directory,
    ]

    ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
    if ssh_auth_sock:
        ssh_auth_sock_path = Path(ssh_auth_sock)
        if ssh_auth_sock_path.exists():
            run_command.extend(
                [
                    "--volume",
                    f"{ssh_auth_sock_path}:{ssh_auth_sock_path}",
                    "--env",
                    f"SSH_AUTH_SOCK={ssh_auth_sock_path}",
                ]
            )

    if browser_bridge_socket is not None:
        host_bridge_dir = browser_bridge_socket.parent
        run_command.extend(
            [
                "--volume",
                (
                    f"{host_bridge_dir}:"
                    f"{_workspace_container_host_browser_bridge_dir()}"
                ),
                "--env",
                (
                    "DEV_FORTRESS_HOST_BROWSER_SOCKET="
                    f"{_workspace_container_host_browser_socket()}"
                ),
            ]
        )

    if _host_runs_under_wsl():
        windows_system_path = _workspace_wsl_windows_system_path()
        if windows_system_path.is_dir():
            run_command.extend(
                [
                    "--volume",
                    f"{windows_system_path}:{windows_system_path}:ro",
                ]
            )
            wsl_init_path = _workspace_wsl_init_path()
            if wsl_init_path.is_file():
                run_command.extend(
                    [
                        "--volume",
                        f"{wsl_init_path}:{wsl_init_path}:ro",
                    ]
                )
            wsl_interop_root = _workspace_wsl_interop_root()
            if wsl_interop_root.is_dir():
                run_command.extend(
                    [
                        "--volume",
                        f"{wsl_interop_root}:{wsl_interop_root}",
                    ]
                )
            for env_name in ("WSL_DISTRO_NAME", "WSL_INTEROP"):
                env_value = os.environ.get(env_name)
                if env_value:
                    run_command.extend(["--env", f"{env_name}={env_value}"])
            if browser_bridge_socket is not None or not os.environ.get("BROWSER"):
                run_command.extend(
                    [
                        "--env",
                        f"BROWSER={_workspace_host_browser_open_command()}",
                    ]
                )
            if browser_bridge_socket is not None or not os.environ.get("GH_BROWSER"):
                run_command.extend(
                    [
                        "--env",
                        f"GH_BROWSER={_workspace_host_browser_open_command()}",
                    ]
                )

    if browser_bridge_socket is not None:
        if not _host_runs_under_wsl() and not os.environ.get("BROWSER"):
            run_command.extend(
                [
                    "--env",
                    f"BROWSER={_workspace_host_browser_open_command()}",
                ]
            )
        if not _host_runs_under_wsl() and not os.environ.get("GH_BROWSER"):
            run_command.extend(
                [
                    "--env",
                    f"GH_BROWSER={_workspace_host_browser_open_command()}",
                ]
            )

    for env_name in ("BROWSER", "GH_BROWSER"):
        env_value = os.environ.get(env_name)
        if env_value:
            run_command.extend(["--env", f"{env_name}={env_value}"])

    for host_path, container_path in mount_plan:
        run_command.extend(
            [
                "--volume",
                f"{host_path}:{container_path}",
            ]
        )

    run_command.extend([image_tag, "sleep", "infinity"])
    run_result = _run_command(run_command)
    if run_result.returncode == 0:
        console.print(f"started {container_name}")
        return True

    console.print(
        (
            run_result.stderr
            or run_result.stdout
            or f"failed to start {container_name}"
        ).strip()
    )
    return False


def _down_workspace_profile(profile_name: str) -> bool:
    """Stop and remove one managed workspace container profile when present."""
    container_name = _workspace_container_name(profile_name)
    inspect_result = _run_command(["docker", "container", "inspect", container_name])
    if inspect_result.returncode != 0:
        console.print(f"workspace already absent: {container_name}")
        return True

    remove_result = _run_command(["docker", "rm", "-f", container_name])
    if remove_result.returncode == 0:
        console.print(f"removed {container_name}")
        return True

    console.print(
        (
            remove_result.stderr
            or remove_result.stdout
            or f"failed to remove {container_name}"
        ).strip()
    )
    return False


def _reset_workspace_profile(profile_name: str) -> bool:
    """Remove one managed workspace container profile and its tagged image."""
    image_tag = _workspace_image_tag(profile_name)
    success = _down_workspace_profile(profile_name)

    image_result = _run_command(["docker", "image", "inspect", image_tag])
    if image_result.returncode != 0:
        console.print(f"image already absent: {image_tag}")
        return success

    remove_result = _run_command(["docker", "image", "rm", "-f", image_tag])
    if remove_result.returncode == 0:
        console.print(f"removed image {image_tag}")
        return success

    console.print(
        (
            remove_result.stderr
            or remove_result.stdout
            or f"failed to remove image {image_tag}"
        ).strip()
    )
    return False


def _exec_workspace_profile(profile_name: str, command: list[str]) -> int:
    """Run one command inside one managed workspace container profile."""
    container_name = _workspace_container_name(profile_name)
    if not _workspace_exists(profile_name):
        console.print(f"[red]workspace not found:[/red] {container_name}")
        return 1

    effective_command = (
        command
        if command
        else ["zsh", "-lc", "whoami && pwd && printenv SHELL_CONFIG_PROFILE"]
    )
    result = _run_streaming_command(
        ["docker", "exec", "-it", container_name, *effective_command]
    )
    return result.returncode


def _shell_workspace_profile(profile_name: str) -> int:
    """Open one interactive zsh login shell in one managed workspace container profile."""
    return _exec_workspace_profile(profile_name, ["zsh", "-il"])


def _enter_workspace_profile(
    profile_name: str,
    profile: WorkspaceProfileDefinition,
    *,
    shell_config_checkout: Path | None = None,
) -> int:
    """Ensure one workspace is ready, then open an interactive shell inside it."""
    if not _up_workspace_profile(
        profile_name,
        profile,
        shell_config_checkout=shell_config_checkout,
    ):
        return 1
    return _shell_workspace_profile(profile_name)


@tool_app.command("plan")
def tool_plan(
    tool: Annotated[str | None, typer.Option(help="Plan only the named tool.")] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
    resolve_latest: Annotated[
        bool,
        typer.Option(
            "--resolve-latest/--use-manifest-version",
            help="Resolve current upstream GitHub releases for tools configured to do so.",
        ),
    ] = True,
) -> None:
    """Print the resolved install plan for one tool or the full enabled set."""
    runtime = _resolve_runtime_options(
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        healthcheck=None,
    )
    manifest_model = load_manifest(Path(runtime["manifest"]))

    for name, tool_definition in _selected_tools(
        manifest_model, tool, target=str(runtime["target"])
    ):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
            resolve_latest=resolve_latest,
        )
        _render_plan(
            plan_model,
            target=str(runtime["target"]),
            install_root=runtime["install_root"],
        )


@tool_app.command("install")
def tool_install(
    tool: Annotated[
        str | None, typer.Option(help="Install only the named tool.")
    ] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
    healthcheck: Annotated[
        bool | None,
        typer.Option(
            "--healthcheck/--no-healthcheck",
            help="Run the configured healthcheck after installation.",
        ),
    ] = None,
    resolve_latest: Annotated[
        bool,
        typer.Option(
            "--resolve-latest/--use-manifest-version",
            help="Resolve current upstream GitHub releases for tools configured to do so.",
        ),
    ] = True,
) -> None:
    """Install one tool or the full enabled tool set from the shared manifest."""
    runtime = _resolve_runtime_options(
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        healthcheck=healthcheck,
    )
    manifest_model = load_manifest(Path(runtime["manifest"]))

    for name, tool_definition in _selected_tools(
        manifest_model, tool, target=str(runtime["target"])
    ):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
            resolve_latest=resolve_latest,
        )
        effective_install_root = _effective_install_root(
            tool_definition.install_root,
            runtime["install_root"],
        )
        if (
            runtime["install_root"] is None
            and effective_install_root != tool_definition.install_root
        ):
            console.print(
                f"Using fallback install root {effective_install_root} because "
                f"{tool_definition.install_root} is not writable."
            )
        installed_path = install_tool(
            plan_model,
            install_root=effective_install_root,
            healthcheck=bool(runtime["healthcheck"]),
        )
        console.print(f"Installed {name} to {installed_path}")


@container_app.command("validate")
def container_validate(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Target selector for disposable test containers. Supports exact "
                "names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for agentic or automated validation consumers.",
        ),
    ] = False,
) -> None:
    """Validate shell, prompt, PATH, and core toolchain state for one or more targets."""
    resolved_targets = _resolve_container_targets(target)
    reports: list[dict[str, object]] = []
    overall_success = True

    for resolved_target in resolved_targets:
        report = _validate_single_container_target(resolved_target)
        reports.append(report)
        if not json_output:
            console.print(f"[bold]validating {resolved_target}[/bold]")
            console.print(f"{'stat':<4} {'check':<24} detail")
            for check in report["checks"]:
                _emit_validation_result(
                    stat=str(check["stat"]),
                    check=str(check["check"]),
                    detail=str(check["detail"]),
                )
        overall_success = overall_success and bool(report["success"])

    if json_output:
        _json_dump(
            {
                "success": overall_success,
                "targets": resolved_targets,
                "reports": reports,
            }
        )

    if not overall_success:
        raise typer.Exit(code=1)


@container_app.command("build")
def container_build(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Target selector for disposable container image builds. Supports "
                "exact names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ],
    shell_config_source: Annotated[
        str,
        typer.Option(
            "--shell-config-source",
            help=(
                "Choose whether the image installs shell-config from GitHub or "
                "from a staged repo-local checkout."
            ),
        ),
    ] = "github",
    shell_config_repo_url: Annotated[
        str,
        typer.Option(
            "--shell-config-repo-url",
            help="GitHub repository URL to clone when using --shell-config-source github.",
        ),
    ] = "https://github.com/GrndZero101/shell-config.git",
    shell_config_branch: Annotated[
        str,
        typer.Option(
            "--shell-config-branch",
            help="Git branch to clone when using --shell-config-source github.",
        ),
    ] = "main",
    shell_config_local_dir: Annotated[
        str | None,
        typer.Option(
            "--shell-config-local-dir",
            help=(
                "Repo-relative staged shell-config path inside the Docker build "
                "context when using --shell-config-source local."
            ),
        ),
    ] = None,
    shell_config_stage_from: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-stage-from",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Absolute host checkout to stage into the repo build context "
                "before a local shell-config build."
            ),
        ),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help=(
                "Disable Docker build cache for this build. Useful when a "
                "moving Git branch appears stale under buildx."
            ),
        ),
    ] = False,
) -> None:
    """Build one or more disposable container images for local testing."""
    resolved_targets = _resolve_container_targets(target)
    overall_success = True

    for resolved_target in resolved_targets:
        console.print(f"[bold]building {resolved_target}[/bold]")
        target_success = _build_single_container_target(
            resolved_target,
            shell_config_source=shell_config_source,
            shell_config_repo_url=shell_config_repo_url,
            shell_config_branch=shell_config_branch,
            shell_config_local_dir=shell_config_local_dir,
            shell_config_stage_from=shell_config_stage_from,
            no_cache=no_cache,
        )
        overall_success = overall_success and target_success

    if not overall_success:
        raise typer.Exit(code=1)


@container_app.command("status")
def container_status(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional target selector for managed disposable containers. "
                "Supports exact names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ] = None,
) -> None:
    """Show Docker status for one or more managed disposable container targets."""
    resolved_targets = (
        list(KNOWN_CONTAINER_TARGETS)
        if target is None
        else _resolve_container_targets(target)
    )
    _render_container_status(resolved_targets)


@container_app.command("up")
def container_up(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Target selector for disposable containers to start. Supports "
                "exact names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ],
) -> None:
    """Start or replace one or more disposable container targets."""
    resolved_targets = _resolve_container_targets(target)
    overall_success = True

    for resolved_target in resolved_targets:
        console.print(f"[bold]starting {resolved_target}[/bold]")
        target_success = _up_single_container_target(resolved_target)
        overall_success = overall_success and target_success

    if not overall_success:
        raise typer.Exit(code=1)


@container_app.command("down")
def container_down(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Target selector for disposable containers to remove. Supports "
                "exact names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ],
) -> None:
    """Stop and remove one or more disposable container targets."""
    resolved_targets = _resolve_container_targets(target)
    overall_success = True

    for resolved_target in resolved_targets:
        console.print(f"[bold]removing {resolved_target}[/bold]")
        target_success = _down_single_container_target(resolved_target)
        overall_success = overall_success and target_success

    if not overall_success:
        raise typer.Exit(code=1)


@container_app.command("reset")
def container_reset(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Target selector for disposable containers and images to remove. "
                "Supports exact names, shell-style wildcards, and the alias 'all'."
            )
        ),
    ],
) -> None:
    """Remove one or more disposable container targets and their tagged images."""
    resolved_targets = _resolve_container_targets(target)
    overall_success = True

    for resolved_target in resolved_targets:
        console.print(f"[bold]resetting {resolved_target}[/bold]")
        target_success = _reset_single_container_target(resolved_target)
        overall_success = overall_success and target_success

    if not overall_success:
        raise typer.Exit(code=1)


@container_app.command("logs")
def container_logs(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One target name or selector that must resolve to exactly one "
                "managed disposable container."
            )
        ),
    ],
) -> None:
    """Follow logs for one managed disposable container target."""
    resolved_target = _resolve_single_container_target(target, command_name="logs")
    raise typer.Exit(code=_logs_single_container_target(resolved_target))


@container_app.command("exec")
def container_exec(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One target name or selector that must resolve to exactly one "
                "managed disposable container."
            )
        ),
    ],
    command: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Optional command to run inside the container. When omitted, a small "
                "identity command runs. Use `--` before the inner command if it has its "
                "own flags, for example: `ft container exec ubuntu -- zsh -lc 'echo $TERM'`."
            ),
        ),
    ] = None,
) -> None:
    """Run one command inside one managed disposable container target."""
    resolved_target = _resolve_single_container_target(target, command_name="exec")
    raise typer.Exit(
        code=_exec_single_container_target(resolved_target, list(command or []))
    )


@container_app.command("shell")
def container_shell(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One target name or selector that must resolve to exactly one "
                "managed disposable container."
            )
        ),
    ],
) -> None:
    """Open one interactive zsh login shell in one managed disposable container target."""
    resolved_target = _resolve_single_container_target(target, command_name="shell")
    raise typer.Exit(code=_shell_single_container_target(resolved_target))


@container_app.command("refresh")
def container_refresh(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One target name or selector that must resolve to exactly one "
                "managed disposable container."
            )
        ),
    ],
    shell_config_source: Annotated[
        str,
        typer.Option(
            "--shell-config-source",
            help=(
                "Choose whether the image installs shell-config from GitHub or "
                "from a staged repo-local checkout."
            ),
        ),
    ] = "github",
    shell_config_repo_url: Annotated[
        str,
        typer.Option(
            "--shell-config-repo-url",
            help="GitHub repository URL to clone when using --shell-config-source github.",
        ),
    ] = "https://github.com/GrndZero101/shell-config.git",
    shell_config_branch: Annotated[
        str,
        typer.Option(
            "--shell-config-branch",
            help="Git branch to clone when using --shell-config-source github.",
        ),
    ] = "main",
    shell_config_local_dir: Annotated[
        str | None,
        typer.Option(
            "--shell-config-local-dir",
            help=(
                "Repo-relative staged shell-config path inside the Docker build "
                "context when using --shell-config-source local."
            ),
        ),
    ] = None,
    shell_config_stage_from: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-stage-from",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Absolute host checkout to stage into the repo build context "
                "before a local shell-config build."
            ),
        ),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help=(
                "Disable Docker build cache for this refresh. Useful when a "
                "moving Git branch appears stale under buildx."
            ),
        ),
    ] = False,
) -> None:
    """Rebuild one target image and replace its managed disposable container."""
    resolved_target = _resolve_single_container_target(target, command_name="refresh")
    if not _refresh_single_container_target(
        resolved_target,
        shell_config_source=shell_config_source,
        shell_config_repo_url=shell_config_repo_url,
        shell_config_branch=shell_config_branch,
        shell_config_local_dir=shell_config_local_dir,
        shell_config_stage_from=shell_config_stage_from,
        no_cache=no_cache,
    ):
        raise typer.Exit(code=1)


@container_app.command("enter")
def container_enter(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One target name or selector that must resolve to exactly one "
                "managed disposable container."
            )
        ),
    ],
) -> None:
    """Ensure one target is ready, then open an interactive shell inside it."""
    resolved_target = _resolve_single_container_target(target, command_name="enter")
    raise typer.Exit(code=_enter_single_container_target(resolved_target))


@workspace_app.command("build")
def workspace_build(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_source: Annotated[
        str,
        typer.Option(
            "--shell-config-source",
            help=(
                "Choose whether the image installs shell-config from GitHub or "
                "from a staged repo-local checkout."
            ),
        ),
    ] = "github",
    shell_config_repo_url: Annotated[
        str,
        typer.Option(
            "--shell-config-repo-url",
            help="GitHub repository URL to clone when using --shell-config-source github.",
        ),
    ] = "https://github.com/GrndZero101/shell-config.git",
    shell_config_branch: Annotated[
        str,
        typer.Option(
            "--shell-config-branch",
            help="Git branch to clone when using --shell-config-source github.",
        ),
    ] = "main",
    shell_config_local_dir: Annotated[
        str | None,
        typer.Option(
            "--shell-config-local-dir",
            help=(
                "Repo-relative staged shell-config path inside the Docker build "
                "context when using --shell-config-source local."
            ),
        ),
    ] = None,
    shell_config_stage_from: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-stage-from",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Absolute host checkout to stage into the repo build context "
                "before a local shell-config build."
            ),
        ),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable Docker build cache for this workspace image build.",
        ),
    ] = False,
) -> None:
    """Build one workspace image from its underlying Ubuntu-first container target."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    if not _build_workspace_profile(
        resolved_profile_name,
        resolved_profile,
        shell_config_source=shell_config_source,
        shell_config_repo_url=shell_config_repo_url,
        shell_config_branch=shell_config_branch,
        shell_config_local_dir=shell_config_local_dir,
        shell_config_stage_from=shell_config_stage_from,
        no_cache=no_cache,
    ):
        raise typer.Exit(code=1)


@workspace_app.command("status")
def workspace_status(
    profile: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional named workspace profile. Defaults to all repo-owned "
                "workspace profiles."
            )
        ),
    ] = None,
) -> None:
    """Show Docker status for one or more managed workspace profiles."""
    resolved_profiles = (
        _workspace_profile_names()
        if profile is None
        else [_resolve_workspace_profile(profile)[0]]
    )
    _render_workspace_status(resolved_profiles)


@workspace_app.command("up")
def workspace_up(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_checkout: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-checkout",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Optional live shell-config checkout to bind-mount into the "
                "workspace. Defaults to a sibling ../shell-config checkout when present."
            ),
        ),
    ] = None,
) -> None:
    """Start or replace one managed workspace container profile."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    if not _up_workspace_profile(
        resolved_profile_name,
        resolved_profile,
        shell_config_checkout=shell_config_checkout,
    ):
        raise typer.Exit(code=1)


@workspace_app.command("down")
def workspace_down(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
) -> None:
    """Stop and remove one managed workspace container profile."""
    resolved_profile_name, _ = _resolve_workspace_profile(profile)
    if not _down_workspace_profile(resolved_profile_name):
        raise typer.Exit(code=1)


@workspace_app.command("reset")
def workspace_reset(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
) -> None:
    """Remove one managed workspace container profile and its tagged image."""
    resolved_profile_name, _ = _resolve_workspace_profile(profile)
    if not _reset_workspace_profile(resolved_profile_name):
        raise typer.Exit(code=1)


@workspace_app.command("exec")
def workspace_exec(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    command: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Optional command to run inside the workspace. Use `--` before "
                "the inner command when it has its own flags."
            ),
        ),
    ] = None,
) -> None:
    """Run one command inside one managed workspace container profile."""
    resolved_profile_name, _ = _resolve_workspace_profile(profile)
    raise typer.Exit(
        code=_exec_workspace_profile(resolved_profile_name, list(command or []))
    )


@workspace_app.command("enter")
def workspace_enter(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_checkout: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-checkout",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Optional live shell-config checkout to bind-mount into the "
                "workspace. Defaults to a sibling ../shell-config checkout when present."
            ),
        ),
    ] = None,
) -> None:
    """Ensure one workspace is ready, then open an interactive shell inside it."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    raise typer.Exit(
        code=_enter_workspace_profile(
            resolved_profile_name,
            resolved_profile,
            shell_config_checkout=shell_config_checkout,
        )
    )


@workspace_app.command("doctor")
def workspace_doctor(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_checkout: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-checkout",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Optional live shell-config checkout to verify for bind-mount "
                "readiness. Defaults to a sibling ../shell-config checkout when present."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Render a small health report for one mounted daily-driver workspace profile."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    if not _run_workspace_doctor(
        resolved_profile_name,
        resolved_profile,
        shell_config_checkout=shell_config_checkout,
        json_output=json_output,
    ):
        raise typer.Exit(code=1)


@workspace_app.command("validate")
def workspace_validate(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_checkout: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-checkout",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Optional live shell-config checkout to validate for bind-mount "
                "presence. Defaults to a sibling ../shell-config checkout when present."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Validate shell, mounts, and layer-specific commands inside one workspace."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    report = _validate_workspace_profile(
        resolved_profile_name,
        resolved_profile,
        shell_config_checkout=shell_config_checkout,
    )
    if json_output:
        _json_dump(report)
    else:
        console.print(f"[bold]validating {resolved_profile_name}[/bold]")
        console.print(f"{'stat':<4} {'check':<24} detail")
        for check in report["checks"]:
            _emit_validation_result(
                stat=str(check["stat"]),
                check=str(check["check"]),
                detail=str(check["detail"]),
            )
    if not bool(report["success"]):
        raise typer.Exit(code=1)


@workspace_app.command("mount-plan")
def workspace_mount_plan(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    shell_config_checkout: Annotated[
        Path | None,
        typer.Option(
            "--shell-config-checkout",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Optional live shell-config checkout to include in the mount "
                "plan. Defaults to a sibling ../shell-config checkout when present."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Render the resolved host-to-container mount plan for one workspace profile."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    payload = _workspace_mount_plan_payload(
        resolved_profile_name,
        resolved_profile,
        shell_config_checkout=shell_config_checkout,
    )
    if json_output:
        _json_dump(payload)
        return

    table = Table(title=f"{resolved_profile_name} workspace mount plan")
    table.add_column("host", style="cyan")
    table.add_column("container", style="white")
    for mount in payload["mounts"]:
        table.add_row(str(mount["host_path"]), str(mount["container_path"]))
    console.print(table)


@workspace_auth_app.command("doctor")
def workspace_auth_doctor(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Inspect auth and persisted-state handoff points for one workspace profile."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    if not _run_workspace_auth_doctor(
        resolved_profile_name,
        resolved_profile,
        json_output=json_output,
    ):
        raise typer.Exit(code=1)


@workspace_auth_app.command("validate")
def workspace_auth_validate(
    profile: Annotated[
        str,
        typer.Argument(
            help="One named workspace profile from the repo-owned workspace manifest."
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Validate runtime browser-auth helpers and selected auth-oriented CLIs."""
    resolved_profile_name, resolved_profile = _resolve_workspace_profile(profile)
    report = _validate_workspace_auth_runtime(
        resolved_profile_name,
        resolved_profile,
    )
    if json_output:
        _json_dump(report)
    else:
        console.print(f"[bold]validating auth for {resolved_profile_name}[/bold]")
        console.print(f"{'stat':<4} {'check':<24} detail")
        for check in report["checks"]:
            _emit_validation_result(
                stat=str(check["stat"]),
                check=str(check["check"]),
                detail=str(check["detail"]),
            )
    if not bool(report["success"]):
        raise typer.Exit(code=1)


@host_app.command("list")
def host_list(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional host target selector. Supports exact names, shell-style "
                "wildcards, and the alias 'all'. Defaults to all configured targets."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help=(
                "Path to the host target TOML config. Defaults to FT_HOST_CONFIG "
                "or the XDG-managed hosts.toml path."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """List the configured Dev Fortress host targets."""
    resolved_path, manifest = _load_host_target_manifest(config)
    resolved_targets = (
        manifest.targets if target is None else _resolve_host_targets(target, manifest)
    )
    if json_output:
        _json_dump(
            {
                "config": str(resolved_path),
                "targets": [_host_target_record(item) for item in resolved_targets],
            }
        )
        return
    console.print(f"host config: {resolved_path}")
    _render_host_target_list(resolved_targets)


@host_app.command("show")
def host_show(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One host target name or selector that must resolve to exactly "
                "one configured host target."
            )
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
) -> None:
    """Show one configured host target in detail."""
    resolved_path, manifest = _load_host_target_manifest(config)
    resolved_target = _resolve_single_host_target(target, manifest, command_name="show")
    payload = {
        "config": str(resolved_path),
        "target": _host_target_record(resolved_target),
    }
    if json_output:
        _json_dump(payload)
        return
    console.print(f"host config: {resolved_path}")
    _render_host_target_details(resolved_target)


@host_app.command("inventory")
def host_inventory(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional host target selector for the generated inventory. Supports "
                "exact names, shell-style wildcards, and the alias 'all'. Defaults "
                "to all configured targets."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render the generated inventory as structured JSON instead of YAML.",
        ),
    ] = False,
) -> None:
    """Render a minimal Ansible inventory from the configured host targets."""
    _, manifest = _load_host_target_manifest(config)
    resolved_targets = (
        manifest.targets if target is None else _resolve_host_targets(target, manifest)
    )
    inventory = _build_host_inventory(resolved_targets)
    if json_output:
        _json_dump(inventory)
        return
    typer.echo(_yaml_dump(inventory), nl=False)


@host_app.command("import-terraform")
def host_import_terraform(
    terraform_dir: Annotated[
        Path,
        typer.Option(
            "--terraform-dir",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help=(
                "Terraform working directory to read with `terraform output -json`. "
                "Defaults to the disposable Ubuntu stack under infra/."
            ),
        ),
    ] = _default_disposable_ubuntu_terraform_dir(),
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help=(
                "Optional host target config path. Defaults to FT_HOST_CONFIG "
                "or the XDG-managed hosts.toml path."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render the import result as structured JSON instead of a table.",
        ),
    ] = False,
) -> None:
    """Import Terraform-emitted host targets into the configured hosts.toml."""
    payload = _import_terraform_host_targets(terraform_dir, config)
    if json_output:
        _json_dump(payload)
        return

    table = Table(title="Terraform host import", show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    table.add_row("config", str(payload["config"]))
    table.add_row("terraform_dir", str(terraform_dir))
    table.add_row(
        "imported_targets",
        ", ".join(str(name) for name in payload["imported_targets"]),
    )
    table.add_row("total_targets", str(payload["total_targets"]))
    console.print(table)


@aws_disposable_ubuntu_app.command("plan")
def infra_aws_disposable_ubuntu_plan(
    terraform_dir: Annotated[
        Path,
        typer.Option(
            "--terraform-dir",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Terraform working directory for the disposable Ubuntu stack.",
        ),
    ] = _default_disposable_ubuntu_terraform_dir(),
    seed_config: Annotated[
        Path,
        typer.Option(
            "--seed-config",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Seed host manifest used to derive the managed SSH key.",
        ),
    ] = _default_disposable_ubuntu_seed_config_path(),
    target_name: Annotated[
        str,
        typer.Option(
            "--target-name",
            help="Managed SSH key and Terraform host target name to use.",
        ),
    ] = "dev-fortress-ec2-dev",
) -> None:
    """Run terraform init, validate, and plan for the disposable Ubuntu stack."""
    for terraform_args in (["init"], ["validate"], ["plan"]):
        exit_code = _run_disposable_ubuntu_terraform(
            terraform_args,
            terraform_dir=terraform_dir,
            target_name=target_name,
            seed_config_path=seed_config,
        )
        if exit_code != 0:
            raise typer.Exit(code=exit_code)


@aws_disposable_ubuntu_app.command("apply")
def infra_aws_disposable_ubuntu_apply(
    terraform_dir: Annotated[
        Path,
        typer.Option(
            "--terraform-dir",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Terraform working directory for the disposable Ubuntu stack.",
        ),
    ] = _default_disposable_ubuntu_terraform_dir(),
    seed_config: Annotated[
        Path,
        typer.Option(
            "--seed-config",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Seed host manifest used to derive the managed SSH key.",
        ),
    ] = _default_disposable_ubuntu_seed_config_path(),
    target_name: Annotated[
        str,
        typer.Option(
            "--target-name",
            help="Managed SSH key and Terraform host target name to use.",
        ),
    ] = "dev-fortress-ec2-dev",
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help=(
                "Optional host target config path. Defaults to FT_HOST_CONFIG "
                "or the XDG-managed hosts.toml path."
            ),
        ),
    ] = None,
    auto_import: Annotated[
        bool,
        typer.Option(
            "--auto-import/--no-auto-import",
            help="Import the Terraform host target into hosts.toml after apply.",
        ),
    ] = True,
    auto_approve: Annotated[
        bool,
        typer.Option(
            "--auto-approve",
            help="Pass -auto-approve to terraform apply.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render the import result as structured JSON when auto-importing.",
        ),
    ] = False,
) -> None:
    """Run terraform init, validate, and apply for the disposable Ubuntu stack."""
    for terraform_args in (["init"], ["validate"]):
        exit_code = _run_disposable_ubuntu_terraform(
            terraform_args,
            terraform_dir=terraform_dir,
            target_name=target_name,
            seed_config_path=seed_config,
        )
        if exit_code != 0:
            raise typer.Exit(code=exit_code)

    apply_args = ["apply"]
    if auto_approve:
        apply_args.append("-auto-approve")
    exit_code = _run_disposable_ubuntu_terraform(
        apply_args,
        terraform_dir=terraform_dir,
        target_name=target_name,
        seed_config_path=seed_config,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)
    if not auto_import:
        return

    payload = _import_terraform_host_targets(terraform_dir, config)
    if json_output:
        _json_dump(payload)
        return

    table = Table(title="Disposable Ubuntu apply", show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    table.add_row("config", str(payload["config"]))
    table.add_row("terraform_dir", str(payload["terraform_dir"]))
    table.add_row("target_name", target_name)
    table.add_row(
        "imported_targets",
        ", ".join(str(name) for name in payload["imported_targets"]),
    )
    table.add_row("total_targets", str(payload["total_targets"]))
    console.print(table)


@aws_disposable_ubuntu_app.command("destroy")
def infra_aws_disposable_ubuntu_destroy(
    terraform_dir: Annotated[
        Path,
        typer.Option(
            "--terraform-dir",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Terraform working directory for the disposable Ubuntu stack.",
        ),
    ] = _default_disposable_ubuntu_terraform_dir(),
    seed_config: Annotated[
        Path,
        typer.Option(
            "--seed-config",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Seed host manifest used to derive the managed SSH key.",
        ),
    ] = _default_disposable_ubuntu_seed_config_path(),
    target_name: Annotated[
        str,
        typer.Option(
            "--target-name",
            help="Managed SSH key and Terraform host target name to use.",
        ),
    ] = "dev-fortress-ec2-dev",
    auto_approve: Annotated[
        bool,
        typer.Option(
            "--auto-approve",
            help="Pass -auto-approve to terraform destroy.",
        ),
    ] = False,
) -> None:
    """Run terraform init and destroy for the disposable Ubuntu stack."""
    exit_code = _run_disposable_ubuntu_terraform(
        ["init"],
        terraform_dir=terraform_dir,
        target_name=target_name,
        seed_config_path=seed_config,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)

    destroy_args = ["destroy"]
    if auto_approve:
        destroy_args.append("-auto-approve")
    exit_code = _run_disposable_ubuntu_terraform(
        destroy_args,
        terraform_dir=terraform_dir,
        target_name=target_name,
        seed_config_path=seed_config,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@host_app.command("ssh-key-path")
def host_ssh_key_path(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One host target name or selector that must resolve to exactly one "
                "configured host target."
            )
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    public: Annotated[
        bool,
        typer.Option(
            "--public",
            help="Print the public key path instead of the private key path.",
        ),
    ] = False,
) -> None:
    """Print the expected Dev Fortress-managed SSH key path for one host target."""
    _, manifest = _load_host_target_manifest(config)
    resolved_target = _resolve_single_host_target(
        target, manifest, command_name="ssh-key-path"
    )
    output_path = (
        _host_ssh_public_key_path(resolved_target)
        if public
        else _host_ssh_private_key_path(resolved_target)
    )
    if output_path is None:
        raise typer.BadParameter(
            f"target {resolved_target.name!r} does not use a managed ssh key",
            param_hint="target",
        )
    typer.echo(str(output_path))


@host_app.command("ssh-key")
def host_ssh_key(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One host target name or selector that must resolve to exactly one "
                "configured host target."
            )
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
) -> None:
    """Ensure the expected managed SSH key exists for one SSH host target."""
    _, manifest = _load_host_target_manifest(config)
    resolved_target = _resolve_single_host_target(
        target, manifest, command_name="ssh-key"
    )
    created, key_path = _ensure_managed_host_ssh_key(resolved_target)
    if created:
        console.print(f"generated ssh key: {key_path}")
    else:
        console.print(f"ssh key already present: {key_path}")


@host_app.command("ssh-key-enroll")
def host_ssh_key_enroll(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "One SSH host target name or selector that must resolve to exactly "
                "one configured host target."
            )
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
) -> None:
    """Enroll one managed public key into the remote authorized_keys file."""
    _, manifest = _load_host_target_manifest(config)
    resolved_target = _resolve_single_host_target(
        target,
        manifest,
        command_name="ssh-key-enroll",
    )
    public_key_path = _enroll_managed_host_ssh_key(resolved_target)
    console.print(f"enrolled public key for {resolved_target.name}: {public_key_path}")


@host_app.command("ssh")
def host_ssh(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional SSH host target name or selector that must resolve to "
                "exactly one configured host target."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Interactively choose one SSH host target.",
        ),
    ] = False,
) -> None:
    """Open one interactive SSH session using the configured Dev Fortress target."""
    _, manifest = _load_host_target_manifest(config)
    if interactive:
        candidate_targets = (
            [
                target_definition
                for target_definition in manifest.targets
                if target_definition.connection == "ssh"
            ]
            if target is None
            else _resolve_host_targets(target, manifest)
        )
        resolved_target = _interactive_select_single_host_target(
            candidate_targets, command_name="ssh"
        )
    else:
        if target is None:
            console.print("target is required unless --interactive is used")
            raise typer.Exit(code=2)
        resolved_target = _resolve_single_host_target(
            target, manifest, command_name="ssh"
        )
    raise typer.Exit(code=_ssh_single_host_target(resolved_target))


@host_app.command("doctor")
def host_doctor(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional host target selector to inspect. Supports exact names, "
                "shell-style wildcards, and the alias 'all'. Defaults to all configured targets."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    probe: Annotated[
        bool,
        typer.Option(
            "--probe",
            help="Attempt a small non-interactive SSH probe for SSH targets.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Interactively choose one or more host targets to inspect.",
        ),
    ] = False,
) -> None:
    """Inspect host-target readiness before attempting bootstrap."""
    resolved_path, manifest = _load_host_target_manifest(config)
    if interactive:
        candidate_targets = (
            manifest.targets
            if target is None
            else _resolve_host_targets(target, manifest)
        )
        resolved_targets = _interactive_select_host_targets(candidate_targets)
    else:
        resolved_targets = (
            manifest.targets
            if target is None
            else _resolve_host_targets(target, manifest)
        )
    if not _run_host_doctor(
        resolved_targets,
        config_path=resolved_path,
        probe=probe,
        json_output=json_output,
    ):
        raise typer.Exit(code=1)


@host_app.command("validate")
def host_validate(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional host target selector to validate. Supports exact names, "
                "shell-style wildcards, and the alias 'all'."
            ),
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for automation or agentic consumers.",
        ),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Interactively choose one or more host targets to validate.",
        ),
    ] = False,
    ask_become_pass: Annotated[
        bool,
        typer.Option(
            "--ask-become-pass",
            "-K",
            help="Pass --ask-become-pass through to ansible-playbook during bootstrap stages.",
        ),
    ] = False,
) -> None:
    """Run the standard doctor/bootstrap convergence loop for one or more host targets."""
    resolved_path, manifest = _load_host_target_manifest(config)
    if interactive:
        candidate_targets = (
            manifest.targets
            if target is None
            else _resolve_host_targets(target, manifest)
        )
        resolved_targets = _interactive_select_host_targets(candidate_targets)
    else:
        if target is None:
            console.print("target is required unless --interactive is used")
            raise typer.Exit(code=2)
        resolved_targets = _resolve_host_targets(target, manifest)
    results: list[dict[str, object]] = []
    success = True
    for resolved_target in resolved_targets:
        target_success = _validate_host_target(
            resolved_target,
            config_path=resolved_path,
            json_output=False,
            ask_become_pass=ask_become_pass,
        )
        results.append({"target": resolved_target.name, "success": target_success})
        success = success and target_success

    if json_output:
        _json_dump(
            {
                "config": str(resolved_path),
                "targets": results,
                "success": success,
            }
        )
    if not success:
        raise typer.Exit(code=1)


@host_app.command("bootstrap")
def host_bootstrap(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional host target selector to bootstrap. Supports exact names, "
                "shell-style wildcards, and the alias 'all'. Defaults to all configured targets."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            resolve_path=True,
            help="Path to the host target TOML config.",
        ),
    ] = None,
    ensure_ssh_keys: Annotated[
        bool,
        typer.Option(
            "--ensure-ssh-keys",
            help="Generate missing managed SSH keys for SSH targets before bootstrap.",
        ),
    ] = False,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Run ansible-playbook in check mode.",
        ),
    ] = False,
    ask_become_pass: Annotated[
        bool,
        typer.Option(
            "--ask-become-pass",
            "-K",
            help="Pass --ask-become-pass through to ansible-playbook.",
        ),
    ] = False,
) -> None:
    """Run the thin inventory-driven host bootstrap playbook for one or more targets."""
    _, manifest = _load_host_target_manifest(config)
    resolved_targets = (
        manifest.targets if target is None else _resolve_host_targets(target, manifest)
    )
    raise typer.Exit(
        code=_bootstrap_host_targets(
            resolved_targets,
            ensure_ssh_keys=ensure_ssh_keys,
            check=check,
            ask_become_pass=ask_become_pass,
        )
    )


@completion_app.command("show")
def completion_show(
    shell: Annotated[
        str,
        typer.Argument(
            help="Shell name to generate completion source for. Currently: zsh."
        ),
    ] = "zsh",
) -> None:
    """Print ft shell completion source for one supported shell."""
    console.print(_generate_ft_completion_source(shell), end="")


@completion_app.command("path")
def completion_path(
    shell: Annotated[
        str,
        typer.Argument(
            help="Shell name to resolve the installed completion artifact path for."
        ),
    ] = "zsh",
) -> None:
    """Print the XDG-managed completion artifact path for one supported shell."""
    resolved_shell = _require_supported_completion_shell(shell)
    typer.echo(str(_completion_output_path(resolved_shell)))


@completion_app.command("install")
def completion_install(
    shell: Annotated[
        str,
        typer.Argument(
            help="Shell name to generate and install completion for. Currently: zsh."
        ),
    ] = "zsh",
) -> None:
    """Generate and install ft shell completion into an XDG-managed runtime path."""
    resolved_shell = _require_supported_completion_shell(shell)
    output_path = _completion_output_path(resolved_shell)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _generate_ft_completion_source(resolved_shell), encoding="utf-8"
    )
    typer.echo(f"Installed completion to {output_path}")


@app.command("plan", hidden=False)
def plan(
    tool: Annotated[str | None, typer.Option(help="Plan only the named tool.")] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
    resolve_latest: Annotated[
        bool,
        typer.Option(
            "--resolve-latest/--use-manifest-version",
            help="Resolve current upstream GitHub releases for tools configured to do so.",
        ),
    ] = True,
) -> None:
    """Compatibility alias for `ft tool plan`."""
    tool_plan(
        tool=tool,
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        resolve_latest=resolve_latest,
    )


@app.command("doctor")
def doctor(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional container target selector to inspect. Supports exact "
                "names, shell-style wildcards, and the alias 'all'. Defaults to all "
                "known disposable container targets."
            )
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Render structured JSON for agentic or automated health checks.",
        ),
    ] = False,
) -> None:
    """Run a quick operator-oriented health check across host and container state."""
    resolved_targets = (
        list(KNOWN_CONTAINER_TARGETS)
        if target is None
        else _resolve_container_targets(target)
    )
    if not _run_doctor(resolved_targets, json_output=json_output):
        raise typer.Exit(code=1)


@app.command("install", hidden=False)
def install(
    tool: Annotated[
        str | None, typer.Option(help="Install only the named tool.")
    ] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
    healthcheck: Annotated[
        bool | None,
        typer.Option(
            "--healthcheck/--no-healthcheck",
            help="Run the configured healthcheck after installation.",
        ),
    ] = None,
    resolve_latest: Annotated[
        bool,
        typer.Option(
            "--resolve-latest/--use-manifest-version",
            help="Resolve current upstream GitHub releases for tools configured to do so.",
        ),
    ] = True,
) -> None:
    """Compatibility alias for `ft tool install`."""
    tool_install(
        tool=tool,
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        healthcheck=healthcheck,
        resolve_latest=resolve_latest,
    )
