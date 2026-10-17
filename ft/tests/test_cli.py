"""CLI and installer tests for ft."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tarfile
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import typer
from ft.cli import (
    _container_host_ssh_public_key_path,
    _default_windows_ssh_dir,
    _deploy_rsync_command,
    _effective_install_root,
    _ensure_container_target_running,
    _host_target_manifest_toml,
    _host_zsh_text,
    _last_non_empty_line,
    _parse_ansible_play_recap,
    _require_supported_container_architecture,
    _resolve_container_targets,
    _resolve_host_targets,
    _resolve_single_container_target,
    _stage_local_shell_config,
    _up_single_container_target,
    _upsert_host_targets,
    _windows_openssh_path,
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
from typer.testing import CliRunner

runner = CliRunner()

# Spot price history fixtures must sit inside the selector's lookback window,
# which is measured back from the real current time.
_SPOT_HISTORY_T1 = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
_SPOT_HISTORY_T0 = _SPOT_HISTORY_T1 - timedelta(hours=1)


@pytest.fixture(autouse=True)
def _pin_host_architecture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin host architecture so target fan-out does not depend on the test host."""
    monkeypatch.setattr("ft.cli.detect_architecture", lambda: "amd64")


def _load_spot_select_module() -> object:
    """Load the stack-local capacity selector module for focused tests."""
    module_path = (
        Path(__file__).parents[2] / "infra" / "aws-disposable-ubuntu" / "spot_select.py"
    )
    spec = importlib.util.spec_from_file_location(
        "aws_disposable_spot_select", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _aws_price_list(hourly_price: str, instance_type: str = "t4g.medium") -> list[str]:
    """Return one minimal AWS Pricing API PriceList payload."""
    return [
        json.dumps(
            {
                "product": {
                    "attributes": {
                        "instanceType": instance_type,
                    }
                },
                "terms": {
                    "OnDemand": {
                        "test-term": {
                            "priceDimensions": {
                                "test-dimension": {
                                    "pricePerUnit": {"USD": hourly_price}
                                }
                            }
                        }
                    }
                },
            }
        )
    ]


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
    assert "ssh-config" in result.stdout
    assert "ssh-key" in result.stdout
    assert "ssh-key-enroll" in result.stdout
    assert "ssh" in result.stdout
    assert "secrets" in result.stdout
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


def test_workspace_secrets_group_uses_help_when_no_args_are_passed() -> None:
    """Workspace secrets subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["workspace", "secrets"])

    assert result.exit_code == 0
    assert "Bootstrap and inspect disposable secrets state" in result.stdout
    assert "init-test" in result.stdout


def test_host_secrets_group_uses_help_when_no_args_are_passed() -> None:
    """Host secrets subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["host", "secrets"])

    assert result.exit_code == 0
    assert "Validate host-side GPG and pass readiness" in result.stdout
    assert "validate" in result.stdout


def test_infra_group_uses_help_when_no_args_are_passed() -> None:
    """Infra subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["infra"])

    assert result.exit_code == 0
    assert "Run thin Terraform-backed infrastructure workflows" in result.stdout
    assert "aws-disposable-ubuntu" in result.stdout


def test_deploy_group_uses_help_when_no_args_are_passed() -> None:
    """Deploy subcommands should show help on empty invocation."""
    result = runner.invoke(app, ["deploy"])

    assert result.exit_code == 0
    assert "Prepare remote Dev Fortress development hosts" in result.stdout
    assert "init" in result.stdout
    assert "sync" in result.stdout
    assert "exec" in result.stdout


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


def test_infra_aws_disposable_ubuntu_capacity_select_wraps_stack_script(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Capacity select should delegate to the stack-local selector script."""
    calls: list[list[str]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._default_disposable_ubuntu_capacity_presets_dir",
        lambda: tmp_path / "capacity-presets",
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
        [
            "infra",
            "aws-disposable-ubuntu",
            "capacity",
            "select",
            "--market",
            "on-demand",
            "--region",
            "ap-southeast-1",
            "--instance-type",
            "t4g.medium",
            "--exclude-families",
            "t*",
            "--sort-by",
            "discount",
            "--max-vcpu",
            "8",
            "--max-memory-gib",
            "32",
            "--max-on-demand-hourly",
            "1.25",
            "--no-cache",
            "--no-progress",
            "--tfvars-path",
            str(tmp_path / "capacity.auto.tfvars.json"),
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0][1].endswith("spot_select.py")
    assert "--market" in calls[0]
    assert calls[0][calls[0].index("--market") + 1] == "on-demand"
    assert "--write-tfvars" in calls[0]
    assert calls[0][calls[0].index("--instance-type") + 1] == "t4g.medium"
    assert calls[0][calls[0].index("--exclude-families") + 1] == "t*"
    assert calls[0][calls[0].index("--sort-by") + 1] == "discount"
    assert calls[0][calls[0].index("--max-vcpu") + 1] == "8"
    assert calls[0][calls[0].index("--max-memory-gib") + 1] == "32.0"
    assert calls[0][calls[0].index("--max-on-demand-hourly") + 1] == "1.25"
    assert calls[0][calls[0].index("--lookback-hours") + 1] == "168"
    assert "--no-cache" in calls[0]
    assert "--no-progress" in calls[0]
    assert (tmp_path / "capacity-presets" / "last.json").is_file()


def test_capacity_select_without_selection_options_does_not_update_last(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Operational options alone should not update the special last preset."""
    calls: list[list[str]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._default_disposable_ubuntu_capacity_presets_dir",
        lambda: tmp_path / "capacity-presets",
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
        [
            "infra",
            "aws-disposable-ubuntu",
            "capacity",
            "select",
            "--no-cache",
            "--no-progress",
            "--no-write-tfvars",
            "--workers",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert calls
    assert not (tmp_path / "capacity-presets" / "last.json").exists()


def test_capacity_select_saves_named_preset(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Capacity select should save effective selector inputs as a named preset."""
    calls: list[list[str]] = []

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._default_disposable_ubuntu_capacity_presets_dir",
        lambda: tmp_path / "capacity-presets",
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
        [
            "infra",
            "aws-disposable-ubuntu",
            "capacity",
            "select",
            "--market",
            "spot",
            "--architecture",
            "arm64",
            "--min-vcpu",
            "2",
            "--min-memory-gib",
            "8",
            "--max-spot-monthly",
            "50",
            "--exclude-families",
            "t*",
            "--sort-by",
            "discount",
            "--save-preset",
            "cheap-dev",
            "--no-progress",
            "--no-write-tfvars",
        ],
    )

    assert result.exit_code == 0
    assert calls
    preset = json.loads(
        (tmp_path / "capacity-presets" / "cheap-dev.json").read_text(encoding="utf-8")
    )
    last = json.loads(
        (tmp_path / "capacity-presets" / "last.json").read_text(encoding="utf-8")
    )
    assert preset["architecture"] == "arm64"
    assert preset["min_memory_gib"] == 8.0
    assert preset["max_spot_monthly"] == 50.0
    assert preset["exclude_families"] == "t*"
    assert preset["sort_by"] == "discount"
    assert preset == last


def test_capacity_select_loads_preset_and_applies_cli_overrides(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Explicit CLI options should override loaded capacity preset values."""
    calls: list[list[str]] = []
    presets_dir = tmp_path / "capacity-presets"
    presets_dir.mkdir()
    (presets_dir / "cheap-dev.json").write_text(
        json.dumps(
            {
                "market": "spot",
                "region": "ap-southeast-1",
                "architecture": "arm64",
                "min_vcpu": 2,
                "min_memory_gib": 8.0,
                "max_vcpu": 8,
                "max_memory_gib": 32.0,
                "max_on_demand_hourly": None,
                "families": None,
                "exclude_families": "t*",
                "instance_type": None,
                "lookback_hours": 168,
                "min_samples": 2,
                "max_hourly_price": None,
                "max_spot_monthly": 50.0,
                "sort_by": "discount",
                "volatility_weight": 2.0,
                "top": 10,
                "spot_history_fresh_ttl_minutes": 15.0,
                "include_previous_generation": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._default_disposable_ubuntu_capacity_presets_dir",
        lambda: presets_dir,
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
        [
            "infra",
            "aws-disposable-ubuntu",
            "capacity",
            "select",
            "--load-preset",
            "cheap-dev",
            "--max-spot-monthly",
            "80",
            "--sort-by",
            "score",
            "--no-progress",
            "--no-write-tfvars",
        ],
    )

    assert result.exit_code == 0
    command = calls[0]
    assert command[command.index("--architecture") + 1] == "arm64"
    assert command[command.index("--min-memory-gib") + 1] == "8.0"
    assert command[command.index("--max-spot-monthly") + 1] == "80.0"
    assert command[command.index("--sort-by") + 1] == "score"
    last = json.loads((presets_dir / "last.json").read_text(encoding="utf-8"))
    assert last["max_spot_monthly"] == 80.0
    assert last["sort_by"] == "score"


def test_capacity_select_last_loads_last_preset(
    tmp_path: Path, monkeypatch: object
) -> None:
    """--last should load the special last capacity preset."""
    calls: list[list[str]] = []
    presets_dir = tmp_path / "capacity-presets"
    presets_dir.mkdir()
    (presets_dir / "last.json").write_text(
        json.dumps(
            {
                "market": "on-demand",
                "region": "ap-southeast-1",
                "architecture": None,
                "min_vcpu": 2,
                "min_memory_gib": 4.0,
                "max_vcpu": None,
                "max_memory_gib": None,
                "max_on_demand_hourly": None,
                "families": None,
                "exclude_families": "",
                "instance_type": "t4g.medium",
                "lookback_hours": 168,
                "min_samples": 2,
                "max_hourly_price": None,
                "max_spot_monthly": None,
                "sort_by": "score",
                "volatility_weight": 2.0,
                "top": 10,
                "spot_history_fresh_ttl_minutes": 15.0,
                "include_previous_generation": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._default_disposable_ubuntu_capacity_presets_dir",
        lambda: presets_dir,
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
        [
            "infra",
            "aws-disposable-ubuntu",
            "capacity",
            "select",
            "--last",
            "--no-progress",
            "--no-write-tfvars",
        ],
    )

    assert result.exit_code == 0
    command = calls[0]
    assert command[command.index("--market") + 1] == "on-demand"
    assert command[command.index("--instance-type") + 1] == "t4g.medium"


def test_spot_selector_defaults_to_one_week_lookback() -> None:
    """Spot selector default lookback should cover one week of history."""
    module = _load_spot_select_module()

    args = module.build_parser().parse_args([])

    assert args.lookback_hours == 168


def test_spot_selector_ranks_spot_candidates(monkeypatch: object) -> None:
    """Stack-local selector should rank spot candidates and emit Terraform inputs."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "t4g.small",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 2048},
                    },
                    {
                        "InstanceType": "t4g.medium",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 4096},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    },
                    {
                        "AvailabilityZone": "ap-southeast-1b",
                        "SubnetId": "subnet-b",
                    },
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.020")}
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": "t4g.medium",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.010",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": "t4g.medium",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.011",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                    {
                        "InstanceType": "t4g.medium",
                        "AvailabilityZone": "ap-southeast-1b",
                        "SpotPrice": "0.007",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": "t4g.medium",
                        "AvailabilityZone": "ap-southeast-1b",
                        "SpotPrice": "0.008",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--region",
            "ap-southeast-1",
            "--architecture",
            "arm64",
            "--min-vcpu",
            "2",
            "--min-memory-gib",
            "4",
            "--families",
            "t4g",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["selected"]["instance_type"] == "t4g.medium"
    assert payload["selected"]["availability_zone"] == "ap-southeast-1b"
    assert payload["selected"]["on_demand_price"] == 0.02
    assert payload["selected"]["spot_savings_per_hour"] == pytest.approx(0.012)
    assert payload["selected"]["spot_discount_pct"] == pytest.approx(60.0)
    assert payload["terraform_tfvars"] == {
        "architecture": "arm64",
        "enable_spot": True,
        "instance_type": "t4g.medium",
        "spot_max_price": "0.00880",
        "subnet_id": "subnet-b",
    }


def test_spot_selector_excludes_families(monkeypatch: object) -> None:
    """Family exclusions should subtract from the candidate set."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "t4g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "m7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.100")}
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": "m7g.large",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.040",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": "m7g.large",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.041",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--families",
            "t*,m*",
            "--exclude-families",
            "t*",
            "--min-memory-gib",
            "8",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["selected"]["instance_type"] == "m7g.large"
    assert all(candidate["family"] != "t4g" for candidate in payload["candidates"])


def test_spot_selector_includes_family_patterns(monkeypatch: object) -> None:
    """Family allow-lists should support fnmatch patterns."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "m7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "r7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 16384},
                    },
                    {
                        "InstanceType": "c7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 4096},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.100")}
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            instance_type = args[args.index("--instance-types") + 1]
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.040",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.041",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--families",
            "m*,r*",
            "--min-memory-gib",
            "8",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert {candidate["family"] for candidate in payload["candidates"]} == {
        "m7g",
        "r7g",
    }


def test_spot_selector_can_sort_by_discount(monkeypatch: object) -> None:
    """Discount sorting should choose the highest percentage discount candidate."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "t4g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "m7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {
                "PriceList": [
                    *_aws_price_list("0.020", "t4g.large"),
                    *_aws_price_list("0.200", "m7g.large"),
                ]
            }
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            instance_type = args[args.index("--instance-types") + 1]
            spot_price = "0.010" if instance_type == "t4g.large" else "0.040"
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": spot_price,
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": spot_price,
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--families",
            "t4g,m7g",
            "--min-memory-gib",
            "8",
            "--sort-by",
            "discount",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["selected"]["instance_type"] == "m7g.large"
    assert payload["selected"]["spot_discount_pct"] == pytest.approx(80.0)


def test_spot_selector_applies_size_and_price_ceilings(monkeypatch: object) -> None:
    """Maximum ceilings should remove oversized or over-budget candidates."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "m7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "m7g.2xlarge",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 8},
                        "MemoryInfo": {"SizeInMiB": 32768},
                    },
                    {
                        "InstanceType": "r7g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 16384},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {
                "PriceList": [
                    *_aws_price_list("0.080", "m7g.large"),
                    *_aws_price_list("0.300", "m7g.2xlarge"),
                    *_aws_price_list("0.200", "r7g.large"),
                ]
            }
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            instance_type = args[args.index("--instance-types") + 1]
            spot_price = "0.080" if instance_type == "r7g.large" else "0.040"
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": spot_price,
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": spot_price,
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--families",
            "m*,r*",
            "--min-memory-gib",
            "8",
            "--max-vcpu",
            "4",
            "--max-memory-gib",
            "16",
            "--max-on-demand-hourly",
            "0.25",
            "--max-spot-monthly",
            "35",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["selected"]["instance_type"] == "m7g.large"
    assert {candidate["instance_type"] for candidate in payload["candidates"]} == {
        "m7g.large"
    }
    assert payload["requested"]["max_spot_monthly"] == 35.0


def test_spot_selector_uses_x86_defaults_for_amd64(monkeypatch: object) -> None:
    """amd64 should use x86 default families instead of ARM families."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "m7i.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["x86_64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "t4g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.120")}
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            assert "m7i.large" in args
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": "m7i.large",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.050",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": "m7i.large",
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.051",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--architecture",
            "amd64",
            "--min-memory-gib",
            "8",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["requested"]["architecture"] == "amd64"
    assert "m7i" in payload["requested"]["families"]
    assert payload["selected"]["instance_type"] == "m7i.large"
    assert payload["terraform_tfvars"]["architecture"] == "amd64"


def test_spot_selector_without_architecture_uses_all_families(
    monkeypatch: object,
) -> None:
    """Omitting architecture should not apply an implicit family allow-list."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            assert not any(
                str(arg).startswith("Name=processor-info.supported-architecture")
                for arg in args
            )
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "m7i.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["x86_64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                    {
                        "InstanceType": "t4g.large",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 8192},
                    },
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.120")}
        if args[:2] == ["ec2", "describe-spot-price-history"]:
            instance_type = args[args.index("--instance-types") + 1]
            return {
                "SpotPriceHistory": [
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.050",
                        "Timestamp": _SPOT_HISTORY_T0.isoformat(),
                    },
                    {
                        "InstanceType": instance_type,
                        "AvailabilityZone": "ap-southeast-1a",
                        "SpotPrice": "0.051",
                        "Timestamp": _SPOT_HISTORY_T1.isoformat(),
                    },
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "spot",
            "--min-memory-gib",
            "8",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["requested"]["architecture"] is None
    assert payload["requested"]["families"] == []
    assert {candidate["instance_type"] for candidate in payload["candidates"]} == {
        "m7i.large",
        "t4g.large",
    }


def test_spot_selector_reuses_cached_metadata(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Cacheable metadata should be reused across selector runs."""
    module = _load_spot_select_module()
    call_counts: dict[tuple[str, str], int] = {}

    def count(args: list[str]) -> None:
        key = (args[0], args[1])
        call_counts[key] = call_counts.get(key, 0) + 1

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        count(args)
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "t4g.medium",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 4096},
                    }
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.040")}
        if args[:2] == ["ec2", "describe-instance-type-offerings"]:
            return {
                "InstanceTypeOfferings": [
                    {
                        "InstanceType": "t4g.medium",
                        "Location": "ap-southeast-1a",
                    }
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    argv = [
        "--market",
        "on-demand",
        "--cache-root",
        str(tmp_path / "cache"),
    ]

    module.select_capacity(module.build_parser().parse_args(argv))
    module.select_capacity(module.build_parser().parse_args(argv))

    assert call_counts[("ec2", "describe-instance-types")] == 1
    assert call_counts[("ec2", "describe-vpcs")] == 1
    assert call_counts[("ec2", "describe-subnets")] == 1
    assert call_counts[("pricing", "get-products")] == 1
    assert call_counts[("ec2", "describe-instance-type-offerings")] == 1


def test_spot_selector_can_emit_on_demand_tfvars(monkeypatch: object) -> None:
    """On-demand mode should disable Spot while preserving selected host shape."""
    module = _load_spot_select_module()

    def fake_run_aws(region: str, args: list[str]) -> dict[str, object]:
        if args[:2] == ["ec2", "describe-instance-types"]:
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": "t4g.medium",
                        "ProcessorInfo": {"SupportedArchitectures": ["arm64"]},
                        "VCpuInfo": {"DefaultVCpus": 2},
                        "MemoryInfo": {"SizeInMiB": 4096},
                    }
                ]
            }
        if args[:2] == ["ec2", "describe-vpcs"]:
            return {"Vpcs": [{"VpcId": "vpc-123"}]}
        if args[:2] == ["ec2", "describe-subnets"]:
            return {
                "Subnets": [
                    {
                        "AvailabilityZone": "ap-southeast-1a",
                        "SubnetId": "subnet-a",
                    }
                ]
            }
        if args[:2] == ["pricing", "get-products"]:
            return {"PriceList": _aws_price_list("0.040")}
        if args[:2] == ["ec2", "describe-instance-type-offerings"]:
            return {
                "InstanceTypeOfferings": [
                    {
                        "InstanceType": "t4g.medium",
                        "Location": "ap-southeast-1a",
                    }
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_aws", fake_run_aws)
    args = module.build_parser().parse_args(
        [
            "--market",
            "on-demand",
            "--region",
            "ap-southeast-1",
            "--instance-type",
            "t4g.medium",
            "--no-cache",
        ]
    )

    payload = module.select_capacity(args)

    assert payload["selected"]["market"] == "on-demand"
    assert payload["selected"]["on_demand_price"] == 0.04
    assert payload["selected"]["on_demand_price_monthly"] == pytest.approx(29.22)
    assert payload["terraform_tfvars"] == {
        "architecture": "arm64",
        "enable_spot": False,
        "instance_type": "t4g.medium",
        "spot_max_price": None,
        "subnet_id": "subnet-a",
    }


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


def test_host_ssh_config_renders_vscode_compatible_block(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh-config should render an OpenSSH block for VS Code Remote SSH."""
    config_path = _write_host_config(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    result = runner.invoke(
        app,
        [
            "host",
            "ssh-config",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Host dev-fortress-ec2-dev" in result.stdout
    assert "HostName ec2.example.internal" in result.stdout
    assert "User ubuntu" in result.stdout
    assert "Port 22" in result.stdout
    assert "IdentitiesOnly yes" in result.stdout
    assert (
        str(
            tmp_path
            / "state"
            / "dev-container-fortress"
            / "ssh"
            / "dev-fortress-ec2-dev"
            / "dev_fortress_ed25519"
        )
        in result.stdout
    )
    assert (
        str(
            tmp_path
            / "state"
            / "dev-container-fortress"
            / "known_hosts"
            / "dev-fortress-ec2-dev"
        )
        in result.stdout
    )
    assert "StrictHostKeyChecking yes" in result.stdout


def test_host_ssh_config_installs_include_and_ensures_main_config(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host ssh-config should write one managed include and add one Include line."""
    config_path = _write_host_config(tmp_path)
    include_path = tmp_path / ".ssh" / "config.d" / "dev-container-fortress"
    ssh_config_path = tmp_path / ".ssh" / "config"
    ssh_config_path.parent.mkdir(parents=True)
    ssh_config_path.write_text(
        "Host dev-fortress-ec2-dev\n  HostName dev-fortress-ec2-dev\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    args = [
        "host",
        "ssh-config",
        "dev-fortress-ec2-dev",
        "--config",
        str(config_path),
        "--host-alias",
        "tboss-ec2",
        "--install",
        "--ensure-include",
        "--include-path",
        str(include_path),
        "--ssh-config-path",
        str(ssh_config_path),
    ]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    include_text = include_path.read_text(encoding="utf-8")
    ssh_config_text = ssh_config_path.read_text(encoding="utf-8")
    assert "Host tboss-ec2" in include_text
    assert "HostName ec2.example.internal" in include_text
    assert ssh_config_text.count(f"Include {include_path}") == 1
    assert ssh_config_text.startswith(f"Include {include_path}\n")


def test_host_ssh_config_windows_exports_material_and_uses_windows_paths(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Windows mode should export SSH material and render Windows OpenSSH paths."""
    config_path = _write_host_config(tmp_path)
    state_private_key_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "ssh"
        / "dev-fortress-ec2-dev"
        / "dev_fortress_ed25519"
    )
    state_private_key_path.parent.mkdir(parents=True, exist_ok=True)
    state_private_key_path.write_text("private", encoding="utf-8")
    state_private_key_path.with_name("dev_fortress_ed25519.pub").write_text(
        "public", encoding="utf-8"
    )
    state_known_hosts_path = (
        tmp_path
        / "state"
        / "dev-container-fortress"
        / "known_hosts"
        / "dev-fortress-ec2-dev"
    )
    state_known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
    state_known_hosts_path.write_text("known-host", encoding="utf-8")
    windows_ssh_dir = tmp_path / "mnt" / "c" / "Users" / "timl" / ".ssh"
    include_path = windows_ssh_dir / "config.d" / "dev-container-fortress"
    ssh_config_path = windows_ssh_dir / "config"
    ssh_config_path.parent.mkdir(parents=True)
    ssh_config_path.write_text(
        "Host dev-fortress-ec2-dev\n  HostName dev-fortress-ec2-dev\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    result = runner.invoke(
        app,
        [
            "host",
            "ssh-config",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
            "--windows",
            "--install",
            "--ensure-include",
            "--windows-ssh-dir",
            str(windows_ssh_dir),
        ],
    )

    assert result.exit_code == 0
    exported_key = (
        windows_ssh_dir
        / "dev-container-fortress"
        / "dev-fortress-ec2-dev"
        / "dev_fortress_ed25519"
    )
    exported_known_hosts = (
        windows_ssh_dir
        / "dev-container-fortress"
        / "known_hosts"
        / "dev-fortress-ec2-dev"
    )
    include_text = include_path.read_text(encoding="utf-8")
    ssh_config_text = ssh_config_path.read_text(encoding="utf-8")
    assert exported_key.read_text(encoding="utf-8") == "private"
    assert exported_key.with_suffix(".pub").read_text(encoding="utf-8") == "public"
    assert exported_known_hosts.read_text(encoding="utf-8") == "known-host"
    assert f"IdentityFile {_windows_openssh_path(exported_key)}" in include_text
    assert (
        f"UserKnownHostsFile {_windows_openssh_path(exported_known_hosts)}"
        in include_text
    )
    assert ssh_config_text.count(f"Include {_windows_openssh_path(include_path)}") == 1
    assert ssh_config_text.startswith(
        f"Include {_windows_openssh_path(include_path)}\n"
    )


def test_default_windows_ssh_dir_uses_windows_userprofile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows SSH dir detection should prefer the Windows USERPROFILE value."""
    monkeypatch.setenv("USERPROFILE", r"C:\Users\actual.windows")
    monkeypatch.setenv("USER", "wsl-user")
    monkeypatch.setattr("ft.cli._windows_userprofile_from_interop", lambda: None)

    assert _default_windows_ssh_dir() == Path("/mnt/c/Users/actual.windows/.ssh")


def test_default_windows_ssh_dir_uses_windows_interop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows SSH dir detection should query Windows when USERPROFILE is absent."""
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("USER", "wsl-user")
    monkeypatch.setattr(
        "ft.cli._windows_userprofile_from_interop",
        lambda: r"D:\Users\actual.windows",
    )

    assert _default_windows_ssh_dir() == Path("/mnt/d/Users/actual.windows/.ssh")


def test_default_windows_ssh_dir_does_not_guess_from_wsl_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows SSH dir detection should not guess from a potentially different WSL user."""
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("USER", "wsl-user")
    monkeypatch.setattr("ft.cli._windows_userprofile_from_interop", lambda: None)

    with pytest.raises(typer.BadParameter, match="--windows-ssh-dir"):
        _default_windows_ssh_dir()


def test_default_windows_ssh_dir_handles_interop_exec_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows SSH dir detection should tolerate unusable Windows interop commands."""
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "powershell.exe":
            raise OSError(8, "Exec format error", command[0])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=r"C:\Users\actual.windows" + "\n",
            stderr="",
        )

    monkeypatch.setattr("ft.cli.subprocess.run", fake_run)

    assert _default_windows_ssh_dir() == Path("/mnt/c/Users/actual.windows/.ssh")


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


def test_deploy_rsync_command_excludes_state_and_uses_managed_ssh(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy rsync command should avoid local state and reuse managed SSH."""
    config_path = _write_host_config(tmp_path)
    manifest = HostTargetManifest.model_validate(
        tomllib.loads(config_path.read_text(encoding="utf-8"))
    )
    target = next(
        item for item in manifest.targets if item.name == "dev-fortress-ec2-dev"
    )
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._refresh_managed_known_host",
        lambda target: tmp_path / "known_hosts",
    )

    command = _deploy_rsync_command(
        source=tmp_path / "dev-container-fortress",
        target=target,
        remote_path="~/workspaces/dev-fortress/dev-container-fortress",
        dry_run=True,
        delete=True,
    )

    assert command[:4] == ["rsync", "-az", "--human-readable", "--itemize-changes"]
    assert "--dry-run" in command
    assert "--delete" in command
    assert ".git" in command
    assert ".venv" in command
    assert ".terraform" in command
    assert "-e" in command
    assert str(private_key_path) in command[command.index("-e") + 1]
    assert command[-1] == (
        "ubuntu@ec2.example.internal:~/workspaces/dev-fortress/dev-container-fortress/"
    )


def test_deploy_init_clones_dev_and_shell_config(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy init should clone or update remote Git checkouts."""
    config_path = _write_host_config(tmp_path)
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
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
        [
            "deploy",
            "init",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 3
    assert calls[0][0] == "ssh"
    assert calls[0][-1] == "mkdir -p -- ~/workspaces/tboss"
    assert calls[1][0] == "ssh"
    assert "git clone --branch main" in calls[1][-1]
    assert "dev-container-fortress.git" in calls[1][-1]
    assert "~/workspaces/tboss/dev-container-fortress" in calls[1][-1]
    assert calls[2][0] == "ssh"
    assert "git clone --branch main" in calls[2][-1]
    assert "shell-config.git" in calls[2][-1]
    assert "~/workspaces/tboss/shell-config" in calls[2][-1]
    assert "initialized dev-fortress-ec2-dev -> ~/workspaces/tboss" in result.stdout


def test_deploy_init_supports_workspace_parent_override(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy init should support a custom remote workspace parent."""
    config_path = _write_host_config(tmp_path)
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
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
        [
            "deploy",
            "init",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
            "--workspace-parent",
            "~/workspaces/custom",
            "--skip-shell-config",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 2
    assert calls[0][-1] == "mkdir -p -- ~/workspaces/custom"
    assert "~/workspaces/custom/dev-container-fortress" in calls[1][-1]
    assert "shell-config" not in calls[1][-1]


def test_deploy_sync_mirrors_dev_and_shell_config(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy sync should mirror both local authoritative checkouts."""
    config_path = _write_host_config(tmp_path)
    shell_config_checkout = tmp_path / "shell-config"
    shell_config_checkout.mkdir()
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
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
        [
            "deploy",
            "sync",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
            "--remote-root",
            "~/workspaces/dev-fortress",
            "--shell-config-checkout",
            str(shell_config_checkout),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 3
    assert calls[0][0] == "ssh"
    assert calls[0][-1] == (
        "mkdir -p -- "
        "~/workspaces/dev-fortress/dev-container-fortress "
        "~/workspaces/dev-fortress/shell-config"
    )
    assert calls[1][0] == "rsync"
    assert calls[2][0] == "rsync"
    assert calls[1][-1].endswith(":~/workspaces/dev-fortress/dev-container-fortress/")
    assert calls[2][-1].endswith(":~/workspaces/dev-fortress/shell-config/")
    assert "synced dev-fortress-ec2-dev -> ~/workspaces/dev-fortress" in result.stdout


def test_deploy_sync_requires_shell_config_checkout_by_default(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy sync should make shell-config drift explicit by default."""
    config_path = _write_host_config(tmp_path)
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "ft.cli._refresh_managed_known_host",
        lambda target: tmp_path / "known_hosts",
    )
    monkeypatch.setattr("ft.cli._ensure_host_target_runtime_ready", lambda target: True)
    monkeypatch.setattr("ft.cli._workspace_default_shell_config_checkout", lambda: None)

    result = runner.invoke(
        app,
        [
            "deploy",
            "sync",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code != 0
    assert "no shell-config checkout found" in result.output


def test_deploy_exec_runs_from_remote_dev_checkout(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Deploy exec should run commands from the mirrored remote repo."""
    config_path = _write_host_config(tmp_path)
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: f"/usr/bin/{name}")
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
        [
            "deploy",
            "exec",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
            "--remote-root",
            "~/workspaces/dev-fortress",
            "--",
            "uv",
            "run",
            "ft",
            "doctor",
        ],
    )

    assert result.exit_code == 0
    assert calls
    assert calls[0][0] == "ssh"
    assert calls[0][-1] == (
        "cd ~/workspaces/dev-fortress/dev-container-fortress && uv run ft doctor"
    )


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


def test_host_zsh_text_uses_remote_zsh_for_ssh_targets(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Host shell execution should preserve Dev Fortress' zsh-first contract."""
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
                }
            ]
        }
    )
    target = manifest.targets[0]
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

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ssh")

    def fake_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ready\n", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run_command)

    ok, output = _host_zsh_text(
        target,
        "print -r -- ready",
        known_hosts_path=tmp_path / "known_hosts",
    )

    assert ok is True
    assert output == "ready"
    assert calls
    command = calls[0]
    assert command[0] == "ssh"
    assert "-i" in command
    assert str(private_key_path) in command
    assert "StrictHostKeyChecking=yes" in " ".join(command)
    assert command[-1].startswith("zsh -ilc ")
    assert "print -r -- ready" in command[-1]


def test_host_secrets_validate_local_reports_info_as_success(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Fresh local host secrets state should be informational, not failing."""
    config_path = _write_host_config(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_host_zsh_text(
        target: object,
        command: str,
        *,
        known_hosts_path: Path | None = None,
    ) -> tuple[bool, str]:
        calls.append((target.name, command))
        if "dev-fortress-zsh-ready" in command:
            return True, "dev-fortress-zsh-ready\n"
        if '[ -d "${HOME}/.gnupg" ]' in command:
            return True, "present\n"
        if "gpg --batch --list-secret-keys" in command:
            return True, "missing\n"
        if '[ -d "${HOME}/.password-store" ]' in command:
            return True, "present\n"
        if '[ -f "${HOME}/.password-store/.gpg-id" ]' in command:
            return True, "missing\n"
        raise AssertionError(f"unexpected host secrets check: {command}")

    monkeypatch.setattr("ft.cli._host_zsh_text", fake_host_zsh_text)

    result = runner.invoke(
        app,
        ["host", "secrets", "validate", "localhost", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "validating host secrets for localhost" in result.stdout
    assert "gpg_secret_key_present" in result.stdout
    assert "INFO" in result.stdout
    assert calls[0][0] == "localhost"


def test_host_secrets_validate_ssh_prepares_runtime_and_known_hosts(
    tmp_path: Path, monkeypatch: object
) -> None:
    """SSH host secrets validation should use the host target SSH readiness path."""
    config_path = _write_host_config(tmp_path)
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
    runtime_calls: list[str] = []
    known_hosts_path = tmp_path / "known_hosts"
    shell_calls: list[tuple[str, Path | None]] = []

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "ft.cli._ensure_host_target_runtime_ready",
        lambda target: runtime_calls.append(target.name) is None or True,
    )
    monkeypatch.setattr(
        "ft.cli._refresh_managed_known_host",
        lambda target: known_hosts_path,
    )

    def fake_host_zsh_text(
        target: object,
        command: str,
        *,
        known_hosts_path: Path | None = None,
    ) -> tuple[bool, str]:
        shell_calls.append((command, known_hosts_path))
        if "dev-fortress-zsh-ready" in command:
            return True, "dev-fortress-zsh-ready\n"
        if '[ -d "${HOME}/.gnupg" ]' in command:
            return True, "present\n"
        if "gpg --batch --list-secret-keys" in command:
            return True, "present\n"
        if '[ -d "${HOME}/.password-store" ]' in command:
            return True, "present\n"
        if '[ -f "${HOME}/.password-store/.gpg-id" ]' in command:
            return True, "initialized\n"
        raise AssertionError(f"unexpected host secrets check: {command}")

    monkeypatch.setattr("ft.cli._host_zsh_text", fake_host_zsh_text)

    result = runner.invoke(
        app,
        [
            "host",
            "secrets",
            "validate",
            "dev-fortress-ec2-dev",
            "--config",
            str(config_path),
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"target": "dev-fortress-ec2-dev"' in result.stdout
    assert runtime_calls == ["dev-fortress-ec2-dev"]
    assert shell_calls
    assert {call[1] for call in shell_calls} == {known_hosts_path}


def test_root_cli_uses_help_when_no_args_are_passed() -> None:
    """The root CLI should show help instead of erroring on empty invocation."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Operator CLI for Dev Fortress" in result.stdout
    assert "tool" in result.stdout
    assert "container" in result.stdout
    assert "workspace" in result.stdout
    assert "host" in result.stdout
    assert "deploy" in result.stdout
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
    assert manifest.tool_layers["secrets"].mode == "image_build"
    assert manifest.tool_layers["secrets"].build_arg == "WORKSPACE_TOOL_LAYER_SECRETS"
    assert manifest.profiles["ubuntu-secrets"].persisted_mounts == [
        "cache",
        "share",
        "gnupg",
        "password-store",
    ]


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

    result = runner.invoke(
        app, ["workspace", "auth", "doctor", "--json", "ubuntu-base"]
    )

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
            "checks": [{"stat": "OK", "check": "browser_helper", "detail": "ready"}],
        },
    )

    result = runner.invoke(
        app,
        ["workspace", "auth", "validate", "--json", "ubuntu-base"],
    )

    assert result.exit_code == 0
    assert '"profile": "ubuntu-base"' in result.stdout
    assert '"success": true' in result.stdout.lower()


def test_validate_workspace_auth_runtime_reports_secrets_readiness(
    monkeypatch: object,
) -> None:
    """Secrets auth validation should distinguish mounted and initialized state."""
    from ft.cli import _validate_workspace_auth_runtime
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.setattr(
        "ft.cli._run_command",
        lambda command: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    outputs = {
        "browser_helper": "ready\n",
        "browser_env": "unset\n",
        "host_browser_socket": "unset\n",
        "gpg_command": "/usr/bin/gpg\n",
        "pass_command": "/usr/bin/pass\n",
        "gpg_home_present": "present\n",
        "gpg_secret_key_present": "missing\n",
        "password_store_present": "present\n",
        "password_store_initialized": "missing\n",
    }

    def fake_shell_text(container_name: str, command: str) -> tuple[bool, str]:
        if "ft-host-browser-open" in command:
            return True, outputs["browser_helper"]
        if "BROWSER" in command:
            return True, outputs["browser_env"]
        if "DEV_FORTRESS_HOST_BROWSER_SOCKET" in command:
            return True, outputs["host_browser_socket"]
        if "command -v -- 'gpg'" in command:
            return True, outputs["gpg_command"]
        if "command -v -- 'pass'" in command:
            return True, outputs["pass_command"]
        if '[ -d "${HOME}/.gnupg" ]' in command:
            return True, outputs["gpg_home_present"]
        if "gpg --batch --list-secret-keys" in command:
            return True, outputs["gpg_secret_key_present"]
        if '[ -d "${HOME}/.password-store" ]' in command:
            return True, outputs["password_store_present"]
        if '[ -f "${HOME}/.password-store/.gpg-id" ]' in command:
            return True, outputs["password_store_initialized"]
        raise AssertionError(f"unexpected shell check: {command}")

    monkeypatch.setattr("ft.cli._shell_text", fake_shell_text)
    monkeypatch.setattr(
        "ft.cli._load_workspace_profile_manifest",
        lambda: WorkspaceProfileManifest.model_validate(
            {
                "tool_layers": {
                    "secrets": {
                        "description": "secrets",
                        "mode": "image_build",
                        "build_arg": "WORKSPACE_TOOL_LAYER_SECRETS",
                    }
                },
                "profiles": {
                    "ubuntu-secrets": {
                        "description": "secrets",
                        "container_target": "ubuntu",
                        "tool_layers": ["secrets"],
                    }
                },
            }
        ),
    )

    profile = WorkspaceProfileDefinition(
        description="secrets",
        container_target="ubuntu",
        tool_layers=["secrets"],
    )

    report = _validate_workspace_auth_runtime("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in report["checks"]}

    assert report["success"] is True
    assert check_map["gpg_home_present"]["stat"] == "OK"
    assert check_map["gpg_secret_key_present"]["stat"] == "INFO"
    assert check_map["password_store_present"]["stat"] == "OK"
    assert check_map["password_store_initialized"]["stat"] == "INFO"


def test_workspace_secrets_init_test_creates_disposable_state(
    monkeypatch: object,
) -> None:
    """Disposable secrets bootstrap should initialize missing test state."""
    from ft.cli import _init_test_workspace_secrets
    from ft.models import WorkspaceProfileDefinition

    reports = [
        {
            "success": True,
            "checks": [
                {
                    "stat": "INFO",
                    "check": "gpg_secret_key_present",
                    "detail": "missing",
                },
                {
                    "stat": "INFO",
                    "check": "password_store_initialized",
                    "detail": "missing",
                },
            ],
        },
        {
            "success": True,
            "checks": [
                {
                    "stat": "OK",
                    "check": "gpg_secret_key_present",
                    "detail": "present",
                },
                {
                    "stat": "OK",
                    "check": "password_store_initialized",
                    "detail": "initialized",
                },
            ],
        },
    ]
    shell_commands: list[str] = []

    monkeypatch.setattr("ft.cli._workspace_exists", lambda profile_name: True)
    monkeypatch.setattr(
        "ft.cli._validate_workspace_auth_runtime",
        lambda profile_name, profile: reports.pop(0),
    )

    def fake_shell_text(container_name: str, command: str) -> tuple[bool, str]:
        shell_commands.append(command)
        return True, "initialized disposable secrets with key ABC123\n"

    monkeypatch.setattr("ft.cli._shell_text", fake_shell_text)

    profile = WorkspaceProfileDefinition(
        description="secrets",
        container_target="ubuntu",
        tool_layers=["secrets"],
    )

    report = _init_test_workspace_secrets("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in report["checks"]}

    assert report["success"] is True
    assert report["disposable"] is True
    assert len(shell_commands) == 1
    assert "gpg --batch --generate-key" in shell_commands[0]
    assert check_map["init_test"]["stat"] == "OK"
    assert check_map["gpg_secret_key_present"]["stat"] == "OK"
    assert check_map["password_store_initialized"]["stat"] == "OK"


def test_workspace_secrets_init_test_refuses_existing_state(
    monkeypatch: object,
) -> None:
    """Disposable secrets bootstrap should not overwrite existing state by default."""
    from ft.cli import _init_test_workspace_secrets
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.setattr("ft.cli._workspace_exists", lambda profile_name: True)
    monkeypatch.setattr(
        "ft.cli._validate_workspace_auth_runtime",
        lambda profile_name, profile: {
            "success": True,
            "checks": [
                {
                    "stat": "OK",
                    "check": "gpg_secret_key_present",
                    "detail": "present",
                },
                {
                    "stat": "OK",
                    "check": "password_store_initialized",
                    "detail": "initialized",
                },
            ],
        },
    )

    profile = WorkspaceProfileDefinition(
        description="secrets",
        container_target="ubuntu",
        tool_layers=["secrets"],
    )

    report = _init_test_workspace_secrets("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in report["checks"]}

    assert report["success"] is False
    assert check_map["existing_secrets_state"]["stat"] == "FAIL"


def test_workspace_secrets_init_test_force_uses_alias_safe_cleanup(
    monkeypatch: object,
) -> None:
    """Forced disposable bootstrap should bypass shell aliases during cleanup."""
    from ft.cli import _init_test_workspace_secrets
    from ft.models import WorkspaceProfileDefinition

    reports = [
        {
            "success": True,
            "checks": [
                {
                    "stat": "OK",
                    "check": "gpg_secret_key_present",
                    "detail": "present",
                },
                {
                    "stat": "OK",
                    "check": "password_store_initialized",
                    "detail": "initialized",
                },
            ],
        },
        {
            "success": True,
            "checks": [
                {
                    "stat": "OK",
                    "check": "gpg_secret_key_present",
                    "detail": "present",
                },
                {
                    "stat": "OK",
                    "check": "password_store_initialized",
                    "detail": "initialized",
                },
            ],
        },
    ]
    shell_commands: list[str] = []

    monkeypatch.setattr("ft.cli._workspace_exists", lambda profile_name: True)
    monkeypatch.setattr(
        "ft.cli._validate_workspace_auth_runtime",
        lambda profile_name, profile: reports.pop(0),
    )

    def fake_shell_text(container_name: str, command: str) -> tuple[bool, str]:
        shell_commands.append(command)
        return True, "initialized disposable secrets with key ABC123\n"

    monkeypatch.setattr("ft.cli._shell_text", fake_shell_text)

    profile = WorkspaceProfileDefinition(
        description="secrets",
        container_target="ubuntu",
        tool_layers=["secrets"],
    )

    report = _init_test_workspace_secrets("ubuntu-secrets", profile, force=True)

    assert report["success"] is True
    assert shell_commands[0].startswith("command find ")
    assert shell_commands[1].startswith("command find ")
    assert "gpg --batch --generate-key" in shell_commands[2]


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
    assert (
        "/usr/local/bin/ft-host-browser-open" in check_map["browser_strategy"]["detail"]
    )


def test_workspace_auth_checks_report_secrets_baseline(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Workspace auth checks should report the first-pass secrets baseline."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    profile = WorkspaceProfileDefinition(
        description="secrets",
        persisted_mounts=["cache", "share", "gnupg", "password-store"],
        tool_layers=["secrets"],
    )

    checks = _workspace_auth_checks("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["gpg_state"]["stat"] == "WARN"
    assert check_map["password_store_state"]["stat"] == "WARN"
    assert check_map["secrets_baseline"]["stat"] == "OK"


def test_workspace_auth_checks_warn_when_secrets_mounts_are_missing(
    monkeypatch: object,
) -> None:
    """Secrets profiles should warn if runtime GPG or pass mounts are omitted."""
    from ft.cli import _workspace_auth_checks
    from ft.models import WorkspaceProfileDefinition

    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)

    profile = WorkspaceProfileDefinition(
        description="secrets",
        persisted_mounts=["cache", "share"],
        tool_layers=["secrets"],
    )

    checks = _workspace_auth_checks("ubuntu-secrets", profile)
    check_map = {check["check"]: check for check in checks}

    assert check_map["secrets_baseline"]["stat"] == "WARN"
    assert "gnupg" in check_map["secrets_baseline"]["detail"]
    assert "password-store" in check_map["secrets_baseline"]["detail"]


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


def test_workspace_layer_command_checks_include_secrets_commands(
    monkeypatch: object,
) -> None:
    """Secrets image-build layers should require GPG and pass at validation time."""
    from ft.cli import _workspace_layer_command_checks
    from ft.models import WorkspaceProfileDefinition, WorkspaceProfileManifest

    monkeypatch.setattr(
        "ft.cli._load_workspace_profile_manifest",
        lambda: WorkspaceProfileManifest.model_validate(
            {
                "tool_layers": {
                    "secrets": {
                        "description": "secrets",
                        "mode": "image_build",
                        "build_arg": "WORKSPACE_TOOL_LAYER_SECRETS",
                    }
                },
                "profiles": {
                    "ubuntu-secrets": {
                        "description": "secrets",
                        "container_target": "ubuntu",
                        "tool_layers": ["secrets"],
                    }
                },
            }
        ),
    )

    profile = WorkspaceProfileDefinition(
        description="secrets",
        container_target="ubuntu",
        tool_layers=["secrets"],
    )

    assert _workspace_layer_command_checks(profile) == ["gpg", "pass"]


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
    assert f"{browser_bridge_dir}:/tmp/dev-fortress-host-services" in run_command
    assert f"{windows_system_path}:{windows_system_path}:ro" in run_command
    assert f"{wsl_init_path}:{wsl_init_path}:ro" in run_command
    assert f"{wsl_interop_root}:{wsl_interop_root}" in run_command
    assert "--env" in run_command
    assert (
        "DEV_FORTRESS_HOST_BROWSER_SOCKET="
        "/tmp/dev-fortress-host-services/browser-open.sock" in run_command
    )
    assert "DEV_FORTRESS_WORKSPACE=1" in run_command
    assert "DEV_FORTRESS_AWS_LOGIN_MODE=device-code" in run_command
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
    assert calls == [["ubuntu", "alpine", "arch"]]


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
        if command[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
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
    assert _resolve_container_targets("all") == ["ubuntu", "alpine", "arch"]
    assert _resolve_container_targets("alp*") == ["alpine"]
    assert _resolve_container_targets("arch") == ["arch"]


def test_container_target_resolution_skips_unsupported_architectures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fan-out selectors should skip amd64-only targets on arm64 hosts."""
    monkeypatch.setattr("ft.cli.detect_architecture", lambda: "arm64")

    assert _resolve_container_targets("all") == ["ubuntu", "alpine"]
    assert _resolve_container_targets("a*") == ["alpine"]
    assert _resolve_container_targets("arch") == ["arch"]


def test_container_build_refuses_arch_on_arm64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arch builds should stop before invoking Docker on unsupported hosts."""
    commands: list[list[str]] = []
    monkeypatch.setattr("ft.cli.detect_architecture", lambda: "arm64")
    monkeypatch.setattr("ft.cli._run_command", lambda command: commands.append(command))

    result = runner.invoke(app, ["container", "build", "arch"])

    assert result.exit_code != 0
    assert "unsupported architecture for arch" in result.stdout
    assert commands == []
    assert _require_supported_container_architecture("ubuntu") is True


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
    assert calls == ["ubuntu", "alpine", "arch"]


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
    assert calls == ["ubuntu", "alpine", "arch"]


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
    assert calls == [["ubuntu", "alpine", "arch"]]


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
    assert calls == ["ubuntu", "alpine", "arch"]


def _fake_container_state(commands: list[list[str]], state: str | None) -> object:
    """Fake docker calls for a container that is running, stopped, or missing."""

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            if state is None:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{state}\n", stderr=""
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    return fake_run


def test_ensure_container_running_reuses_running_container(
    monkeypatch: object,
) -> None:
    """A running target container should be reused, not replaced."""
    commands: list[list[str]] = []
    monkeypatch.setattr("ft.cli._run_command", _fake_container_state(commands, "true"))
    monkeypatch.setattr(
        "ft.cli._up_single_container_target",
        lambda target: pytest.fail("running container must not be replaced"),
    )

    assert _ensure_container_target_running("ubuntu") is True
    assert len(commands) == 1


def test_ensure_container_running_starts_stopped_container(
    monkeypatch: object,
) -> None:
    """A stopped target container should be restarted with its state intact."""
    commands: list[list[str]] = []
    monkeypatch.setattr("ft.cli._run_command", _fake_container_state(commands, "false"))
    monkeypatch.setattr(
        "ft.cli._up_single_container_target",
        lambda target: pytest.fail("stopped container must not be replaced"),
    )

    assert _ensure_container_target_running("ubuntu") is True
    assert commands[-1] == ["docker", "start", "dev-fortress-ubuntu-test"]


def test_ensure_container_running_creates_missing_container(
    monkeypatch: object,
) -> None:
    """A missing target container should be created through the normal up path."""
    commands: list[list[str]] = []
    created: list[str] = []
    monkeypatch.setattr("ft.cli._run_command", _fake_container_state(commands, None))
    monkeypatch.setattr(
        "ft.cli._up_single_container_target",
        lambda target: created.append(target) or True,
    )

    assert _ensure_container_target_running("ubuntu") is True
    assert created == ["ubuntu"]


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


def test_container_up_arch_publishes_dedicated_ssh_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arch disposable targets should forward their own loopback SSH port."""
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_command", fake_run)

    assert _up_single_container_target("arch") is True
    run_command = commands[-1]
    assert "127.0.0.1:2224:2222" in run_command
    assert "dev-container-fortress:arch-test" in run_command


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
    assert calls == ["ubuntu", "alpine", "arch"]


def test_container_reset_runs_for_wildcard_target(monkeypatch: object) -> None:
    """Reset should iterate every target selected by the resolver."""
    calls: list[str] = []

    def fake_reset(target: str) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._reset_single_container_target", fake_reset)

    result = runner.invoke(app, ["container", "reset", "*"])

    assert result.exit_code == 0
    assert calls == ["ubuntu", "alpine", "arch"]


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
        '#!/bin/sh\nexec "$(dirname "$0")/../libexec/demo-tool/demo-tool" "$@"\n',
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


def test_install_tool_reuses_cached_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    assert sorted(download_calls) == sorted(
        [archive_path.as_uri(), checksum_path.as_uri()]
    )
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
        lambda url, destination: shutil.copy2(
            Path(url.removeprefix("file://")), destination
        ),
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
