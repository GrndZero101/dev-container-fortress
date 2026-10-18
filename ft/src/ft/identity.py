"""Git identity and forge-login helpers for ft.

The identity step sets ``user.name`` and ``user.email`` without ever blocking a
non-interactive bootstrap: explicit values win, a terminal prompts only for
what is still missing, and anything else is skipped with the manual commands.
An existing identity changes only when a new value is passed explicitly.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

GIT_NAME_ENV = "DEV_CONTAINER_FORTRESS_GIT_NAME"
GIT_EMAIL_ENV = "DEV_CONTAINER_FORTRESS_GIT_EMAIL"
FORGE_LOGIN_ENV = "DEV_CONTAINER_FORTRESS_FORGE_LOGIN"

NOREPLY_HINT = (
    "GitHub declines pushes from a private email; use the noreply address from "
    "GitHub > Settings > Emails (<id>+<user>@users.noreply.github.com)."
)

# Each forge maps to its CLI, a status check that succeeds when already logged
# in, and the login commands. `gh auth setup-git` makes HTTPS pushes use gh.
FORGE_LOGINS: dict[str, tuple[str, list[str], list[list[str]]]] = {
    "github": (
        "gh",
        ["gh", "auth", "status", "--hostname", "github.com"],
        [
            [
                "gh",
                "auth",
                "login",
                "--hostname",
                "github.com",
                "--git-protocol",
                "https",
                "--web",
            ],
            ["gh", "auth", "setup-git"],
        ],
    ),
    "gitlab": (
        "glab",
        ["glab", "auth", "status"],
        [["glab", "auth", "login"]],
    ),
}


@dataclass(frozen=True)
class GitIdentity:
    """A Git author identity.

    Attributes:
        name: The ``user.name`` value, empty when unset.
        email: The ``user.email`` value, empty when unset.
    """

    name: str = ""
    email: str = ""

    @property
    def complete(self) -> bool:
        """Return whether both the name and the email are set."""
        return bool(self.name and self.email)

    def __str__(self) -> str:
        """Return the identity in Git's ``Name <email>`` form."""
        return f"{self.name or '(no name)'} <{self.email or 'no email'}>"


def _scope_flag(local: bool) -> str:
    """Return the ``git config`` scope flag.

    Args:
        local: Whether to use the current checkout's config.

    Returns:
        ``--local`` or ``--global``.
    """
    return "--local" if local else "--global"


def read_identity(*, local: bool, cwd: Path | None = None) -> GitIdentity:
    """Read the Git identity from one config scope.

    Args:
        local: Whether to read the current checkout's config instead of the
            global one.
        cwd: Directory to run Git in.

    Returns:
        The identity, with empty fields for unset values.
    """

    def get(key: str) -> str:
        result = subprocess.run(
            ["git", "config", _scope_flag(local), "--get", key],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    return GitIdentity(name=get("user.name"), email=get("user.email"))


def write_identity(
    identity: GitIdentity, *, local: bool, cwd: Path | None = None
) -> None:
    """Write a complete Git identity to one config scope.

    Args:
        identity: The identity to write.
        local: Whether to write the current checkout's config instead of the
            global one.
        cwd: Directory to run Git in.

    Raises:
        subprocess.CalledProcessError: If ``git config`` fails.
    """
    for key, value in (("user.name", identity.name), ("user.email", identity.email)):
        subprocess.run(
            ["git", "config", _scope_flag(local), key, value],
            cwd=cwd,
            check=True,
        )


def validate_email(email: str) -> bool:
    """Return whether an email looks usable as a Git author email.

    Args:
        email: Candidate email address.

    Returns:
        True when the address has one ``@`` with text on both sides and no
        whitespace.
    """
    local_part, at, domain = email.partition("@")
    return bool(
        at
        and local_part
        and domain
        and "@" not in domain
        and not any(c.isspace() for c in email)
    )


def resolve_identity(
    current: GitIdentity,
    *,
    name: str | None,
    email: str | None,
    prompt: Callable[[str, str], str] | None,
) -> GitIdentity:
    """Combine the current identity, explicit values, and optional prompts.

    Args:
        current: The identity already configured.
        name: An explicit name, which replaces the current one.
        email: An explicit email, which replaces the current one.
        prompt: A callable taking a label and a default and returning the
            answer, used only for fields that are still empty. ``None`` skips
            prompting.

    Returns:
        The resolved identity, which may still be incomplete.
    """
    resolved_name = (name or "").strip() or current.name
    resolved_email = (email or "").strip() or current.email
    if prompt is not None:
        if not resolved_name:
            resolved_name = prompt("Git user.name", "").strip()
        if not resolved_email:
            resolved_email = prompt("Git user.email", "").strip()
    return GitIdentity(name=resolved_name, email=resolved_email)


def manual_identity_commands(*, local: bool) -> list[str]:
    """Return the manual commands that set a Git identity.

    Args:
        local: Whether the commands should target the current checkout.

    Returns:
        Shell commands for the operator to copy.
    """
    scope = "" if local else " --global"
    return [
        f'git config{scope} user.name "Your Name"',
        f'git config{scope} user.email "you@example.com"',
    ]


def forge_cli_available(forge: str) -> bool:
    """Return whether the CLI for one forge is on ``PATH``.

    Args:
        forge: A key of ``FORGE_LOGINS``.

    Returns:
        True when the forge CLI is installed.
    """
    return shutil.which(FORGE_LOGINS[forge][0]) is not None


def forge_logged_in(forge: str) -> bool:
    """Return whether the forge CLI already has a login.

    Args:
        forge: A key of ``FORGE_LOGINS``.

    Returns:
        True when the forge CLI's status check succeeds.
    """
    status_command = FORGE_LOGINS[forge][1]
    result = subprocess.run(status_command, capture_output=True, check=False)
    return result.returncode == 0


def run_forge_login(forge: str) -> bool:
    """Run the interactive login commands for one forge.

    Args:
        forge: A key of ``FORGE_LOGINS``.

    Returns:
        True when every login command succeeded.

    Side effects:
        Starts the forge CLI's browser or device-code login on the terminal.
    """
    for command in FORGE_LOGINS[forge][2]:
        if subprocess.run(command, check=False).returncode != 0:
            return False
    return True
