"""Tests for the ft identity step."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ft.cli import app
from ft.identity import GitIdentity, read_identity, resolve_identity, validate_email
from typer.testing import CliRunner

from ft import cli

runner = CliRunner()


@pytest.fixture
def git_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point Git's global config at a temporary file and clear identity inputs.

    Returns:
        The temporary global config path.
    """
    config = tmp_path / "gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for variable in (
        "DEV_CONTAINER_FORTRESS_GIT_NAME",
        "DEV_CONTAINER_FORTRESS_GIT_EMAIL",
        "DEV_CONTAINER_FORTRESS_FORGE_LOGIN",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(tmp_path)
    return config


def test_resolve_identity_prefers_explicit_values_then_current() -> None:
    """Explicit values replace current ones, and prompts fill only gaps."""
    current = GitIdentity(name="Old", email="")
    prompted: list[str] = []

    def prompt(label: str, default: str) -> str:
        prompted.append(label)
        return "new@example.com"

    resolved = resolve_identity(current, name=None, email=None, prompt=prompt)

    assert resolved == GitIdentity(name="Old", email="new@example.com")
    assert prompted == ["Git user.email"]
    assert resolve_identity(
        current, name="New", email=None, prompt=None
    ) == GitIdentity(name="New")


@pytest.mark.parametrize(
    ("email", "valid"),
    [
        ("1+me@users.noreply.github.com", True),
        ("me@example.com", True),
        ("me", False),
        ("@example.com", False),
        ("me@", False),
        ("me @example.com", False),
    ],
)
def test_validate_email(email: str, valid: bool) -> None:
    """Email validation accepts plain and noreply addresses only."""
    assert validate_email(email) is valid


def test_identity_skips_without_blocking_when_not_interactive(git_home: Path) -> None:
    """A non-interactive run with no identity skips and prints the commands."""
    result = runner.invoke(app, ["identity"])

    assert result.exit_code == 0, result.output
    assert "skipping" in result.output
    assert "git config --global user.email" in result.output
    assert not git_home.exists()


def test_identity_sets_global_values_from_environment(
    git_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment variables set the global identity non-interactively."""
    monkeypatch.setenv("DEV_CONTAINER_FORTRESS_GIT_NAME", "Ada Lovelace")
    monkeypatch.setenv("DEV_CONTAINER_FORTRESS_GIT_EMAIL", "ada@example.com")

    result = runner.invoke(app, ["identity"])

    assert result.exit_code == 0, result.output
    assert "Set Git identity (global)" in result.output
    assert read_identity(local=False) == GitIdentity("Ada Lovelace", "ada@example.com")

    rerun = runner.invoke(app, ["identity"])
    assert "Set Git identity" not in rerun.output
    assert "Ada Lovelace <ada@example.com>" in rerun.output


def test_identity_keeps_existing_identity_without_explicit_values(
    git_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing identity is kept and never prompted for again."""
    git_home.write_text("[user]\n\tname = Kept\n\temail = kept@example.com\n")
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    monkeypatch.setattr(
        cli, "_prompt_identity_field", lambda *_: pytest.fail("should not prompt")
    )

    result = runner.invoke(app, ["identity"])

    assert result.exit_code == 0, result.output
    assert read_identity(local=False) == GitIdentity("Kept", "kept@example.com")


def test_identity_reports_previous_value_when_replaced(git_home: Path) -> None:
    """Replacing an identity names the old value instead of overwriting silently."""
    git_home.write_text("[user]\n\tname = Old\n\temail = old@example.com\n")

    result = runner.invoke(app, ["identity", "--email", "new@example.com"])

    assert result.exit_code == 0, result.output
    assert "was Old <old@example.com>" in result.output
    assert read_identity(local=False) == GitIdentity("Old", "new@example.com")


def test_identity_prompts_for_missing_fields_on_a_terminal(
    git_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal run prompts only for the missing fields."""
    git_home.write_text("[user]\n\tname = Ada\n")
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(app, ["identity"], input="not-an-email\nada@example.com\n")

    assert result.exit_code == 0, result.output
    assert "not an email address" in result.output
    assert "noreply" in result.output
    assert read_identity(local=False) == GitIdentity("Ada", "ada@example.com")


def test_identity_rejects_invalid_email_and_unknown_forge(git_home: Path) -> None:
    """Invalid explicit inputs fail before anything is written."""
    assert runner.invoke(app, ["identity", "--email", "nope"]).exit_code == 2
    assert runner.invoke(app, ["identity", "--login", "bitbucket"]).exit_code == 2
    assert not git_home.exists()


def test_identity_local_writes_only_the_checkout(
    git_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--local writes the checkout config and leaves the global config alone."""
    subprocess.run(["git", "init", "-q", str(tmp_path / "repo")], check=True)
    monkeypatch.chdir(tmp_path / "repo")

    result = runner.invoke(
        app, ["identity", "--local", "--name", "Ada", "--email", "ada@example.com"]
    )

    assert result.exit_code == 0, result.output
    assert "this checkout" in result.output
    assert read_identity(local=True) == GitIdentity("Ada", "ada@example.com")
    assert not git_home.exists()


def test_identity_local_outside_a_checkout_fails(git_home: Path) -> None:
    """--local outside a Git checkout fails clearly."""
    result = runner.invoke(app, ["identity", "--local", "--name", "Ada"])

    assert result.exit_code == 1
    assert "inside a Git checkout" in result.output


def test_identity_login_skips_without_a_terminal(
    git_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A requested forge login never blocks a non-interactive run."""
    monkeypatch.setattr(cli, "forge_cli_available", lambda forge: True)
    monkeypatch.setattr(cli, "forge_logged_in", lambda forge: False)
    monkeypatch.setattr(
        cli, "run_forge_login", lambda forge: pytest.fail("should not log in")
    )

    result = runner.invoke(app, ["identity", "--login", "github"])

    assert result.exit_code == 0, result.output
    assert "needs a terminal" in result.output
