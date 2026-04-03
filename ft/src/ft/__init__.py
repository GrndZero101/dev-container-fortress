"""CLI entrypoint package for the ft installer."""

from ft.cli import app


def main() -> None:
    """Run the Typer application."""
    app()
