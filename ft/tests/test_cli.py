"""CLI and installer tests for ft."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tomllib

import pytest
import typer
from typer.testing import CliRunner

from ft.cli import (
    _container_host_ssh_public_key_path,
    _effective_install_root,
    _host_target_manifest_toml,
    _last_non_empty_line,
    _parse_ansible_play_recap,
    _resolve_container_targets,
    _resolve_host_targets,
    _resolve_single_container_target,
    _up_single_container_target,
    _upsert_host_targets,
    _stage_local_shell_config,
    app,
)
from ft.installer import build_plan, install_tool
from ft.models import (
    HostTargetManifest,
    IntegrityConfig,
    ToolAsset,
    ToolDefinition,
    WorkspaceProfileManifest,
)

runner = CliRunner()


def _write_host_config(tmp_path: Path) -> Path:
    """Write a small host-target config for CLI tests."""
    config_path = tmp_path / "hosts.toml"
    config_path.write_text(
        """[[targets]]
name = "localhost"
kind = "workstation"
connection = "local"
auth_method = "local"
tags = ["local", "bootstrap"]

[[targets]]
name = "dev-fortress-ubuntu"
kind = "docker"
connection = "ssh"
host = "127.0.0.1"
port = 2222
user = "vscode"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-ubuntu"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["docker", "ubuntu"]

[[targets]]
name = "dev-fortress-alpine"
kind = "docker"
connection = "ssh"
host = "127.0.0.1"
port = 2223
user = "vscode"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-alpine"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["docker", "alpine"]

[[targets]]
name = "workstation-example"
kind = "workstation"
connection = "ssh"
host = "workstation.example.internal"
user = "devops"
auth_method = "ssh_key"
ssh_key_name = "workstation-devops"
tags = ["ssh", "workstation"]

[[targets]]
name = "dev-fortress-ec2-dev"
kind = "cloud"
connection = "ssh"
host = "ec2.example.internal"
user = "ubuntu"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-ec2-dev"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["ssh", "ubuntu", "cloud", "disposable"]
""",
        encoding="utf-8",
    )
    return config_path


def test_host_group_uses_help_when_no_args_are_passed() -> None:
    """Host subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["host"])

    assert result.exit_code == 0
    assert (
        "Model, inspect, and render SSH-oriented Dev Fortress host targets"
        in result.stdout
    )
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "inventory" in result.stdout
    assert "ssh-key-path" in result.stdout
    assert "ssh-key" in result.stdout
    assert "ssh-key-enroll" in result.stdout
    assert "ssh" in result.stdout
    assert "doctor" in result.stdout
    assert "validate" in result.stdout
    assert "bootstrap" in result.stdout


def test_workspace_group_uses_help_when_no_args_are_passed() -> None:
    """Workspace subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["workspace"])

    assert result.exit_code == 0
    assert "mounted Dev Fortress daily-driver workspace containers" in result.stdout
    assert "build" in result.stdout
    assert "status" in result.stdout
    assert "up" in result.stdout
    assert "down" in result.stdout
    assert "reset" in result.stdout
    assert "enter" in result.stdout
    assert "doctor" in result.stdout


def test_workspace_auth_group_uses_help_when_no_args_are_passed() -> None:
    """Workspace auth subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["workspace", "auth"])

    assert result.exit_code == 0
    assert "Inspect auth and persisted-state handoff points" in result.stdout
    assert "doctor" in result.stdout


def test_infra_group_uses_help_when_no_args_are_passed() -> None:
    """Infra subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["infra"])

    assert result.exit_code == 0
    assert "Run thin Terraform-backed infrastructure workflows" in result.stdout
    assert "aws-disposable-ubuntu" in result.stdout


def test_host_target_resolution_supports_all_and_wildcards() -> None:
    """Host target selectors should support exact, all, and wildcard input."""
    manifest = HostTargetManifest.model_validate(
        {
            "targets": [
                {
                    "name": "localhost",
                    "kind": "workstation",
                    "connection": "local",
                    "auth_method": "local",
                },
                {
                    "name": "dev-fortress-ubuntu",
                    "kind": "docker",
                    "connection": "ssh",
                    "host": "127.0.0.1",
                    "user": "vscode",
                },
            ]
        }
    )

    assert [target.name for target in _resolve_host_targets("all", manifest)] == [
        "localhost",
        "dev-fortress-ubuntu",
    ]
    assert [target.name for target in _resolve_host_targets("local*", manifest)] == [
        "localhost",
    ]
    assert [target.name for target in _resolve_host_targets("dev-*", manifest)] == [
        "dev-fortress-ubuntu",
    ]


def test_host_list_supports_json_output(tmp_path: Path) -> None:
    """Host list should render structured JSON for configured targets."""
    config_path = _write_host_config(tmp_path)

    result = runner.invoke(
        app, ["host", "list", "--json", "--config", str(config_path)]
    )

    assert result.exit_code == 0
    assert '"targets"' in result.stdout
    assert '"localhost"' in result.stdout
    assert '"dev-fortress-ubuntu"' in result.stdout


def test_host_list_defaults_to_layered_example_targets(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host commands should fall back to the example manifest when no user config exists."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["host", "list", "--json"])

    assert result.exit_code == 0
    assert '"dev-fortress-ubuntu"' in result.stdout
    assert '"dev-fortress-alpine"' in result.stdout


def test_host_list_merges_user_targets_with_example_targets(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Default host loading should merge built-in example targets with user targets."""
    user_config_dir = tmp_path / "config" / "dev-container-fortress"
    user_config_dir.mkdir(parents=True, exist_ok=True)
    (user_config_dir / "hosts.toml").write_text(
        """[[targets]]
name = "dev-fortress-ec2-dev"
kind = "cloud"
connection = "ssh"
host = "ec2.example.internal"
user = "ubuntu"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-ec2-dev"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["ssh", "ubuntu", "cloud", "disposable"]
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["host", "list", "--json"])

    assert result.exit_code == 0
    assert '"dev-fortress-ubuntu"' in result.stdout
    assert '"dev-fortress-alpine"' in result.stdout
    assert '"dev-fortress-ec2-dev"' in result.stdout


def test_host_show_renders_one_target(tmp_path: Path) -> None:
    """Host show should render detail for exactly one resolved target."""
    config_path = _write_host_config(tmp_path)

    result = runner.invoke(
        app, ["host", "show", "dev-fortress-ubuntu", "--config", str(config_path)]
    )

    assert result.exit_code == 0
    assert "dev-fortress-ubuntu host target" in result.stdout
    assert "ssh_private_key" in result.stdout


def test_host_inventory_renders_yaml(tmp_path: Path) -> None:
    """Host inventory should render a minimal YAML inventory by default."""
    config_path = _write_host_config(tmp_path)

    result = runner.invoke(app, ["host", "inventory", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "all:" in result.stdout
    assert "dev_fortress:" in result.stdout
    assert 'ansible_connection: "ssh"' in result.stdout
    assert 'ansible_python_interpreter: "/usr/bin/python3"' in result.stdout
    assert (
        'ansible_ssh_common_args: "-o StrictHostKeyChecking=yes -o UserKnownHostsFile='
        in result.stdout
    )


def test_host_target_manifest_toml_round_trips() -> None:
    """Host-target TOML rendering should round-trip through the manifest model."""
    manifest = HostTargetManifest.model_validate(
        {
            "targets": [
                {
                    "name": "dev-fortress-ec2-dev",
                    "kind": "cloud",
                    "connection": "ssh",
                    "host": "ec2.example.internal",
                    "user": "ubuntu",
                    "auth_method": "ssh_key",
                    "ssh_key_name": "dev-fortress-ec2-dev",
                    "ansible_python_interpreter": "/usr/bin/python3",
                    "tags": ["ssh", "ubuntu", "cloud", "disposable"],
                }
            ]
        }
    )

    rendered = _host_target_manifest_toml(manifest)
    round_tripped = HostTargetManifest.model_validate(tomllib.loads(rendered))

    assert round_tripped.model_dump() == manifest.model_dump()


def test_upsert_host_targets_replaces_existing_target() -> None:
    """Imported Terraform targets should replace existing targets by name."""
    existing_manifest = HostTargetManifest.model_validate(
        {
            "targets": [
                {
                    "name": "dev-fortress-ec2-dev",
                    "kind": "cloud",
                    "connection": "ssh",
                    "host": "old.example.internal",
                    "user": "ubuntu",
                    "auth_method": "ssh_key",
                    "ssh_key_name": "dev-fortress-ec2-dev",
                    "tags": ["old"],
                },
                {
                    "name": "localhost",
                    "kind": "workstation",
                    "connection": "local",
                    "auth_method": "local",
                    "tags": ["local"],
                },
            ]
        }
    )
    imported_targets = [
        HostTargetManifest.model_validate(
            {
                "targets": [
                    {
                        "name": "dev-fortress-ec2-dev",
                        "kind": "cloud",
                        "connection": "ssh",
                        "host": "new.example.internal",
                        "user": "ubuntu",
                        "auth_method": "ssh_key",
                        "ssh_key_name": "dev-fortress-ec2-dev",
                        "ansible_python_interpreter": "/usr/bin/python3",
                        "tags": ["ssh", "cloud"],
                    }
                ]
            }
        ).targets[0]
    ]

    merged_manifest = _upsert_host_targets(existing_manifest, imported_targets)

    assert [target.name for target in merged_manifest.targets] == [
        "dev-fortress-ec2-dev",
        "localhost",
    ]
    assert merged_manifest.targets[0].host == "new.example.internal"
    assert merged_manifest.targets[1].name == "localhost"


def test_host_import_terraform_creates_config_from_outputs(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Terraform host import should create a host config from Terraform outputs."""
    config_path = tmp_path / "hosts.toml"
    terraform_dir = tmp_path / "terraform"
    terraform_dir.mkdir()

    payload = {
        "host_target_toml_fragment": {
            "sensitive": False,
            "type": "string",
            "value": """[[targets]]
name = "dev-fortress-ec2-dev"
kind = "cloud"
connection = "ssh"
host = "ec2.example.internal"
port = 22
user = "ubuntu"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-ec2-dev"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["ssh", "ubuntu", "cloud", "disposable"]
""",
        }
    }

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/terraform")
    monkeypatch.setattr(
        "ft.cli._run_command",
        lambda command: subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(payload), stderr=""
        ),
    )

    result = runner.invoke(
        app,
        [
            "host",
            "import-terraform",
            "--terraform-dir",
            str(terraform_dir),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    manifest = HostTargetManifest.model_validate(
        tomllib.loads(config_path.read_text(encoding="utf-8"))
    )
    assert [target.name for target in manifest.targets] == ["dev-fortress-ec2-dev"]
    assert manifest.targets[0].host == "ec2.example.internal"


def test_host_import_terraform_upserts_existing_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Terraform host import should update matching targets instead of duplicating them."""
    config_path = _write_host_config(tmp_path)
    terraform_dir = tmp_path / "terraform"
    terraform_dir.mkdir()

    payload = {
        "host_target_toml_fragment": {
            "sensitive": False,
            "type": "string",
            "value": """[[targets]]
name = "dev-fortress-ec2-dev"
kind = "cloud"
connection = "ssh"
host = "fresh-ec2.example.internal"
port = 22
user = "ubuntu"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-ec2-dev"
ansible_python_interpreter = "/usr/bin/python3"
tags = ["ssh", "ubuntu", "cloud", "disposable"]
""",
        }
    }

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/terraform")
    monkeypatch.setattr(
        "ft.cli._run_command",
        lambda command: subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(payload), stderr=""
        ),
    )

    result = runner.invoke(
        app,
        [
            "host",
            "import-terraform",
            "--terraform-dir",
            str(terraform_dir),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    manifest = HostTargetManifest.model_validate(
        tomllib.loads(config_path.read_text(encoding="utf-8"))
    )
    names = [target.name for target in manifest.targets]
    assert names.count("dev-fortress-ec2-dev") == 1
    imported_target = next(
        target for target in manifest.targets if target.name == "dev-fortress-ec2-dev"
    )
    assert imported_target.host == "fresh-ec2.example.internal"


def test_infra_aws_disposable_ubuntu_plan_injects_tf_vars(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Infra plan should export TF_VAR values from the managed SSH key."""
    terraform_dir = tmp_path / "terraform"
    terraform_dir.mkdir()
    public_key_path = tmp_path / "dev_fortress_ed25519.pub"
    public_key_path.write_text("ssh-ed25519 AAAATEST dev-fortress-ec2-dev\n")
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/terraform")
    monkeypatch.setattr(
        "ft.cli._ensure_managed_ssh_public_key_for_name",
        lambda target_name, seed_config_path: public_key_path,
    )

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, env))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)

    result = runner.invoke(
        app,
        [
            "infra",
            "aws-disposable-ubuntu",
            "plan",
            "--terraform-dir",
            str(terraform_dir),
        ],
    )

    assert result.exit_code == 0
    assert [call[0][-1] for call in calls] == ["init", "validate", "plan"]
    for _, env in calls:
        assert env is not None
        assert env["TF_IN_AUTOMATION"] == "1"
        assert env["TF_VAR_name"] == "dev-fortress-ec2-dev"
        assert (
            env["TF_VAR_ssh_public_key"] == "ssh-ed25519 AAAATEST dev-fortress-ec2-dev"
        )


def test_infra_aws_disposable_ubuntu_apply_auto_imports_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Infra apply should import the Terraform host target by default."""
    terraform_dir = tmp_path / "terraform"
    terraform_dir.mkdir()
    public_key_path = tmp_path / "dev_fortress_ed25519.pub"
    public_key_path.write_text("ssh-ed25519 AAAATEST dev-fortress-ec2-dev\n")
    calls: list[list[str]] = []
    import_calls: list[tuple[Path, Path | None]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/terraform")
    monkeypatch.setattr(
        "ft.cli._ensure_managed_ssh_public_key_for_name",
        lambda target_name, seed_config_path: public_key_path,
    )

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def fake_import(
        terraform_dir_arg: Path, config_path_arg: Path | None
    ) -> dict[str, object]:
        import_calls.append((terraform_dir_arg, config_path_arg))
        return {
            "config": str(tmp_path / "hosts.toml"),
            "terraform_dir": str(terraform_dir_arg),
            "imported_targets": ["dev-fortress-ec2-dev"],
            "total_targets": 1,
        }

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)
    monkeypatch.setattr("ft.cli._import_terraform_host_targets", fake_import)

    result = runner.invoke(
        app,
        [
            "infra",
            "aws-disposable-ubuntu",
            "apply",
            "--terraform-dir",
            str(terraform_dir),
            "--auto-approve",
        ],
    )

    assert result.exit_code == 0
    assert [command[-1] for command in calls] == ["init", "validate", "-auto-approve"]
    assert calls[2][-2] == "apply"
    assert import_calls == [(terraform_dir, None)]


def test_host_ssh_key_path_uses_xdg_state(tmp_path: Path, monkeypatch: object) -> None:
    """Host ssh-key-path should resolve into the XDG-managed Dev Fortress state root."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    result = runner.invoke(
        app,
        ["host", "ssh-key-path", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == str(
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ubuntu"
        / "dev_fortress_ed25519"
    )


def test_host_ssh_runs_with_managed_key_and_known_hosts(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh should reuse the managed key and known-hosts policy."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    private_key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ec2-dev"
        / "dev_fortress_ed25519"
    )
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_text("private", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ssh")
    monkeypatch.setattr(
        "ft.cli._refresh_managed_known_host",
        lambda target: tmp_path / "known_hosts",
    )
    monkeypatch.setattr("ft.cli._ensure_host_target_runtime_ready", lambda target: True)

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)

    result = runner.invoke(
        app,
        ["host", "ssh", "dev-fortress-ec2-dev", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls
    assert calls[0][0] == "ssh"
    assert "-i" in calls[0]
    assert str(private_key_path) in calls[0]
    assert "StrictHostKeyChecking=yes" in " ".join(calls[0])
    assert "UserKnownHostsFile=" in " ".join(calls[0])
    assert calls[0][-1] == "ubuntu@ec2.example.internal"


def test_host_ssh_fails_when_managed_key_is_missing(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh should fail clearly when the managed SSH key is missing."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ssh")

    result = runner.invoke(
        app,
        ["host", "ssh", "dev-fortress-ec2-dev", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "missing managed ssh key for dev-fortress-ec2-dev" in result.stdout


def test_host_ssh_auto_starts_matching_docker_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh should auto-start the matching disposable container for docker targets."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    private_key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ubuntu"
        / "dev_fortress_ed25519"
    )
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_text("private", encoding="utf-8")
    calls: list[list[str]] = []
    up_calls: list[str] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ssh")
    monkeypatch.setattr(
        "ft.cli._refresh_managed_known_host",
        lambda target: tmp_path / "known_hosts",
    )
    monkeypatch.setattr(
        "ft.cli._ensure_host_target_runtime_ready",
        lambda target: up_calls.append(target.name) is None or True,
    )

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)

    result = runner.invoke(
        app,
        ["host", "ssh", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert up_calls == ["dev-fortress-ubuntu"]
    assert calls
    assert calls[0][-1] == "vscode@127.0.0.1"


def test_host_ssh_interactive_uses_selected_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh should accept one target from the interactive selector."""
    config_path = _write_host_config(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(
        "ft.cli._interactive_select_single_host_target",
        lambda targets, command_name: targets[0],
    )

    def fake_ssh_single_host_target(target: object) -> int:
        calls.append(target.name)
        return 0

    monkeypatch.setattr("ft.cli._ssh_single_host_target", fake_ssh_single_host_target)

    result = runner.invoke(
        app,
        ["host", "ssh", "--interactive", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == ["dev-fortress-ubuntu"]


def test_host_show_includes_managed_known_hosts_path(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host show should surface the managed known-hosts file path for SSH targets."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    result = runner.invoke(
        app, ["host", "show", "dev-fortress-ubuntu", "--config", str(config_path)]
    )

    assert result.exit_code == 0
    assert "known_hosts" in result.stdout
    assert "dev-fortress-ubuntu" in result.stdout


def test_root_cli_uses_help_when_no_args_are_passed() -> None:
    """The root CLI should show help instead of erroring on empty invocation."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Operator CLI for Dev Fortress" in result.stdout
    assert "tool" in result.stdout
    assert "container" in result.stdout
    assert "workspace" in result.stdout
    assert "host" in result.stdout
    assert "doctor" in result.stdout
    assert "completion" in result.stdout


def test_container_group_uses_help_when_no_args_are_passed() -> None:
    """Container subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["container"])

    assert result.exit_code == 0
    assert (
        "Operate and validate Dev Fortress disposable container targets"
        in result.stdout
    )
    assert "validate" in result.stdout
    assert "build" in result.stdout
    assert "status" in result.stdout
    assert "up" in result.stdout
    assert "down" in result.stdout
    assert "reset" in result.stdout
    assert "refresh" in result.stdout
    assert "enter" in result.stdout


def test_workspace_status_defaults_to_all_profiles(monkeypatch: object) -> None:
    """Workspace status should render every repo-owned profile when omitted."""
    calls: list[list[str]] = []

    monkeypatch.setattr("ft.cli._workspace_profile_names", lambda: ["ubuntu-base"])
    monkeypatch.setattr(
        "ft.cli._render_workspace_status",
        lambda profiles: calls.append(profiles),
    )

    result = runner.invoke(app, ["workspace", "status"])

    assert result.exit_code == 0
    assert calls == [["ubuntu-base"]]


def test_workspace_profile_manifest_includes_named_profiles() -> None:
    """The repo-owned workspace manifest should expose the initial profile set."""
    from ft.cli import _load_workspace_profile_manifest, _workspace_profile_names

    assert _workspace_profile_names() == [
        "ubuntu-base",
        "ubuntu-cloud-aws",
        "ubuntu-cloud-azure",
        "ubuntu-full",
        "ubuntu-gitforge",
        "ubuntu-secrets",
    ]
    manifest = _load_workspace_profile_manifest()
    assert sorted(manifest.tool_layers) == ["aws", "azure", "gitforge", "secrets"]
    assert manifest.tool_layers["gitforge"].mode == "image_build"
    assert manifest.tool_layers["gitforge"].build_arg == "WORKSPACE_TOOL_LAYER_GITFORGE"


def test_workspace_build_uses_resolved_profile(monkeypatch: object) -> None:
    """Workspace build should resolve the named profile before building."""
    calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )

    def fake_build(profile_name: str, profile: object, **kwargs: object) -> bool:
        calls.append((profile_name, kwargs["shell_config_source"], kwargs["no_cache"]))
        return True

    monkeypatch.setattr("ft.cli._build_workspace_profile", fake_build)

    result = runner.invoke(
        app,
        [
            "workspace",
            "build",
            "ubuntu-base",
            "--shell-config-source",
            "local",
            "--no-cache",
        ],
    )

    assert result.exit_code == 0
    assert calls == [("ubuntu-base", "local", True)]


def test_build_workspace_profile_forwards_image_build_layer_args(
    monkeypatch: object,
) -> None:
    """Workspace build should pass image-build layer args through to Docker."""
    from ft.cli import _build_workspace_profile
    from ft.models import WorkspaceProfileDefinition

    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "ft.cli._load_workspace_profile_manifest",
        lambda: WorkspaceProfileManifest.model_validate(
            {
                "tool_layers": {
                    "gitforge": {
                        "description": "forge",
                        "mode": "image_build",
                        "build_arg": "WORKSPACE_TOOL_LAYER_GITFORGE",
                    }
                },
                "profiles": {
                    "ubuntu-gitforge": {
                        "description": "gitforge",
                        "container_target": "ubuntu",
                        "tool_layers": ["gitforge"],
                    }
                },
            }
        ),
    )

    def fake_build(target: str, **kwargs: object) -> bool:
        calls.append({"target": target, **kwargs})
        return True

    monkeypatch.setattr("ft.cli._build_single_container_target", fake_build)

    profile = WorkspaceProfileDefinition(
        description="gitforge",
        container_target="ubuntu",
        tool_layers=["gitforge"],
    )

    assert (
        _build_workspace_profile(
            "ubuntu-gitforge",
            profile,
            shell_config_source="github",
            shell_config_repo_url="https://github.com/GrndZero101/shell-config.git",
            shell_config_branch="main",
            shell_config_local_dir=None,
            shell_config_stage_from=None,
            no_cache=False,
        )
        is True
    )
    assert calls[0]["extra_build_args"] == ["WORKSPACE_TOOL_LAYER_GITFORGE=1"]


def test_workspace_up_passes_shell_config_checkout(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace up should forward the live shell-config checkout path."""
    shell_config_checkout = tmp_path / "shell-config"
    shell_config_checkout.mkdir()
    calls: list[tuple[str, Path | None]] = []

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )

    def fake_up(profile_name: str, profile: object, **kwargs: object) -> bool:
        calls.append((profile_name, kwargs["shell_config_checkout"]))
        return True

    monkeypatch.setattr("ft.cli._up_workspace_profile", fake_up)

    result = runner.invoke(
        app,
        [
            "workspace",
            "up",
            "ubuntu-base",
            "--shell-config-checkout",
            str(shell_config_checkout),
        ],
    )

    assert result.exit_code == 0
    assert calls == [("ubuntu-base", shell_config_checkout)]


def test_workspace_exec_runs_command(monkeypatch: object) -> None:
    """Workspace exec should pass the command vector through unchanged."""
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )
    monkeypatch.setattr(
        "ft.cli._exec_workspace_profile",
        lambda profile_name, command: calls.append((profile_name, command)) or 0,
    )

    result = runner.invoke(
        app,
        ["workspace", "exec", "ubuntu-base", "--", "zsh", "-lc", "pwd"],
    )

    assert result.exit_code == 0
    assert calls == [("ubuntu-base", ["zsh", "-lc", "pwd"])]


def test_workspace_doctor_supports_json_output(monkeypatch: object) -> None:
    """Workspace doctor should pass the JSON renderer flag through."""
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )

    def fake_doctor(
        profile_name: str,
        profile: object,
        *,
        shell_config_checkout: Path | None = None,
        json_output: bool = False,
    ) -> bool:
        calls.append((profile_name, json_output))
        return True

    monkeypatch.setattr("ft.cli._run_workspace_doctor", fake_doctor)

    result = runner.invoke(app, ["workspace", "doctor", "--json", "ubuntu-base"])

    assert result.exit_code == 0
    assert calls == [("ubuntu-base", True)]


def test_workspace_validate_supports_json_output(monkeypatch: object) -> None:
    """Workspace validate should emit structured JSON when requested."""
    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )
    monkeypatch.setattr(
        "ft.cli._validate_workspace_profile",
        lambda profile_name, profile, **kwargs: {
            "profile": profile_name,
            "container": f"dev-fortress-workspace-{profile_name}",
            "success": True,
            "checks": [{"stat": "OK", "check": "runtime_user", "detail": "vscode"}],
        },
    )

    result = runner.invoke(app, ["workspace", "validate", "--json", "ubuntu-base"])

    assert result.exit_code == 0
    assert '"profile": "ubuntu-base"' in result.stdout
    assert '"success": true' in result.stdout.lower()


def test_workspace_auth_doctor_supports_json_output(monkeypatch: object) -> None:
    """Workspace auth doctor should pass the JSON renderer flag through."""
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )

    def fake_auth_doctor(
        profile_name: str,
        profile: object,
        *,
        json_output: bool = False,
    ) -> bool:
        calls.append((profile_name, json_output))
        return True

    monkeypatch.setattr("ft.cli._run_workspace_auth_doctor", fake_auth_doctor)

    result = runner.invoke(app, ["workspace", "auth", "doctor", "--json", "ubuntu-base"])

    assert result.exit_code == 0
    assert calls == [("ubuntu-base", True)]


def test_workspace_auth_validate_supports_json_output(monkeypatch: object) -> None:
    """Workspace auth validate should emit structured JSON when requested."""
    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )
    monkeypatch.setattr(
        "ft.cli._validate_workspace_auth_runtime",
        lambda profile_name, profile: {
            "profile": profile_name,
            "container": f"dev-fortress-workspace-{profile_name}",
            "success": True,
            "checks": [
                {"stat": "OK", "check": "browser_helper", "detail": "ready"}
            ],
        },
    )

    result = runner.invoke(
        app,
        ["workspace", "auth", "validate", "--json", "ubuntu-base"],
    )

    assert result.exit_code == 0
    assert '"profile": "ubuntu-base"' in result.stdout
    assert '"success": true' in result.stdout.lower()


def test_workspace_mount_plan_supports_json_output(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace mount-plan should render structured JSON."""
    shell_config_checkout = tmp_path / "shell-config"
    shell_config_checkout.mkdir()

    monkeypatch.setattr(
        "ft.cli._resolve_workspace_profile",
        lambda profile_name: (
            profile_name,
            object(),
        ),
    )
    monkeypatch.setattr(
        "ft.cli._workspace_mount_plan_payload",
        lambda profile_name, profile, **kwargs: {
            "profile": profile_name,
            "target": "ubuntu",
            "working_directory": "/workspace/dev-container-fortress",
            "tool_layers": [
                {
                    "name": "gitforge",
                    "mode": "image_build",
                    "description": "forge state",
                    "build_arg": "WORKSPACE_TOOL_LAYER_GITFORGE",
                }
            ],
            "image_build_layers": ["gitforge"],
            "state_only_layers": [],
            "shell_config": {
                "requested_path": str(kwargs["shell_config_checkout"]),
                "resolved_path": str(kwargs["shell_config_checkout"]),
                "source": "explicit",
                "available": True,
                "detail": "using --shell-config-checkout",
            },
            "shell_config_checkout": str(kwargs["shell_config_checkout"]),
            "mounts": [
                {
                    "host_path": "/host/dev-container-fortress",
                    "container_path": "/workspace/dev-container-fortress",
                }
            ],
        },
    )

    result = runner.invoke(
        app,
        [
            "workspace",
            "mount-plan",
            "--json",
            "ubuntu-base",
            "--shell-config-checkout",
            str(shell_config_checkout),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["profile"] == "ubuntu-base"
    assert payload["tool_layers"][0]["name"] == "gitforge"
    assert payload["tool_layers"][0]["mode"] == "image_build"
    assert payload["image_build_layers"] == ["gitforge"]
    assert payload["shell_config"]["source"] == "explicit"


def test_workspace_shell_config_resolution_explicit(tmp_path: Path) -> None:
    """Explicit shell-config checkouts should resolve with clear provenance."""
    from ft.cli import _workspace_shell_config_resolution

    shell_config_checkout = tmp_path / "shell-config"
    shell_config_checkout.mkdir()

    resolution = _workspace_shell_config_resolution(shell_config_checkout)

    assert resolution["source"] == "explicit"
    assert resolution["available"] is True
    assert resolution["resolved_path"] == str(shell_config_checkout)


def test_workspace_shell_config_resolution_missing_default(monkeypatch: object) -> None:
    """Missing default shell-config checkouts should produce actionable detail."""
    from ft.cli import _workspace_shell_config_resolution

    monkeypatch.setattr("ft.cli._workspace_default_shell_config_checkout", lambda: None)

    resolution = _workspace_shell_config_resolution(None)

    assert resolution["source"] == "none"
    assert resolution["available"] is False
    assert "pass --shell-config-checkout" in str(resolution["detail"])


def test_workspace_auth_checks_reflect_profile_mounts(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace auth checks should reflect the profile's persisted mount policy."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.Path.home", lambda: tmp_path / "home")
    gh_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "workspaces"
        / "ubuntu-gitforge"
        / "config-gh"
    )
    gh_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "home" / ".aws").mkdir(parents=True, exist_ok=True)

    profile = WorkspaceProfileDefinition(
        description="mixed",
        persisted_mounts=["gh", "glab", "aws"],
        tool_layers=["gitforge", "aws"],
    )

    checks = _workspace_auth_checks("ubuntu-gitforge", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["ssh_agent"]["stat"] == "WARN"
    assert check_map["browser_env"]["stat"] == "INFO"
    assert check_map["github_cli_state"]["stat"] == "OK"
    assert check_map["gitlab_cli_state"]["stat"] == "WARN"
    assert check_map["aws_cli_state"]["stat"] == "OK"
    assert check_map["secrets_baseline"]["stat"] == "INFO"


def test_workspace_auth_checks_honor_browser_env(monkeypatch: object) -> None:
    """Workspace auth checks should report explicit browser env overrides."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.setenv("GH_BROWSER", "wslview")

    profile = WorkspaceProfileDefinition(
        description="gitforge",
        persisted_mounts=["gh"],
        tool_layers=["gitforge"],
    )

    checks = _workspace_auth_checks("ubuntu-gitforge", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["gh_browser_env"]["stat"] == "OK"
    assert check_map["gh_browser_env"]["detail"] == "wslview"


def test_workspace_auth_checks_report_wsl_browser_strategy(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace auth checks should describe the WSL browser-launch strategy."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.delenv("GH_BROWSER", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "dev-fortress")
    monkeypatch.setattr(
        "ft.cli._workspace_wsl_windows_system_path",
        lambda: tmp_path / "System32",
    )
    (tmp_path / "System32").mkdir()

    profile = WorkspaceProfileDefinition(
        description="gitforge",
        persisted_mounts=["gh"],
        tool_layers=["gitforge"],
    )

    checks = _workspace_auth_checks("ubuntu-gitforge", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["browser_strategy"]["stat"] == "OK"
    assert "/usr/local/bin/ft-host-browser-open" in check_map["browser_strategy"]["detail"]


def test_workspace_auth_checks_warn_for_secrets_layer(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace auth checks should warn when the secrets layer is selected but not implemented."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    profile = WorkspaceProfileDefinition(
        description="secrets",
        persisted_mounts=["cache", "share"],
        tool_layers=["secrets"],
    )

    checks = _workspace_auth_checks("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["secrets_baseline"]["stat"] == "WARN"


def test_workspace_layer_command_checks_include_gitforge_commands(
    monkeypatch: object,
) -> None:
    """Gitforge image-build layers should require forge CLIs and xdg-open at validation time."""
    from ft.cli import _workspace_layer_command_checks
    from ft.models import WorkspaceProfileDefinition, WorkspaceProfileManifest

    monkeypatch.setattr(
        "ft.cli._load_workspace_profile_manifest",
        lambda: WorkspaceProfileManifest.model_validate(
            {
                "tool_layers": {
                    "gitforge": {
                        "description": "forge",
                        "mode": "image_build",
                        "build_arg": "WORKSPACE_TOOL_LAYER_GITFORGE",
                    }
                },
                "profiles": {
                    "ubuntu-gitforge": {
                        "description": "gitforge",
                        "container_target": "ubuntu",
                        "tool_layers": ["gitforge"],
                    }
                },
            }
        ),
    )

    profile = WorkspaceProfileDefinition(
        description="gitforge",
        container_target="ubuntu",
        tool_layers=["gitforge"],
    )

    assert _workspace_layer_command_checks(profile) == ["gh", "glab", "xdg-open"]


def test_workspace_layer_command_checks_include_aws_command(
    monkeypatch: object,
) -> None:
    """AWS image-build layers should require the AWS CLI at validation time."""
    from ft.cli import _workspace_layer_command_checks
    from ft.models import WorkspaceProfileDefinition, WorkspaceProfileManifest

    monkeypatch.setattr(
        "ft.cli._load_workspace_profile_manifest",
        lambda: WorkspaceProfileManifest.model_validate(
            {
                "tool_layers": {
                    "aws": {
                        "description": "aws",
                        "mode": "image_build",
                        "build_arg": "WORKSPACE_TOOL_LAYER_AWS",
                    }
                },
                "profiles": {
                    "ubuntu-cloud-aws": {
                        "description": "aws",
                        "container_target": "ubuntu",
                        "tool_layers": ["aws"],
                    }
                },
            }
        ),
    )

    profile = WorkspaceProfileDefinition(
        description="aws",
        container_target="ubuntu",
        tool_layers=["aws"],
    )

    assert _workspace_layer_command_checks(profile) == ["aws"]


def test_workspace_up_configures_wsl_browser_bridge(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace up should mount Windows interop and default browser envs on WSL hosts."""
    from ft.cli import _up_workspace_profile
    from ft.models import WorkspaceProfileDefinition

    commands: list[list[str]] = []
    windows_system_path = tmp_path / "mnt" / "c" / "Windows" / "System32"
    wsl_interop_root = tmp_path / "run" / "WSL"
    wsl_init_path = tmp_path / "init"
    browser_bridge_dir = tmp_path / "host-browser"
    browser_bridge_socket = browser_bridge_dir / "browser-open.sock"
    windows_system_path.mkdir(parents=True)
    wsl_interop_root.mkdir(parents=True)
    browser_bridge_dir.mkdir(parents=True)
    (wsl_interop_root / "622_interop").write_text("", encoding="utf-8")
    wsl_init_path.write_text("init\n", encoding="utf-8")

    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.delenv("GH_BROWSER", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "dev-fortress")
    monkeypatch.setenv("WSL_INTEROP", str(wsl_interop_root / "622_interop"))
    monkeypatch.setattr(
        "ft.cli._workspace_wsl_windows_system_path",
        lambda: windows_system_path,
    )
    monkeypatch.setattr(
        "ft.cli._workspace_wsl_interop_root",
        lambda: wsl_interop_root,
    )
    monkeypatch.setattr(
        "ft.cli._workspace_wsl_init_path",
        lambda: wsl_init_path,
    )
    monkeypatch.setattr(
        "ft.cli._ensure_workspace_host_browser_bridge",
        lambda profile_name: browser_bridge_socket,
    )
    monkeypatch.setattr("ft.cli._workspace_mount_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr("ft.cli._build_workspace_profile", lambda *args, **kwargs: True)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:4] == [
            "docker",
            "image",
            "inspect",
            "dev-container-fortress:workspace-ubuntu-gitforge",
        ]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[:4] == [
            "docker",
            "container",
            "inspect",
            "dev-fortress-workspace-ubuntu-gitforge",
        ]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command[:3] == ["docker", "run", "--detach"]:
            return subprocess.CompletedProcess(command, 0, stdout="cid\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    profile = WorkspaceProfileDefinition(
        description="gitforge",
        container_target="ubuntu",
        tool_layers=["gitforge"],
    )

    assert _up_workspace_profile("ubuntu-gitforge", profile) is True
    run_command = commands[-1]
    assert "--volume" in run_command
    assert (
        f"{browser_bridge_dir}:/tmp/dev-fortress-host-services"
        in run_command
    )
    assert f"{windows_system_path}:{windows_system_path}:ro" in run_command
    assert f"{wsl_init_path}:{wsl_init_path}:ro" in run_command
    assert f"{wsl_interop_root}:{wsl_interop_root}" in run_command
    assert "--env" in run_command
    assert (
        "DEV_FORTRESS_HOST_BROWSER_SOCKET="
        "/tmp/dev-fortress-host-services/browser-open.sock"
        in run_command
    )
    assert "BROWSER=/usr/local/bin/ft-host-browser-open" in run_command
    assert "GH_BROWSER=/usr/local/bin/ft-host-browser-open" in run_command
    assert "WSL_DISTRO_NAME=dev-fortress" in run_command
    assert f"WSL_INTEROP={wsl_interop_root / '622_interop'}" in run_command


def test_completion_group_uses_help_when_no_args_are_passed() -> None:
    """Completion subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["completion"])

    assert result.exit_code == 0
    assert "Generate and install shell completion artifacts" in result.stdout
    assert "show" in result.stdout
    assert "path" in result.stdout
    assert "install" in result.stdout


def test_doctor_defaults_to_all_targets(monkeypatch: object) -> None:
    """Doctor should inspect all known targets when none are specified."""
    calls: list[list[str]] = []

    def fake_run_doctor(targets: list[str], *, json_output: bool = False) -> bool:
        calls.append(targets + (["--json"] if json_output else []))
        return True

    monkeypatch.setattr("ft.cli._run_doctor", fake_run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert calls == [["ubuntu", "alpine"]]


def test_completion_path_uses_xdg_layout(monkeypatch: object) -> None:
    """Completion path should resolve into the XDG-managed Dev Fortress directory."""
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/dev-fortress-data")

    result = runner.invoke(app, ["completion", "path", "zsh"])

    assert result.exit_code == 0
    assert (
        result.stdout.strip()
        == "/tmp/dev-fortress-data/dev-container-fortress/completions/zsh/_ft"
    )


def test_completion_show_prints_generated_source(monkeypatch: object) -> None:
    """Completion show should print the generated shell source."""
    monkeypatch.setattr(
        "ft.cli._generate_ft_completion_source",
        lambda shell_name: "#compdef ft\n",
    )

    result = runner.invoke(app, ["completion", "show", "zsh"])

    assert result.exit_code == 0
    assert result.stdout == "#compdef ft\n"


def test_completion_install_writes_generated_source(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Completion install should write the generated artifact into the XDG path."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(
        "ft.cli._generate_ft_completion_source",
        lambda shell_name: "#compdef ft\n",
    )

    result = runner.invoke(app, ["completion", "install", "zsh"])

    output_path = tmp_path / "dev-container-fortress" / "completions" / "zsh" / "_ft"
    assert result.exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "#compdef ft\n"


def test_doctor_accepts_wildcard_target(monkeypatch: object) -> None:
    """Doctor should resolve wildcard selectors before running checks."""
    calls: list[list[str]] = []

    def fake_run_doctor(targets: list[str], *, json_output: bool = False) -> bool:
        calls.append(targets + (["--json"] if json_output else []))
        return True

    monkeypatch.setattr("ft.cli._run_doctor", fake_run_doctor)

    result = runner.invoke(app, ["doctor", "alp*"])

    assert result.exit_code == 0
    assert calls == [["alpine"]]


def test_doctor_supports_json_output(monkeypatch: object) -> None:
    """Doctor should pass the JSON renderer flag through to the shared helper."""
    calls: list[tuple[list[str], bool]] = []

    def fake_run_doctor(targets: list[str], *, json_output: bool = False) -> bool:
        calls.append((targets, json_output))
        return True

    monkeypatch.setattr("ft.cli._run_doctor", fake_run_doctor)

    result = runner.invoke(app, ["doctor", "--json", "ubuntu"])

    assert result.exit_code == 0
    assert calls == [(["ubuntu"], True)]


def test_host_doctor_supports_json_output(tmp_path: Path, monkeypatch: object) -> None:
    """Host doctor should emit structured JSON for configured targets."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    result = runner.invoke(
        app,
        ["host", "doctor", "localhost", "--json", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert '"success": true' in result.stdout.lower()
    assert '"localhost"' in result.stdout


def test_host_doctor_fails_for_missing_ssh_key(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host doctor should fail clearly when an SSH target key is missing."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    result = runner.invoke(
        app,
        ["host", "doctor", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "dev-fortress-ubuntu_ssh_key" in result.stdout
    assert "generate missing keys with `ft host ssh-key <target>`" in result.stdout


def test_host_doctor_probe_checks_ssh_reachability(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host doctor should support optional SSH probing for SSH targets."""
    config_path = _write_host_config(tmp_path)
    key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ubuntu"
        / "dev_fortress_ed25519"
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh-keyscan":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="[127.0.0.1]:2222 ssh-ed25519 AAAATEST\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    result = runner.invoke(
        app,
        [
            "host",
            "doctor",
            "dev-fortress-ubuntu",
            "--probe",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "ssh probe succeeded" in result.stdout


def test_host_doctor_probe_refreshes_managed_known_hosts(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host probe should refresh the managed known-hosts file for disposable targets."""
    config_path = _write_host_config(tmp_path)
    key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ubuntu"
        / "dev_fortress_ed25519"
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh-keyscan":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="[127.0.0.1]:2222 ssh-ed25519 AAAATEST\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    result = runner.invoke(
        app,
        [
            "host",
            "doctor",
            "dev-fortress-ubuntu",
            "--probe",
            "--config",
            str(config_path),
        ],
    )

    known_hosts_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "known_hosts"
        / "dev-fortress-ubuntu"
    )
    assert result.exit_code == 0
    assert (
        known_hosts_path.read_text(encoding="utf-8")
        == "[127.0.0.1]:2222 ssh-ed25519 AAAATEST\n"
    )


def test_host_doctor_probe_refreshes_managed_known_hosts_for_cloud_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host probe should refresh the managed known-hosts file for cloud disposable targets."""
    config_path = _write_host_config(tmp_path)
    key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ec2-dev"
        / "dev_fortress_ed25519"
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh-keyscan":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="[ec2.example.internal]:22 ssh-ed25519 AAACLOUD\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    result = runner.invoke(
        app,
        [
            "host",
            "doctor",
            "dev-fortress-ec2-dev",
            "--probe",
            "--config",
            str(config_path),
        ],
    )

    known_hosts_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "known_hosts"
        / "dev-fortress-ec2-dev"
    )
    assert result.exit_code == 0
    assert (
        known_hosts_path.read_text(encoding="utf-8")
        == "[ec2.example.internal]:22 ssh-ed25519 AAACLOUD\n"
    )


def test_host_doctor_probe_auto_starts_matching_docker_target(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host doctor probe should auto-start the matching docker SSH target."""
    config_path = _write_host_config(tmp_path)
    key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-alpine"
        / "dev_fortress_ed25519"
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    up_calls: list[str] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh-keyscan":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="[127.0.0.1]:2223 ssh-ed25519 AAAALPINE\n",
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "ft.cli._up_single_container_target",
        lambda target: up_calls.append(target) is None or True,
    )
    monkeypatch.setattr("ft.cli._wait_for_target_ssh_service", lambda target: True)
    monkeypatch.setattr("ft.cli._run_command", fake_run)

    result = runner.invoke(
        app,
        [
            "host",
            "doctor",
            "dev-fortress-alpine",
            "--probe",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert up_calls == ["alpine"]
    assert "ssh probe succeeded" in result.stdout


def test_host_doctor_interactive_uses_selected_targets(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host doctor should accept targets returned by the interactive selector."""
    config_path = _write_host_config(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(
        "ft.cli._interactive_select_host_targets",
        lambda targets: [targets[1], targets[2]],
    )

    def fake_run_host_doctor(
        targets: list[object],
        *,
        config_path: Path,
        probe: bool,
        json_output: bool,
    ) -> bool:
        calls.extend(target.name for target in targets)
        return True

    monkeypatch.setattr("ft.cli._run_host_doctor", fake_run_host_doctor)

    result = runner.invoke(
        app,
        ["host", "doctor", "--interactive", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == ["dev-fortress-ubuntu", "dev-fortress-alpine"]


def test_host_ssh_key_generates_managed_key(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh-key should generate the expected managed SSH key when missing."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        key_path = (
            tmp_path
            / "state"
            / "dev-container-fortress"
            / "ssh"
            / "dev-fortress-ubuntu"
            / "dev_fortress_ed25519"
        )
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("private\n", encoding="utf-8")
        key_path.with_name("dev_fortress_ed25519.pub").write_text(
            "public\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    result = runner.invoke(
        app,
        ["host", "ssh-key", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "generated ssh key:" in result.stdout


def test_host_ssh_key_enroll_installs_public_key(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh-key-enroll should install the managed public key on the target."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    calls: list[tuple[list[str], str]] = []

    def fake_keygen(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh-keyscan":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="[127.0.0.1]:2222 ssh-ed25519 AAAATEST\n",
                stderr="",
            )
        key_path = (
            tmp_path
            / "state"
            / "dev-container-fortress"
            / "ssh"
            / "dev-fortress-ubuntu"
            / "dev_fortress_ed25519"
        )
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("private\n", encoding="utf-8")
        key_path.with_name("dev_fortress_ed25519.pub").write_text(
            "ssh-ed25519 AAAATEST dev-fortress-ubuntu\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def fake_with_input(
        command: list[str], input_text: str
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, input_text))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_keygen)
    monkeypatch.setattr("ft.cli._run_command_with_input", fake_with_input)

    result = runner.invoke(
        app,
        ["host", "ssh-key-enroll", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls
    assert calls[0][0][0] == "ssh"
    assert calls[0][1] == "ssh-ed25519 AAAATEST dev-fortress-ubuntu\n"
    assert "UserKnownHostsFile=" in " ".join(calls[0][0])
    assert "enrolled public key for dev-fortress-ubuntu" in result.stdout


def test_host_bootstrap_runs_ansible_with_generated_inventory(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host bootstrap should render inventory and invoke ansible-playbook."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[list[str], dict[str, str] | None]] = []
    inventories: list[str] = []

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, env))
        inventory_path = Path(command[2])
        inventories.append(inventory_path.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ansible-playbook")

    result = runner.invoke(
        app,
        ["host", "bootstrap", "localhost", "--config", str(config_path), "--check"],
    )

    assert result.exit_code == 0
    assert calls
    assert calls[0][0][-1] == "--check"
    assert calls[0][1] is not None
    assert calls[0][1]["ANSIBLE_CONFIG"].endswith("ansible/ansible.cfg")
    assert "localhost:" in inventories[0]
    assert 'ansible_connection: "local"' in inventories[0]


def test_host_bootstrap_passes_ask_become_pass_to_ansible(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host bootstrap should pass -K through to ansible-playbook when requested."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_stream(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, env))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ansible-playbook")

    result = runner.invoke(
        app,
        [
            "host",
            "bootstrap",
            "localhost",
            "--config",
            str(config_path),
            "--ask-become-pass",
        ],
    )

    assert result.exit_code == 0
    assert calls
    assert "-K" in calls[0][0]


def test_host_bootstrap_fails_when_ssh_key_is_missing(
    tmp_path: Path, monkeypatch: object
) -> None:
    """SSH bootstrap should fail clearly when the managed key is missing."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ansible-playbook")

    result = runner.invoke(
        app,
        ["host", "bootstrap", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "missing managed ssh key for dev-fortress-ubuntu" in result.stdout
    assert "Run `ft host ssh-key" in result.stdout
    assert "--ensure-ssh-keys" in result.stdout


def test_host_validate_runs_doctor_and_bootstrap_sequence(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should run probe, check, apply, then convergence apply."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[str, object]] = []

    def fake_run_host_doctor(
        targets: list[object],
        *,
        config_path: Path,
        probe: bool,
        json_output: bool,
    ) -> bool:
        calls.append(("doctor", probe))
        return True

    def fake_bootstrap(
        targets: list[object],
        *,
        ensure_ssh_keys: bool,
        check: bool,
        ask_become_pass: bool,
    ) -> int:
        calls.append(("bootstrap", check, ask_become_pass))
        return 0

    def fake_bootstrap_with_result(
        targets: list[object],
        *,
        ensure_ssh_keys: bool,
        check: bool,
        ask_become_pass: bool,
        capture_recap: bool,
    ) -> dict[str, object]:
        calls.append(("bootstrap_result", check, ask_become_pass, capture_recap))
        return {
            "returncode": 0,
            "target_recaps": {targets[0].name: {"changed": 0}},
        }

    monkeypatch.setattr("ft.cli._run_host_doctor", fake_run_host_doctor)
    monkeypatch.setattr("ft.cli._bootstrap_host_targets", fake_bootstrap)
    monkeypatch.setattr(
        "ft.cli._bootstrap_host_targets_with_result", fake_bootstrap_with_result
    )

    result = runner.invoke(
        app,
        ["host", "validate", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [
        ("doctor", True),
        ("bootstrap", True, False),
        ("bootstrap", False, False),
        ("bootstrap_result", False, False, True),
    ]


def test_host_validate_stops_on_first_failure(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should stop once one validation stage fails."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[str, object]] = []

    def fake_run_host_doctor(
        targets: list[object],
        *,
        config_path: Path,
        probe: bool,
        json_output: bool,
    ) -> bool:
        calls.append(("doctor", probe))
        return True

    def fake_bootstrap(
        targets: list[object],
        *,
        ensure_ssh_keys: bool,
        check: bool,
        ask_become_pass: bool,
    ) -> int:
        calls.append(("bootstrap", check, ask_become_pass))
        return 1 if check else 0

    monkeypatch.setattr("ft.cli._run_host_doctor", fake_run_host_doctor)
    monkeypatch.setattr("ft.cli._bootstrap_host_targets", fake_bootstrap)

    result = runner.invoke(
        app,
        ["host", "validate", "dev-fortress-ubuntu", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert calls == [
        ("doctor", True),
        ("bootstrap", True, False),
    ]


def test_host_validate_passes_ask_become_pass_to_bootstrap(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should pass ask-become-pass to every bootstrap stage."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[str, object]] = []

    def fake_run_host_doctor(
        targets: list[object],
        *,
        config_path: Path,
        probe: bool,
        json_output: bool,
    ) -> bool:
        calls.append(("doctor", probe))
        return True

    def fake_bootstrap(
        targets: list[object],
        *,
        ensure_ssh_keys: bool,
        check: bool,
        ask_become_pass: bool,
    ) -> int:
        calls.append(("bootstrap", check, ask_become_pass))
        return 0

    def fake_bootstrap_with_result(
        targets: list[object],
        *,
        ensure_ssh_keys: bool,
        check: bool,
        ask_become_pass: bool,
        capture_recap: bool,
    ) -> dict[str, object]:
        calls.append(("bootstrap_result", check, ask_become_pass, capture_recap))
        return {
            "returncode": 0,
            "target_recaps": {targets[0].name: {"changed": 0}},
        }

    monkeypatch.setattr("ft.cli._run_host_doctor", fake_run_host_doctor)
    monkeypatch.setattr("ft.cli._bootstrap_host_targets", fake_bootstrap)
    monkeypatch.setattr(
        "ft.cli._bootstrap_host_targets_with_result", fake_bootstrap_with_result
    )

    result = runner.invoke(
        app,
        [
            "host",
            "validate",
            "localhost",
            "--config",
            str(config_path),
            "--ask-become-pass",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("doctor", True),
        ("bootstrap", True, True),
        ("bootstrap", False, True),
        ("bootstrap_result", False, True, True),
    ]


def test_host_validate_fails_when_final_convergence_still_changes(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should fail if the final bootstrap pass still reports changes."""
    config_path = _write_host_config(tmp_path)

    monkeypatch.setattr("ft.cli._run_host_doctor", lambda *args, **kwargs: True)
    monkeypatch.setattr("ft.cli._bootstrap_host_targets", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "ft.cli._bootstrap_host_targets_with_result",
        lambda targets, **kwargs: {
            "returncode": 0,
            "target_recaps": {targets[0].name: {"changed": 1}},
        },
    )

    result = runner.invoke(
        app,
        ["host", "validate", "localhost", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "did not converge cleanly: changed=1" in result.stdout


def test_host_validate_accepts_all_selector(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should iterate over every target matched by the selector."""
    config_path = _write_host_config(tmp_path)
    calls: list[str] = []

    def fake_validate_host_target(
        target: object,
        *,
        config_path: Path,
        json_output: bool,
        ask_become_pass: bool,
    ) -> bool:
        calls.append(target.name)
        return True

    monkeypatch.setattr("ft.cli._validate_host_target", fake_validate_host_target)

    result = runner.invoke(
        app,
        ["host", "validate", "all", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == [
        "localhost",
        "dev-fortress-ubuntu",
        "dev-fortress-alpine",
        "workstation-example",
        "dev-fortress-ec2-dev",
    ]


def test_host_validate_interactive_accepts_selected_targets(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host validate should accept targets returned by the interactive selector."""
    config_path = _write_host_config(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(
        "ft.cli._interactive_select_host_targets",
        lambda targets: [targets[1], targets[2]],
    )

    def fake_validate_host_target(
        target: object,
        *,
        config_path: Path,
        json_output: bool,
        ask_become_pass: bool,
    ) -> bool:
        calls.append(target.name)
        return True

    monkeypatch.setattr("ft.cli._validate_host_target", fake_validate_host_target)

    result = runner.invoke(
        app,
        ["host", "validate", "--interactive", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert calls == ["dev-fortress-ubuntu", "dev-fortress-alpine"]


def test_host_validate_requires_selector_without_interactive(tmp_path: Path) -> None:
    """Host validate should require a selector unless interactive mode is used."""
    config_path = _write_host_config(tmp_path)

    result = runner.invoke(app, ["host", "validate", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "target is required unless --interactive is used" in result.stdout


def test_plan_uses_environment_defaults(monkeypatch: object) -> None:
    """The CLI should honor environment-backed settings defaults."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    monkeypatch.setenv("FT_MANIFEST", str(manifest_path))
    monkeypatch.setenv("FT_TARGET", "ubuntu")
    monkeypatch.setenv("FT_SYSTEM", "linux")
    monkeypatch.setenv("FT_ARCHITECTURE", "amd64")

    result = runner.invoke(app, ["plan", "--tool", "atuin", "--use-manifest-version"])

    assert result.exit_code == 0
    assert "atuin plan" in result.stdout
    assert "18.13.6" in result.stdout
    assert "linux/amd64" in result.stdout


def test_container_target_resolution_supports_all_and_wildcards() -> None:
    """Container target selectors should support exact, all, and wildcard input."""
    assert _resolve_container_targets("ubuntu") == ["ubuntu"]
    assert _resolve_container_targets("all") == ["ubuntu", "alpine"]
    assert _resolve_container_targets("alp*") == ["alpine"]


def test_single_target_resolution_rejects_multi_match() -> None:
    """Interactive container commands should reject selectors that fan out."""
    with pytest.raises(typer.BadParameter):
        _resolve_single_container_target("*", command_name="shell")


def test_last_non_empty_line_prefers_the_final_meaningful_line() -> None:
    """Validation helpers should tolerate extra startup lines before the real value."""
    assert _last_non_empty_line("warning line\nvscode\n") == "vscode"


def test_parse_ansible_play_recap_reads_changed_counts() -> None:
    """Ansible recap parsing should preserve per-target change counters."""
    recap = _parse_ansible_play_recap(
        """
PLAY RECAP *********************************************************************
localhost : ok=11 changed=0 unreachable=0 failed=0 skipped=4 rescued=0 ignored=0
dev-fortress-ubuntu : ok=9 changed=2 unreachable=0 failed=0 skipped=1 rescued=0 ignored=0
"""
    )

    assert recap["localhost"]["changed"] == 0
    assert recap["dev-fortress-ubuntu"]["changed"] == 2


def test_parse_ansible_play_recap_accepts_logged_prefixes() -> None:
    """Ansible recap parsing should tolerate timestamped log prefixes."""
    recap = _parse_ansible_play_recap(
        """
2026-04-19 11:10:34,123 p=12345 u=timl n=ansible | PLAY RECAP ********************************
2026-04-19 11:10:34,124 p=12345 u=timl n=ansible | localhost : ok=14 changed=0 unreachable=0 failed=0 skipped=6 rescued=0 ignored=0
"""
    )

    assert recap["localhost"]["changed"] == 0
    assert recap["localhost"]["ok"] == 14


def test_container_validate_runs_for_wildcard_target(monkeypatch: object) -> None:
    """Validation should iterate the targets matched by the selector."""
    calls: list[str] = []

    def fake_validate(target: str) -> dict[str, object]:
        calls.append(target)
        return {
            "target": target,
            "container": f"{target}-container",
            "success": True,
            "checks": [],
        }

    monkeypatch.setattr("ft.cli._validate_single_container_target", fake_validate)

    result = runner.invoke(app, ["container", "validate", "*"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine"]


def test_container_validate_supports_json_output(monkeypatch: object) -> None:
    """Validation should emit structured JSON when requested."""

    def fake_validate(target: str) -> dict[str, object]:
        return {
            "target": target,
            "container": f"{target}-container",
            "success": True,
            "checks": [{"stat": "OK", "check": "runtime_user", "detail": "vscode"}],
        }

    monkeypatch.setattr("ft.cli._validate_single_container_target", fake_validate)

    result = runner.invoke(app, ["container", "validate", "--json", "ubuntu"])

    assert result.exit_code == 0
    assert '"success": true' in result.stdout.lower()
    assert '"target": "ubuntu"' in result.stdout


def test_container_build_runs_for_all_targets(monkeypatch: object) -> None:
    """Build should iterate every target selected by the wildcard-aware resolver."""
    calls: list[str] = []

    def fake_build(target: str, **kwargs: object) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._build_single_container_target", fake_build)

    result = runner.invoke(app, ["container", "build", "all"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine"]


def test_container_build_forwards_shell_config_options(monkeypatch: object) -> None:
    """Build should forward shell-config source controls into the shared helper."""
    calls: list[dict[str, object]] = []

    def fake_build(target: str, **kwargs: object) -> bool:
        calls.append({"target": target, **kwargs})
        return True

    monkeypatch.setattr("ft.cli._build_single_container_target", fake_build)

    result = runner.invoke(
        app,
        [
            "container",
            "build",
            "ubuntu",
            "--shell-config-source",
            "local",
            "--shell-config-local-dir",
            ".local/sources/custom-shell-config",
            "--no-cache",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "target": "ubuntu",
            "shell_config_source": "local",
            "shell_config_repo_url": "https://github.com/GrndZero101/shell-config.git",
            "shell_config_branch": "main",
            "shell_config_local_dir": ".local/sources/custom-shell-config",
            "shell_config_stage_from": None,
            "no_cache": True,
        }
    ]


def test_container_status_defaults_to_all_targets(monkeypatch: object) -> None:
    """Status should render both known targets when no selector is provided."""
    calls: list[list[str]] = []

    def fake_render(targets: list[str]) -> None:
        calls.append(targets)

    monkeypatch.setattr("ft.cli._render_container_status", fake_render)

    result = runner.invoke(app, ["container", "status"])

    assert result.exit_code == 0
    assert calls == [["ubuntu", "alpine"]]


def test_stage_local_shell_config_excludes_runtime_junk(tmp_path: Path) -> None:
    """Local shell-config staging should avoid copying host runtime state."""
    source = tmp_path / "shell-config"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "csm").write_text("#!/bin/sh\n", encoding="utf-8")
    (source / ".zsh_history").write_text("echo nope\n", encoding="utf-8")
    (source / ".cache").mkdir()
    (source / ".cache" / "temp").write_text("cache\n", encoding="utf-8")
    (source / "README.md").write_text("hello\n", encoding="utf-8")
    destination = tmp_path / "staged"

    staged_path = _stage_local_shell_config(source, destination)

    assert staged_path == destination
    assert (destination / "README.md").is_file()
    assert not (destination / ".zsh_history").exists()
    assert not (destination / ".cache").exists()


def test_container_up_runs_for_wildcard_target(monkeypatch: object) -> None:
    """Up should iterate every target selected by the resolver."""
    calls: list[str] = []

    def fake_up(target: str) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._up_single_container_target", fake_up)

    result = runner.invoke(app, ["container", "up", "*"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine"]


def test_container_up_ubuntu_enables_ssh_with_managed_key_mount(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Ubuntu disposable targets should publish SSH and mount the managed key."""
    commands: list[list[str]] = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    public_key_path = _container_host_ssh_public_key_path("ubuntu")
    assert public_key_path is not None
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.write_text(
        "ssh-ed25519 AAAATEST dev-fortress-ubuntu\n", encoding="utf-8"
    )

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:4] == [
            "docker",
            "image",
            "inspect",
            "dev-container-fortress:ubuntu-test",
        ]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[:4] == [
            "docker",
            "container",
            "inspect",
            "dev-fortress-ubuntu-test",
        ]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command[:3] == ["docker", "run", "--detach"]:
            return subprocess.CompletedProcess(command, 0, stdout="cid\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    assert _up_single_container_target("ubuntu") is True
    run_command = commands[-1]
    assert "--publish" in run_command
    assert "127.0.0.1:2222:2222" in run_command
    assert "--volume" in run_command
    assert f"{public_key_path}:/tmp/dev-fortress-authorized-key:ro" in run_command
    assert run_command[-4:] == [
        "sudo",
        "/usr/local/bin/start-test-target",
        "sshd",
        "/tmp/dev-fortress-authorized-key",
    ]


def test_container_up_alpine_enables_ssh_entrypoint(monkeypatch: object) -> None:
    """Alpine disposable targets should now use the SSH-oriented entrypoint."""
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:4] == [
            "docker",
            "image",
            "inspect",
            "dev-container-fortress:alpine-test",
        ]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[:4] == [
            "docker",
            "container",
            "inspect",
            "dev-fortress-alpine-test",
        ]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command[:3] == ["docker", "run", "--detach"]:
            return subprocess.CompletedProcess(command, 0, stdout="cid\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    assert _up_single_container_target("alpine") is True
    run_command = commands[-1]
    assert run_command[-4:] == [
        "sudo",
        "/usr/local/bin/start-test-target",
        "sshd",
        "/tmp/dev-fortress-authorized-key",
    ]


def test_container_down_runs_for_all_targets(monkeypatch: object) -> None:
    """Down should iterate every target selected by the resolver."""
    calls: list[str] = []

    def fake_down(target: str) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._down_single_container_target", fake_down)

    result = runner.invoke(app, ["container", "down", "all"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine"]


def test_container_reset_runs_for_wildcard_target(monkeypatch: object) -> None:
    """Reset should iterate every target selected by the resolver."""
    calls: list[str] = []

    def fake_reset(target: str) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._reset_single_container_target", fake_reset)

    result = runner.invoke(app, ["container", "reset", "*"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine"]


def test_container_logs_runs_for_single_target(monkeypatch: object) -> None:
    """Logs should resolve one target and delegate to the interactive helper."""
    calls: list[str] = []

    def fake_logs(target: str) -> int:
        calls.append(target)
        return 0

    monkeypatch.setattr("ft.cli._logs_single_container_target", fake_logs)

    result = runner.invoke(app, ["container", "logs", "ubuntu"])

    assert result.exit_code == 0
    assert calls == ["ubuntu"]


def test_container_exec_passes_command_arguments(monkeypatch: object) -> None:
    """Exec should pass through the requested command arguments unchanged."""
    calls: list[tuple[str, list[str]]] = []

    def fake_exec(target: str, command: list[str]) -> int:
        calls.append((target, command))
        return 0

    monkeypatch.setattr("ft.cli._exec_single_container_target", fake_exec)

    result = runner.invoke(app, ["container", "exec", "ubuntu", "env", "TERM"])

    assert result.exit_code == 0
    assert calls == [("ubuntu", ["env", "TERM"])]


def test_container_shell_runs_for_single_target(monkeypatch: object) -> None:
    """Shell should resolve one target and delegate to the interactive helper."""
    calls: list[str] = []

    def fake_shell(target: str) -> int:
        calls.append(target)
        return 0

    monkeypatch.setattr("ft.cli._shell_single_container_target", fake_shell)

    result = runner.invoke(app, ["container", "shell", "alpine"])

    assert result.exit_code == 0
    assert calls == ["alpine"]


def test_container_refresh_runs_for_single_target(monkeypatch: object) -> None:
    """Refresh should resolve one target and delegate to the chained helper."""
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_refresh(target: str, **kwargs: object) -> bool:
        calls.append((target, kwargs))
        return True

    monkeypatch.setattr("ft.cli._refresh_single_container_target", fake_refresh)

    result = runner.invoke(app, ["container", "refresh", "ubuntu"])

    assert result.exit_code == 0
    assert calls == [
        (
            "ubuntu",
            {
                "shell_config_source": "github",
                "shell_config_repo_url": "https://github.com/GrndZero101/shell-config.git",
                "shell_config_branch": "main",
                "shell_config_local_dir": None,
                "shell_config_stage_from": None,
                "no_cache": False,
            },
        )
    ]


def test_container_enter_runs_for_single_target(monkeypatch: object) -> None:
    """Enter should resolve one target and delegate to the chained helper."""
    calls: list[str] = []

    def fake_enter(target: str) -> int:
        calls.append(target)
        return 0

    monkeypatch.setattr("ft.cli._enter_single_container_target", fake_enter)

    result = runner.invoke(app, ["container", "enter", "alpine"])

    assert result.exit_code == 0
    assert calls == ["alpine"]


def test_effective_install_root_falls_back_to_user_local(monkeypatch: object) -> None:
    """A non-writable default install root should fall back to ~/.local/bin."""
    monkeypatch.setattr("ft.cli._is_writable_directory", lambda path: False)
    monkeypatch.setattr(Path, "home", lambda: Path("/tmp/test-home"))

    install_root = _effective_install_root(Path("/usr/local/bin"), None)

    assert install_root == Path("/tmp/test-home/.local/bin")


def test_install_tool_from_local_artifacts(tmp_path: Path) -> None:
    """The installer should extract, verify, and install a local tarball."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    binary_path = source_dir / "demo-tool"
    binary_path.write_text(
        "#!/bin/sh\necho demo-tool version 1.0.0\n", encoding="utf-8"
    )
    binary_path.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname="demo-tool")

    checksum_path = tmp_path / "checksums.txt"
    checksum_path.write_text(
        f"{_sha256(archive_path)}  demo-tool.tar.gz\n",
        encoding="utf-8",
    )

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "bin",
        healthcheck=["demo-tool", "version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    installed_path = install_tool(
        plan, healthcheck=True, cache_root=tmp_path / "download-cache"
    )

    assert installed_path.exists()
    assert installed_path.read_text(encoding="utf-8").startswith("#!/bin/sh")


def test_install_tool_accepts_digest_only_checksum_files(tmp_path: Path) -> None:
    """Digest-only checksum files should verify successfully for single-asset releases."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    binary_path = source_dir / "demo-tool"
    binary_path.write_text(
        "#!/bin/sh\necho demo-tool version 1.0.0\n", encoding="utf-8"
    )
    binary_path.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname="demo-tool")

    checksum_path = tmp_path / "demo-tool.tar.gz.sha256"
    checksum_path.write_text(f"{_sha256(archive_path)}\n", encoding="utf-8")

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "bin",
        healthcheck=["demo-tool", "version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    installed_path = install_tool(
        plan, healthcheck=True, cache_root=tmp_path / "download-cache"
    )

    assert installed_path.exists()
    assert installed_path.name == "demo-tool"


def test_install_tool_preserves_support_directories(tmp_path: Path) -> None:
    """Archive installs should carry required support trees next to the bin root."""
    source_root = tmp_path / "source" / "demo-tool-1.0.0"
    bin_dir = source_root / "bin"
    libexec_dir = source_root / "libexec" / "demo-tool"
    libexec_dir.mkdir(parents=True)
    bin_dir.mkdir(parents=True)

    support_binary = libexec_dir / "demo-tool"
    support_binary.write_text(
        "#!/bin/sh\necho demo-tool version 1.0.0\n", encoding="utf-8"
    )
    support_binary.chmod(0o755)

    launcher = bin_dir / "demo-tool"
    launcher.write_text(
        "#!/bin/sh\nexec \"$(dirname \"$0\")/../libexec/demo-tool/demo-tool\" \"$@\"\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_root, arcname="demo-tool-1.0.0")

    checksum_path = tmp_path / "checksums.txt"
    checksum_path.write_text(
        f"{_sha256(archive_path)}  demo-tool.tar.gz\n",
        encoding="utf-8",
    )

    install_root = tmp_path / "prefix" / "bin"
    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=install_root,
        healthcheck=["demo-tool", "--version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool-1.0.0/bin/demo-tool",
                support_paths=["demo-tool-1.0.0/libexec"],
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    installed_path = install_tool(
        plan, healthcheck=True, cache_root=tmp_path / "download-cache"
    )

    assert installed_path.exists()
    assert (install_root.parent / "libexec" / "demo-tool" / "demo-tool").exists()


def test_install_tool_merges_support_directories_without_replacing_existing_data(
    tmp_path: Path,
) -> None:
    """Support directories should merge into the install prefix instead of replacing it."""
    source_root = tmp_path / "source" / "nvim-linux-x86_64"
    bin_dir = source_root / "bin"
    runtime_share = source_root / "share" / "nvim"
    runtime_lib = source_root / "lib" / "nvim"
    runtime_share.mkdir(parents=True)
    runtime_lib.mkdir(parents=True)
    bin_dir.mkdir(parents=True)

    launcher = bin_dir / "nvim"
    launcher.write_text("#!/bin/sh\necho NVIM v0.test\n", encoding="utf-8")
    launcher.chmod(0o755)
    (runtime_share / "runtime.txt").write_text("runtime\n", encoding="utf-8")
    (runtime_lib / "libnvim.so").write_text("binary\n", encoding="utf-8")

    archive_path = tmp_path / "nvim.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_root, arcname="nvim-linux-x86_64")

    checksum_path = tmp_path / "checksums.txt"
    checksum_path.write_text(
        f"{_sha256(archive_path)}  nvim.tar.gz\n",
        encoding="utf-8",
    )

    install_root = tmp_path / "prefix" / "bin"
    existing_manifest = (
        install_root.parent / "share" / "dev-container-fortress" / "marker.txt"
    )
    existing_manifest.parent.mkdir(parents=True, exist_ok=True)
    existing_manifest.write_text("keep me\n", encoding="utf-8")

    tool = ToolDefinition(
        description="Demo nvim",
        version="0.test",
        install_root=install_root,
        healthcheck=["nvim", "--version"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="nvim-linux-x86_64/bin/nvim",
                support_paths=["nvim-linux-x86_64/lib", "nvim-linux-x86_64/share"],
                checksum_asset="nvim.tar.gz",
            )
        ],
    )
    plan = build_plan(
        "neovim", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    installed_path = install_tool(
        plan, healthcheck=True, cache_root=tmp_path / "download-cache"
    )

    assert installed_path.exists()
    assert existing_manifest.exists()
    assert (install_root.parent / "share" / "nvim" / "runtime.txt").exists()
    assert (install_root.parent / "lib" / "nvim" / "libnvim.so").exists()


def test_install_tool_reuses_cached_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verified cached assets should be reused without redownloading."""
    source_root = tmp_path / "source" / "demo-tool-1.0.0"
    source_root.mkdir(parents=True)
    binary_path = source_root / "demo-tool"
    binary_path.write_text("#!/bin/sh\necho demo-tool 1.0.0\n", encoding="utf-8")
    binary_path.chmod(0o755)

    archive_path = tmp_path / "demo-tool.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(binary_path, arcname="demo-tool")

    checksum_path = tmp_path / "checksums.txt"
    checksum_path.write_text(
        f"{_sha256(archive_path)}  demo-tool.tar.gz\n",
        encoding="utf-8",
    )

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "prefix" / "bin",
        healthcheck=["demo-tool"],
        integrity=IntegrityConfig(checksum_url=checksum_path.as_uri()),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                url=archive_path.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
                checksum_asset="demo-tool.tar.gz",
            )
        ],
    )
    plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    download_calls: list[str] = []

    def _download_recorder(url: str, destination: Path) -> None:
        download_calls.append(url)
        shutil.copy2(Path(url.removeprefix("file://")), destination)

    monkeypatch.setattr("ft.installer._download", _download_recorder)
    cache_root = tmp_path / "cache"

    first_install_root = tmp_path / "prefix-one" / "bin"
    second_install_root = tmp_path / "prefix-two" / "bin"
    install_tool(
        plan,
        install_root=first_install_root,
        healthcheck=True,
        cache_root=cache_root,
    )
    install_tool(
        plan,
        install_root=second_install_root,
        healthcheck=True,
        cache_root=cache_root,
    )

    assert sorted(download_calls) == sorted([archive_path.as_uri(), checksum_path.as_uri()])
    assert (second_install_root / "demo-tool").exists()


def test_install_tool_cache_key_separates_target_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache entries should diverge when target-scoped assets change."""
    ubuntu_asset = tmp_path / "demo-ubuntu.tar.gz"
    alpine_asset = tmp_path / "demo-alpine.tar.gz"
    for asset_path, message in (
        (ubuntu_asset, "ubuntu"),
        (alpine_asset, "alpine"),
    ):
        source = tmp_path / f"{message}.sh"
        source.write_text(f"#!/bin/sh\necho {message}\n", encoding="utf-8")
        source.chmod(0o755)
        with tarfile.open(asset_path, "w:gz") as archive:
            archive.add(source, arcname="demo-tool")

    monkeypatch.setattr(
        "ft.installer._download",
        lambda url, destination: shutil.copy2(Path(url.removeprefix("file://")), destination),
    )

    tool = ToolDefinition(
        description="Demo tool",
        version="1.0.0",
        install_root=tmp_path / "prefix" / "bin",
        healthcheck=["demo-tool"],
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                target="ubuntu",
                url=ubuntu_asset.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
            ),
            ToolAsset(
                os="linux",
                arch="amd64",
                target="alpine",
                url=alpine_asset.as_uri(),
                archive="tar.gz",
                binary_path="demo-tool",
            ),
        ],
    )

    cache_root = tmp_path / "cache"
    ubuntu_plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )
    alpine_plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="alpine"
    )

    install_tool(
        ubuntu_plan,
        install_root=tmp_path / "ubuntu" / "bin",
        healthcheck=True,
        cache_root=cache_root,
    )
    install_tool(
        alpine_plan,
        install_root=tmp_path / "alpine" / "bin",
        healthcheck=True,
        cache_root=cache_root,
    )

    assert (cache_root / "demo-tool" / "ubuntu" / "linux" / "amd64" / "1.0.0").exists()
    assert (cache_root / "demo-tool" / "alpine" / "linux" / "amd64" / "1.0.0").exists()


def test_build_plan_renders_template_variables() -> None:
    """Plan building should render asset and integrity templates from variables."""
    tool = ToolDefinition(
        description="Demo tool",
        version="1.2.3",
        install_root=Path("/usr/local/bin"),
        variables={"github_repo": "example/demo", "release_tag": "v1.2.3"},
        integrity=IntegrityConfig(
            checksum_url_template=(
                "https://github.com/{github_repo}/releases/download/{release_tag}/{filename}.sha256"
            )
        ),
        assets=[
            ToolAsset(
                os="linux",
                arch="amd64",
                filename="demo-tool-linux-amd64.tar.gz",
                url_template=(
                    "https://github.com/{github_repo}/releases/download/{release_tag}/{filename}"
                ),
                archive="tar.gz",
                binary_path="demo-tool",
            )
        ],
    )

    plan = build_plan(
        "demo-tool", tool, os_name="linux", architecture="amd64", target="ubuntu"
    )

    assert plan.asset.url.endswith("/demo-tool-linux-amd64.tar.gz")
    assert plan.asset.checksum_asset == "demo-tool-linux-amd64.tar.gz"
    assert plan.integrity.checksum_url.endswith("/demo-tool-linux-amd64.tar.gz.sha256")


def _sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a local file."""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
