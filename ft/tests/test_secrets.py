"""Tests for shared secrets readiness checks."""

from __future__ import annotations

from ft.secrets import SECRET_READINESS_COMMANDS, run_secret_readiness_checks


def test_secret_readiness_checks_report_fresh_state() -> None:
    """Fresh mounted secrets state should be informational, not failing."""
    outputs = {
        "gpg_home_present": "present\n",
        "gpg_secret_key_present": "missing\n",
        "password_store_present": "present\n",
        "password_store_initialized": "missing\n",
    }

    def executor(command: str) -> tuple[bool, str]:
        for check_name, check_command, _ in SECRET_READINESS_COMMANDS:
            if command == check_command:
                return True, outputs[check_name]
        raise AssertionError(f"unexpected command: {command}")

    checks = run_secret_readiness_checks(executor)
    check_map = {check["check"]: check for check in checks}

    assert check_map["gpg_home_present"]["stat"] == "OK"
    assert check_map["gpg_secret_key_present"]["stat"] == "INFO"
    assert check_map["password_store_present"]["stat"] == "OK"
    assert check_map["password_store_initialized"]["stat"] == "INFO"


def test_secret_readiness_checks_report_restored_state() -> None:
    """Restored secrets state should report key and password store readiness."""
    outputs = {
        "gpg_home_present": "present\n",
        "gpg_secret_key_present": "present\n",
        "password_store_present": "present\n",
        "password_store_initialized": "initialized\n",
    }

    def executor(command: str) -> tuple[bool, str]:
        for check_name, check_command, _ in SECRET_READINESS_COMMANDS:
            if command == check_command:
                return True, outputs[check_name]
        raise AssertionError(f"unexpected command: {command}")

    checks = run_secret_readiness_checks(executor)

    assert {check["stat"] for check in checks} == {"OK"}
