"""CLI and installer tests for ft."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tarfile

import pytest
import typer
from typer.testing import CliRunner

from ft.cli import (
    _container_host_ssh_public_key_path,
    _effective_install_root,
    _last_non_empty_line,
    _resolve_container_targets,
    _resolve_host_targets,
    _resolve_single_container_target,
    _up_single_container_target,
    _stage_local_shell_config,
    app,
)
from ft.installer import build_plan, install_tool
from ft.models import HostTargetManifest, IntegrityConfig, ToolAsset, ToolDefinition

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
tags = ["docker", "ubuntu"]

[[targets]]
name = "workstation-example"
kind = "workstation"
connection = "ssh"
host = "workstation.example.internal"
user = "devops"
auth_method = "ssh_key"
ssh_key_name = "workstation-devops"
tags = ["ssh", "workstation"]
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
    assert "doctor" in result.stdout
    assert "bootstrap" in result.stdout


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
    assert (
        'ansible_ssh_common_args: "-o StrictHostKeyChecking=yes -o UserKnownHostsFile='
        in result.stdout
    )


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
        / "id_ed25519"
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


def test_root_cli_uses_help_when_no_args_are_passed() -> None:
    """The root CLI should show help instead of erroring on empty invocation."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Operator CLI for Dev Fortress" in result.stdout
    assert "tool" in result.stdout
    assert "container" in result.stdout
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
        / "id_ed25519"
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
        / "id_ed25519"
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
            / "id_ed25519"
        )
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("private\n", encoding="utf-8")
        key_path.with_name("id_ed25519.pub").write_text("public\n", encoding="utf-8")
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
            / "id_ed25519"
        )
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("private\n", encoding="utf-8")
        key_path.with_name("id_ed25519.pub").write_text(
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
    calls: list[list[str]] = []
    inventories: list[str] = []

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def fake_stream(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
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
    assert calls[0][-1] == "--check"
    assert "localhost:" in inventories[0]
    assert 'ansible_connection: "local"' in inventories[0]


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
    assert "dev-fortress-ubuntu` or use --ensure-ssh-keys." in result.stdout


def test_plan_uses_environment_defaults(monkeypatch: object) -> None:
    """The CLI should honor environment-backed settings defaults."""
    manifest_path = Path(__file__).resolve().parents[1] / "tools" / "tools.toml"
    monkeypatch.setenv("FT_MANIFEST", str(manifest_path))
    monkeypatch.setenv("FT_TARGET", "ubuntu")
    monkeypatch.setenv("FT_SYSTEM", "linux")
    monkeypatch.setenv("FT_ARCHITECTURE", "amd64")

    result = runner.invoke(app, ["plan", "--tool", "atuin"])

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
            "shell_config_branch": "feature-ohmyposh_disble_transient_prompt",
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


def test_container_up_alpine_keeps_sleep_entrypoint(monkeypatch: object) -> None:
    """Non-SSH disposable targets should keep the simple sleep entrypoint."""
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
    assert commands[-1][-2:] == ["sleep", "infinity"]


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
    calls: list[str] = []

    def fake_refresh(target: str) -> bool:
        calls.append(target)
        return True

    monkeypatch.setattr("ft.cli._refresh_single_container_target", fake_refresh)

    result = runner.invoke(app, ["container", "refresh", "ubuntu"])

    assert result.exit_code == 0
    assert calls == ["ubuntu"]


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

    installed_path = install_tool(plan, healthcheck=True)

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

    installed_path = install_tool(plan, healthcheck=True)

    assert installed_path.exists()
    assert installed_path.name == "demo-tool"


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
