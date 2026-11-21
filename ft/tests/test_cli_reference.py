"""Help-text coverage tests for the ft command tree.

``docs/reference/cli.md`` is generated from the Typer app, so a command or
parameter without help text becomes a blank entry in the published reference.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import click
import typer
from ft.cli import app


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
    reference = Path(__file__).parents[2] / "docs" / "reference" / "cli.md"
    absolute_defaults = [
        line for line in reference.read_text().splitlines() if "[default: /" in line
    ]
    assert not absolute_defaults, "absolute default paths: " + "; ".join(
        absolute_defaults
    )
