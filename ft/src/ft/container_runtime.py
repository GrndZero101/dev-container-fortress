"""Runtime contract shared by ``ft workspace`` and the rendered devcontainers.

Dev Fortress starts containers two ways: ``ft workspace`` runs them with
``docker run``, and VS Code or the devcontainer CLI runs the definitions that
``ft devcontainer render`` writes. Both read this module, so a persisted
mount, a start step, or an option's environment is declared once. See
``docs/design/architecture.md`` for why the two runtimes stay separate.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTAINER_HOME = "/home/vscode"
CLAUDE_CONFIG_DIR = f"{CONTAINER_HOME}/.claude"
HOMEBREW_PREFIX = "/home/linuxbrew/.linuxbrew"

# The image owns ``${XDG_DATA_HOME}`` (``uv`` tools and Python, ``ft``, the
# Neovim runtime, and prewarmed zinit plugins), so persisted mounts target
# narrow runtime-state paths rather than the whole data root.
PERSISTED_MOUNT_PATHS: dict[str, str] = {
    "cache": f"{CONTAINER_HOME}/.cache",
    "state": f"{CONTAINER_HOME}/.local/state",
    "zoxide": f"{CONTAINER_HOME}/.local/share/zoxide",
    "atuin": f"{CONTAINER_HOME}/.local/share/atuin",
    "gh": f"{CONTAINER_HOME}/.config/gh",
    "glab": f"{CONTAINER_HOME}/.config/glab-cli",
    "aws": f"{CONTAINER_HOME}/.aws",
    "azure": f"{CONTAINER_HOME}/.azure",
    "gnupg": f"{CONTAINER_HOME}/.gnupg",
    "password-store": f"{CONTAINER_HOME}/.password-store",
    "claude": CLAUDE_CONFIG_DIR,
    "claude-versions": f"{CONTAINER_HOME}/.local/share/claude",
}

# Optional components a container installs when it starts, each with the
# persisted mounts and environment it needs. The other options, such as the
# tmux profiles, are host-only.
OPTION_MOUNTS: dict[str, tuple[str, ...]] = {
    "claude-code": ("claude", "claude-versions"),
}
OPTION_ENV: dict[str, dict[str, str]] = {
    # Keeps ~/.claude.json inside the persisted config directory too.
    "claude-code": {"CLAUDE_CONFIG_DIR": CLAUDE_CONFIG_DIR},
}

# Persisted mounts every devcontainer carries. Profiles choose their own set
# for ``ft workspace``; a devcontainer has no profile, so it gets this one.
DEVCONTAINER_MOUNTS: tuple[str, ...] = ("state", "zoxide", "atuin")
# State for tools that come from the Homebrew floor, so musl targets skip it.
HOMEBREW_TOOL_MOUNTS: tuple[str, ...] = ("gh", "glab")


@dataclass(frozen=True)
class StartStep:
    """One in-image helper that a container runs each time it starts.

    Attributes:
        command: The helper on the image's ``PATH``.
        since: The milestone whose images first ship the helper, named in the
            error when an older image lacks it.
        homebrew_only: Whether only Homebrew targets run the step.
        option: The option that selects the step, or None when it always runs.
    """

    command: str
    since: str
    homebrew_only: bool = False
    option: str | None = None

    def applies(self, *, homebrew: bool) -> bool:
        """Return whether the step belongs on a target at all.

        Args:
            homebrew: Whether the target's userland comes from Homebrew.

        Returns:
            True unless the step is Homebrew-only and the target is not.
        """
        return homebrew or not self.homebrew_only

    def devcontainer_command(self) -> str:
        """Return the step as a devcontainer lifecycle command.

        A devcontainer cannot read the host's saved option selection, so an
        option-gated step checks ``DEV_CONTAINER_FORTRESS_OPTIONS`` itself.

        Returns:
            The shell command for ``postStartCommand``.
        """
        return f"{self.command} --if-selected" if self.option else self.command


START_STEPS: tuple[StartStep, ...] = (
    StartStep("ft-brew-floor", since="M5c-2", homebrew_only=True),
    StartStep("ft-ensure-claude-code", since="M5c-3", option="claude-code"),
)
