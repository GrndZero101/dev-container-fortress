"""Reusable secrets readiness checks for Dev Fortress targets."""

from __future__ import annotations

from collections.abc import Callable


ShellExecutor = Callable[[str], tuple[bool, str]]


SECRET_READINESS_COMMANDS: tuple[tuple[str, str, str], ...] = (
    (
        "gpg_home_present",
        (
            'if [ -d "${HOME}/.gnupg" ]; '
            "then print -r -- present; else print -r -- missing; fi"
        ),
        "present",
    ),
    (
        "gpg_secret_key_present",
        (
            "gpg --batch --list-secret-keys --with-colons 2>/dev/null "
            '| awk -F: \'$1 == "sec" { found=1 } '
            'END { print found ? "present" : "missing" }\''
        ),
        "present",
    ),
    (
        "password_store_present",
        (
            'if [ -d "${HOME}/.password-store" ]; '
            "then print -r -- present; else print -r -- missing; fi"
        ),
        "present",
    ),
    (
        "password_store_initialized",
        (
            'if [ -f "${HOME}/.password-store/.gpg-id" ]; '
            "then print -r -- initialized; else print -r -- missing; fi"
        ),
        "initialized",
    ),
)


def last_non_empty_line(output: str) -> str:
    """Return the last non-empty line from command output."""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def run_secret_readiness_checks(
    executor: ShellExecutor,
) -> list[dict[str, str]]:
    """Run shared GPG and pass readiness checks through a shell executor.

    Args:
        executor: Callable that executes one shell command on a target and
            returns ``(success, output)``.

    Returns:
        Validation result dictionaries with ``stat``, ``check``, and ``detail``.
    """
    results: list[dict[str, str]] = []
    for check_name, command, expected in SECRET_READINESS_COMMANDS:
        ok, output = executor(command)
        normalized_output = last_non_empty_line(output)
        results.append(
            {
                "stat": "OK" if ok and normalized_output == expected else "INFO",
                "check": check_name,
                "detail": normalized_output or "unknown",
            }
        )
    return results
