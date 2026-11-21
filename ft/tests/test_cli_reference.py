"""Help-text coverage tests for the ft command tree.

``docs/reference/cli.md`` is generated from the Typer app, so a command or
parameter without help text becomes a blank entry in the published reference.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import click
import pytest
import typer
from ft.cli import app
from typer.testing import CliRunner

REFERENCE = Path(__file__).parents[2] / "docs" / "reference" / "cli.md"

# The main day-to-day commands, whose help must end with a worked example.
MAIN_COMMANDS = (
    "host list",
    "host doctor",
    "host bootstrap",
    "host validate",
    "host ssh",
    "host ssh-config",
    "workspace build",
    "workspace pull",
    "workspace up",
    "workspace enter",
    "workspace status",
    "workspace down",
    "workspace exec",
    "workspace validate",
    "container build",
    "container up",
    "container enter",
    "container status",
    "container exec",
    "container validate",
    "container down",
    "container refresh",
    "workbench init",
    "workbench render",
    "workbench clone",
    "workbench list",
)


def _walk(command: click.Command, path: str) -> Iterator[tuple[str, click.Command]]:
    """Yield every command in a Click tree with its full invocation path.

    Args:
        command: The Click command or group to walk.
        path: The invocation path of ``command``, such as ``ft workspace``.

    Yields:
        Pairs of invocation path and command, parents before children.
    """
    yield path, command
    if isinstance(command, click.Group):
        for name, child in sorted(command.commands.items()):
            yield from _walk(child, f"{path} {name}")


def test_every_command_and_parameter_has_help_text() -> None:
    """Every ft command, option, and argument documents itself."""
    missing: list[str] = []
    for path, command in _walk(typer.main.get_command(app), "ft"):
        if not (command.help or "").strip():
            missing.append(path)
        for param in command.params:
            if not (getattr(param, "help", None) or "").strip():
                missing.append(f"{path} <{param.name}>")
    assert not missing, "missing help text: " + ", ".join(missing)


def test_command_help_has_no_docstring_sections() -> None:
    """Command docstrings omit Google-style sections.

    Typer prints a command's whole docstring as its description, so an
    ``Args:`` section would appear verbatim in ``--help`` and the reference.
    """
    sections = ("Args:", "Returns:", "Raises:", "Yields:")
    offenders = [
        path
        for path, command in _walk(typer.main.get_command(app), "ft")
        if any(section in (command.help or "") for section in sections)
    ]
    assert not offenders, "docstring sections in command help: " + ", ".join(offenders)


def test_reference_has_no_absolute_default_paths() -> None:
    """The committed reference renders the same on every machine.

    A default built from the checkout or home directory embeds an absolute
    path, which differs between a workstation and CI and fails the render
    check. Give such options a ``show_default`` label instead.
    """
    absolute_defaults = [
        line for line in REFERENCE.read_text().splitlines() if "[default: /" in line
    ]
    assert not absolute_defaults, "absolute default paths: " + "; ".join(
        absolute_defaults
    )


def _squash(text: str) -> str:
    """Collapse whitespace so wrapped help text compares as one line.

    Args:
        text: Help or reference text, possibly wrapped across lines.

    Returns:
        The text with every whitespace run replaced by one space.
    """
    return " ".join(text.split())


def _has_example(text: str, command: str) -> bool:
    """Report whether text carries a ``For example`` line for one command.

    Args:
        text: Whitespace-squashed help or reference text.
        command: Command path below ``ft``, such as ``host list``.

    Returns:
        True when the example invokes exactly ``command``, with or without
        arguments.
    """
    lead = f"For example, `ft {command}"
    return f"{lead} " in text or f"{lead}`" in text


@pytest.mark.parametrize("command", MAIN_COMMANDS)
def test_main_command_help_example(command: str) -> None:
    """Each main command's ``--help`` shows a worked ``For example`` line."""
    result = CliRunner().invoke(
        app, [*command.split(), "--help"], env={"COLUMNS": "200"}
    )
    assert result.exit_code == 0, result.output
    assert _has_example(_squash(result.output), command), result.output


def test_reference_shows_main_command_help_example() -> None:
    """The generated reference carries each main command's example."""
    reference = _squash(REFERENCE.read_text())
    missing = [
        command for command in MAIN_COMMANDS if not _has_example(reference, command)
    ]
    assert not missing, "examples missing from cli.md: " + ", ".join(missing)
