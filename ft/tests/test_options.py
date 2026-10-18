"""Tests for optional host bootstrap components."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ft.cli import app
from ft.options import (
    OPTIONS_ENV,
    OptionSelection,
    load_saved_options,
    option_ansible_vars,
    options_config_path,
    parse_option_names,
    resolve_options,
    save_options,
)
from typer.testing import CliRunner

runner = CliRunner()

CLAUDE_VAR = "dev_container_fortress_claude_code_manage"
TMUX_VAR = "dev_container_fortress_tmux_profile"


@pytest.fixture(autouse=True)
def isolated_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the options config at a temporary XDG tree and clear the variable.

    Returns:
        The isolated options.toml path, which does not exist yet.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv(OPTIONS_ENV, raising=False)
    return options_config_path()


def _write_local_host_config(tmp_path: Path) -> Path:
    """Write a host config with only the local target.

    Returns:
        The config path.
    """
    config_path = tmp_path / "hosts.toml"
    config_path.write_text(
        '[[targets]]\nname = "localhost"\nkind = "workstation"\n'
        'connection = "local"\nauth_method = "local"\n',
        encoding="utf-8",
    )
    return config_path


def test_parse_option_names_accepts_lists_commas_and_none() -> None:
    """Names may be repeated or comma-separated, and none selects nothing."""
    assert parse_option_names(["Claude-Code, claude-code"]) == ("claude-code",)
    assert parse_option_names("none") == ()
    assert parse_option_names([]) == ()


@pytest.mark.parametrize("value", ["codex", "none,claude-code"])
def test_parse_option_names_rejects_unknown_and_mixed_none(value: str) -> None:
    """Unknown names and none mixed with names fail with the supported list."""
    with pytest.raises(ValueError):
        parse_option_names(value)


def test_default_selects_nothing() -> None:
    """With no flag, variable, or config, nothing optional is enabled."""
    assert resolve_options() == OptionSelection((), "default")
    assert option_ansible_vars(()) == {CLAUDE_VAR: False, TMUX_VAR: "none"}


def test_tmux_profiles_are_one_pick_one_choice() -> None:
    """One tmux profile sets the shared variable; two in one selection fail."""
    assert parse_option_names("tmux-raidboss,claude-code") == (
        "claude-code",
        "tmux-raidboss",
    )
    assert option_ansible_vars(("tmux-raidboss",)) == {
        CLAUDE_VAR: False,
        TMUX_VAR: "raidboss",
    }
    assert option_ansible_vars(("tmux-minimal",))[TMUX_VAR] == "minimal"
    with pytest.raises(ValueError, match="choose one of tmux-minimal and tmux-full"):
        parse_option_names(["tmux-full", "tmux-minimal"])


def test_precedence_flag_then_environment_then_config(
    isolated_options: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flag beats the variable, which beats the saved config."""
    save_options(("claude-code",))
    assert resolve_options() == OptionSelection(("claude-code",), "config")

    monkeypatch.setenv(OPTIONS_ENV, "none")
    assert resolve_options() == OptionSelection((), "environment")

    assert resolve_options(["claude-code"]) == OptionSelection(("claude-code",), "flag")


def test_saved_options_round_trip_and_validate(isolated_options: Path) -> None:
    """The saved file round-trips, and bad content fails clearly."""
    assert load_saved_options() is None
    save_options(())
    assert load_saved_options() == ()

    isolated_options.write_text('enabled = ["codex"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown option"):
        load_saved_options()
    isolated_options.write_text("enabled = [\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid TOML"):
        load_saved_options()


def test_options_command_lists_the_catalog_and_source() -> None:
    """`ft options` shows each option and where the selection came from."""
    result = runner.invoke(app, ["options"])

    assert result.exit_code == 0
    assert "claude-code" in result.stdout
    assert "(default)" in result.stdout


def test_options_pick_requires_a_terminal() -> None:
    """The picker fails clearly without a terminal instead of hanging."""
    result = runner.invoke(app, ["options", "pick"])

    assert result.exit_code != 0
    assert "needs a terminal" in result.output


def test_options_pick_saves_the_selection(
    isolated_options: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confirmed pick is saved; a cancelled one leaves the file alone."""
    monkeypatch.setattr("ft.cli._interactive_terminal", lambda: True)
    monkeypatch.setattr(
        "ft.cli._interactive_multi_select", lambda *args, **kwargs: ["claude-code"]
    )
    assert runner.invoke(app, ["options", "pick"]).exit_code == 0
    assert load_saved_options() == ("claude-code",)

    monkeypatch.setattr("ft.cli._interactive_multi_select", lambda *a, **k: None)
    assert runner.invoke(app, ["options", "pick"]).exit_code == 1
    assert load_saved_options() == ("claude-code",)


def test_options_pick_reopens_on_two_tmux_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two tmux profiles reopen the picker with the checks kept, then save."""
    monkeypatch.setattr("ft.cli._interactive_terminal", lambda: True)
    picks = iter([["tmux-full", "tmux-raidboss"], ["tmux-full"]])
    seen: list[tuple[str, ...]] = []

    def fake_select(*args: object, **kwargs: object) -> list[str]:
        seen.append(kwargs["preselected"])  # type: ignore[arg-type]
        return next(picks)

    monkeypatch.setattr("ft.cli._interactive_multi_select", fake_select)
    result = runner.invoke(app, ["options", "pick"])

    assert result.exit_code == 0
    assert "choose one of" in result.output
    assert seen == [(), ("tmux-full", "tmux-raidboss")]
    assert load_saved_options() == ("tmux-full",)


def test_host_inventory_renders_option_vars(
    tmp_path: Path, isolated_options: Path
) -> None:
    """The inventory carries one boolean per option, from the saved selection."""
    config_path = _write_local_host_config(tmp_path)
    save_options(("claude-code",))

    result = runner.invoke(
        app, ["host", "inventory", "--config", str(config_path), "--json"]
    )

    assert result.exit_code == 0
    group = json.loads(result.stdout)["all"]["children"]["dev_fortress"]
    assert group["vars"] == {CLAUDE_VAR: True, TMUX_VAR: "none"}


@pytest.mark.parametrize(
    ("args", "expected"),
    [([], "false"), (["--options", "claude-code"], "true")],
)
def test_host_bootstrap_passes_options_to_ansible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    expected: str,
) -> None:
    """Bootstrap renders the selection into the inventory it hands Ansible."""
    config_path = _write_local_host_config(tmp_path)
    inventories: list[str] = []

    def fake_stream(
        command: list[str], *, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        inventories.append(Path(command[2]).read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ft.cli._run_streaming_command", fake_stream)
    monkeypatch.setattr("ft.cli.shutil.which", lambda name: "/usr/bin/ansible-playbook")

    result = runner.invoke(
        app,
        ["host", "bootstrap", "localhost", "--config", str(config_path), *args],
    )

    assert result.exit_code == 0
    assert f"{CLAUDE_VAR}: {expected}" in inventories[0]


def test_host_bootstrap_rejects_unknown_options(tmp_path: Path) -> None:
    """An unknown option fails before Ansible runs."""
    config_path = _write_local_host_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "host",
            "bootstrap",
            "localhost",
            "--config",
            str(config_path),
            "--options",
            "codex",
        ],
    )

    assert result.exit_code == 2
    assert "unknown option" in result.output
