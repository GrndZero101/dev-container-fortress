"""Typer CLI for ft."""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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
)
from ft.platforms import detect_architecture, detect_system
from ft.settings import FtSettings

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
        "Manage pinned tool installation plans and installs from the shared manifest."
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
app.add_typer(completion_app, name="completion")

console = Console()
KNOWN_CONTAINER_TARGETS = ("ubuntu", "alpine")
SUPPORTED_SHELL_CONFIG_SOURCES = ("github", "local")


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
) -> list[tuple[str, ToolDefinition]]:
    """Resolve the tool subset requested by the user."""
    if requested_tool is None:
        return manifest.enabled_tools()
    if requested_tool not in manifest.tools:
        raise typer.BadParameter(f"unknown tool: {requested_tool}", param_hint="--tool")
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
    table.add_row("version", plan.tool.version)
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
) -> int:
    """Run the host bootstrap playbook for one or more configured targets."""
    playbook_path = _host_playbook_path()
    ansible_config_path = _ansible_config_path()
    if not playbook_path.is_file():
        console.print(f"missing playbook: {playbook_path}")
        return 1
    if not ansible_config_path.is_file():
        console.print(f"missing ansible config: {ansible_config_path}")
        return 1
    if shutil.which("ansible-playbook") is None:
        console.print("ansible-playbook not found in PATH")
        return 1

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
            return 1

    inventory = _build_host_inventory(targets)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".yml", delete=False
    ) as handle:
        handle.write(_yaml_dump(inventory))
        inventory_path = Path(handle.name)

    command = ["ansible-playbook", "-i", str(inventory_path), str(playbook_path)]
    if check:
        command.append("--check")
    ansible_env = os.environ.copy()
    ansible_env["ANSIBLE_CONFIG"] = str(ansible_config_path)

    try:
        return _run_streaming_command(command, env=ansible_env).returncode
    finally:
        inventory_path.unlink(missing_ok=True)


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

    for command_name in (
        "starship",
        "atuin",
        "zoxide",
        "fzf",
        "fortress-hud",
        "csm",
        "ft",
    ):
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
    shell_config_source: str,
    shell_config_repo_url: str,
    shell_config_branch: str,
    shell_config_local_dir: str | None,
    shell_config_stage_from: Path | None,
    no_cache: bool,
) -> bool:
    """Build one disposable container image target from the repo Dockerfile."""
    dockerfile_path = _dockerfile_for_target(target)
    image_tag = _image_tag_for_target(target)

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

    build_command.extend(
        [
            "-f",
            str(dockerfile_path),
            "-t",
            image_tag,
            str(_repo_root()),
        ]
    )
    result = _run_streaming_command(build_command)
    return result.returncode == 0


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

    for name, tool_definition in _selected_tools(manifest_model, tool):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
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

    for name, tool_definition in _selected_tools(manifest_model, tool):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
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
) -> None:
    """Inspect host-target readiness before attempting bootstrap."""
    resolved_path, manifest = _load_host_target_manifest(config)
    resolved_targets = (
        manifest.targets if target is None else _resolve_host_targets(target, manifest)
    )
    if not _run_host_doctor(
        resolved_targets,
        config_path=resolved_path,
        probe=probe,
        json_output=json_output,
    ):
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
) -> None:
    """Compatibility alias for `ft tool plan`."""
    tool_plan(
        tool=tool,
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
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
    )
