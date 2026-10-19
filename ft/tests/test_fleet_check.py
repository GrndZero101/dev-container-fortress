"""Tests for the fleet check planner, runner, and judge."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer
from ft.cli import _fleet_host_checks, _fleet_installer
from ft.fleet_check import (
    FAILED,
    PASSED,
    CheckStep,
    HostCheck,
    check_kind,
    judge_step,
    markdown_summary,
    run_host_check,
)
from ft.models import HostTargetManifest

RECAP = (
    "localhost                  : ok=81   changed={changed}    unreachable=0    "
    "failed={failed}    skipped=39   rescued=0    ignored=0   "
)


def _recap(changed: int, failed: int = 0) -> str:
    """Return one Ansible recap line with the given counters."""
    return RECAP.format(changed=changed, failed=failed)


def _step(
    tmp_path: Path, label: str, script: str, *, converged: bool = False
) -> CheckStep:
    """Return a step that runs one shell snippet."""
    return CheckStep(
        label=label,
        command=["sh", "-c", script],
        log_path=tmp_path / f"{label.replace(' ', '')}.log",
        expect_converged=converged,
    )


def test_check_kind_uses_the_one_liner_on_ubuntu_only() -> None:
    """Ubuntu gets the one-liner; other OSes go through ft host validate."""
    assert check_kind("ubuntu") == "one-liner"
    assert check_kind("arch") == "validate"
    assert check_kind("alpine") == "validate"


@pytest.mark.parametrize(
    ("returncode", "log", "converged", "passed", "summary"),
    [
        (0, _recap(26), False, True, "changed=26"),
        (0, _recap(0), True, True, "changed=0"),
        (0, _recap(1), True, False, "changed=1: expected changed=0"),
        (2, _recap(5), False, False, "exit 2 (changed=5)"),
        (0, "no ansible here", False, False, "no Ansible recap in the log"),
        (0, _recap(3, failed=1), False, False, "changed=3, failed=1"),
        (0, "\x1b[0;33m" + _recap(4) + "\x1b[0m", False, True, "changed=4"),
    ],
)
def test_judge_step(
    tmp_path: Path,
    returncode: int,
    log: str,
    converged: bool,
    passed: bool,
    summary: str,
) -> None:
    """A step passes on exit 0 with a clean recap, converged when required."""
    step = _step(tmp_path, "pass", "true", converged=converged)

    assert judge_step(step, returncode, log) == (passed, summary)


def test_judge_step_lists_every_validate_pass(tmp_path: Path) -> None:
    """A validate log's check, real, and second passes all appear in order."""
    log = "\n".join([_recap(4), _recap(18), _recap(0)])

    assert judge_step(_step(tmp_path, "validate", "true"), 0, log) == (
        True,
        "changed=4, changed=18, changed=0",
    )


def test_run_host_check_passes_and_logs_each_step(tmp_path: Path) -> None:
    """Steps run in order, each into its own log."""
    check = HostCheck(
        host="dev-fortress-fleet-ubuntu-2604-arm64",
        os="ubuntu",
        architecture="arm64",
        check="one-liner",
        steps=[
            _step(tmp_path, "pass 1", f"echo '{_recap(26)}'"),
            _step(tmp_path, "pass 2", f"echo '{_recap(0)}'", converged=True),
        ],
    )
    updates: list[str] = []

    run_host_check(
        check, timeout_seconds=30, on_update=lambda c: updates.append(c.status)
    )

    assert check.status == PASSED
    assert check.results == ["pass 1: changed=26", "pass 2: changed=0"]
    assert (tmp_path / "pass1.log").read_text().strip() == _recap(26).strip()
    assert updates[0] == "running" and updates[-1] == PASSED
    assert check.elapsed() > 0


def test_run_host_check_stops_at_the_first_failure(tmp_path: Path) -> None:
    """A failed step stops the check, so later steps never run."""
    check = HostCheck(
        host="h",
        os="ubuntu",
        architecture="amd64",
        check="one-liner",
        steps=[
            _step(tmp_path, "pass 1", "exit 3"),
            _step(tmp_path, "pass 2", "touch should-not-exist"),
        ],
    )

    run_host_check(check, timeout_seconds=30, on_update=lambda _: None)

    assert check.status == FAILED
    assert check.detail == "pass 1: exit 3"
    assert not (tmp_path / "pass2.log").exists()


def test_run_host_check_times_out(tmp_path: Path) -> None:
    """A step that runs past the limit fails instead of hanging the run."""
    check = HostCheck(
        host="h",
        os="arch",
        architecture="amd64",
        check="validate",
        steps=[_step(tmp_path, "validate", "sleep 5")],
    )

    run_host_check(check, timeout_seconds=0.2, on_update=lambda _: None)

    assert check.status == FAILED
    assert "timed out" in check.detail


def test_markdown_summary_marks_each_host(tmp_path: Path) -> None:
    """The markdown table has one row per host with a pass or fail mark."""
    passed = HostCheck("a", "ubuntu", "arm64", "one-liner", [], status=PASSED)
    passed.results = ["pass 1: changed=26", "pass 2: changed=0"]
    failed = HostCheck("b", "arch", "amd64", "validate", [], status=FAILED)
    failed.results = ["validate: exit 1"]

    table = markdown_summary([passed, failed]).splitlines()

    assert table[0] == "| Host | Check | Result | Time |"
    assert table[2].startswith(
        "| a (arm64) | one-liner | ✅ pass 1: changed=26; pass 2"
    )
    assert table[3].startswith("| b (amd64) | validate | ❌ validate: exit 1")


def test_fleet_installer_defaults_to_main() -> None:
    """Without a ref, the checks install the published main installer."""
    url, args = _fleet_installer(None)

    assert url.endswith("/main/install.sh")
    assert args == []


def test_fleet_installer_pins_a_branch_to_its_commit(monkeypatch: object) -> None:
    """A branch ref is fetched by SHA so a cached branch copy is never used."""
    sha = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setattr(
        "ft.cli._run_command",
        lambda command: subprocess.CompletedProcess(
            command, 0, stdout=f"{sha}\trefs/heads/feat/x\n", stderr=""
        ),
    )

    url, args = _fleet_installer("feat/x")

    assert url.endswith(f"/{sha}/install.sh")
    assert args == ["--ref", "feat/x"]


def test_fleet_installer_rejects_an_unpushed_ref(monkeypatch: object) -> None:
    """A ref the remote does not have fails with a clear hint."""
    monkeypatch.setattr(
        "ft.cli._run_command",
        lambda command: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    with pytest.raises(typer.BadParameter, match="push it first"):
        _fleet_installer("feat/missing")


def test_fleet_host_checks_plan_one_check_per_os(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Ubuntu hosts get two SSH passes; other OSes get ft host validate."""
    config_path = tmp_path / "hosts.toml"
    config_path.write_text(
        "\n".join(
            f"""[[targets]]
name = "dev-fortress-fleet-{suffix}"
kind = "cloud"
connection = "ssh"
host = "{suffix}.example.internal"
user = "{user}"
auth_method = "ssh_key"
ssh_key_name = "dev-fortress-fleet"
tags = ["ssh", "cloud"]
"""
            for suffix, user in [
                ("ubuntu-2604-arm64", "ubuntu"),
                ("arch-amd64", "arch"),
            ]
        )
    )
    payload = {
        "hosts": {
            "value": {
                "dev-fortress-fleet-ubuntu-2604-arm64": {
                    "os": "ubuntu",
                    "architecture": "arm64",
                },
                "dev-fortress-fleet-arch-amd64": {
                    "os": "arch",
                    "architecture": "amd64",
                },
            }
        }
    }
    monkeypatch.setattr(
        "ft.cli._terraform_output_payload", lambda terraform_dir: payload
    )
    monkeypatch.setattr(
        "ft.cli._host_ssh_command",
        lambda target: ["ssh", "-i", "key", f"{target.user}@{target.host}"],
    )

    checks = _fleet_host_checks(
        "*", ref=None, config=config_path, log_dir=tmp_path / "logs"
    )

    arch, ubuntu = checks
    assert [step.label for step in ubuntu.steps] == ["pass 1", "pass 2"]
    assert ubuntu.steps[0].command[:3] == ["ssh", "-i", "key"]
    assert "BatchMode=yes" in ubuntu.steps[0].command
    assert ubuntu.steps[0].command[-2] == "ubuntu@ubuntu-2604-arm64.example.internal"
    assert ubuntu.steps[0].command[-1].endswith("/main/install.sh | sh")
    assert [step.expect_converged for step in ubuntu.steps] == [False, True]
    assert arch.check == "validate"
    assert arch.steps[0].command[1:6] == ["-m", "ft", "host", "validate", arch.host]
    assert arch.steps[0].command[-2:] == ["--config", str(config_path)]


def test_fleet_host_checks_filters_by_selector(
    tmp_path: Path, monkeypatch: object
) -> None:
    """A selector that matches no fleet host stops with a clear message."""
    monkeypatch.setattr(
        "ft.cli._terraform_output_payload",
        lambda terraform_dir: {
            "hosts": {
                "value": {
                    "dev-fortress-fleet-arch-amd64": {
                        "os": "arch",
                        "architecture": "amd64",
                    }
                }
            }
        },
    )
    manifest = HostTargetManifest.model_validate(
        {
            "targets": [
                {
                    "name": "dev-fortress-fleet-arch-amd64",
                    "kind": "cloud",
                    "connection": "ssh",
                    "host": "arch.example.internal",
                    "user": "arch",
                    "auth_method": "ssh_key",
                    "tags": ["ssh"],
                }
            ]
        }
    )
    monkeypatch.setattr(
        "ft.cli._load_host_target_manifest", lambda config: (None, manifest)
    )
    monkeypatch.setattr("ft.cli._fleet_installer", lambda ref: ("url", []))

    with pytest.raises(typer.Exit):
        _fleet_host_checks("*ubuntu*", ref=None, config=None, log_dir=tmp_path)
