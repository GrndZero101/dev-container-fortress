"""Typer CLI for ft."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from rich.console import Console
from rich.table import Table
import typer

from ft.installer import InstallPlan, build_plan, install_tool
from ft.manifest import load_manifest
from ft.models import ToolDefinition, ToolManifest
from ft.platforms import detect_architecture, detect_system
from ft.settings import FtSettings

app = typer.Typer(
    add_completion=False,
    help="Install pinned tooling from a reusable manifest.",
)

console = Console()


def _is_writable_directory(path: Path) -> bool:
    """Return whether the directory exists or can be created by the current user."""
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent, os.W_OK)


def _default_user_install_root() -> Path:
    """Return the fallback user-local binary directory."""
    return Path.home() / ".local" / "bin"


def _effective_install_root(
    tool_install_root: Path,
    override_install_root: Path | None,
) -> Path:
    """Return the install root to use for the current execution context."""
    if override_install_root is not None:
        return override_install_root
    if _is_writable_directory(tool_install_root):
        return tool_install_root
    return _default_user_install_root()


def _resolve_runtime_options(
    *,
    manifest: Path | None,
    target: str | None,
    system_name: str | None,
    architecture: str | None,
    install_root: Path | None,
    healthcheck: bool | None,
) -> dict[str, object]:
    """Resolve CLI options with environment-backed defaults."""
    settings = FtSettings()
    return {
        "manifest": manifest or settings.manifest,
        "target": target or settings.target,
        "system_name": system_name or settings.system or detect_system(),
        "architecture": architecture or settings.architecture or detect_architecture(),
        "install_root": install_root or settings.install_root,
        "healthcheck": settings.healthcheck if healthcheck is None else healthcheck,
    }


def _selected_tools(
    manifest: ToolManifest,
    requested_tool: str | None,
) -> list[tuple[str, ToolDefinition]]:
    """Resolve the tool subset requested by the user."""
    if requested_tool is None:
        return manifest.enabled_tools()
    if requested_tool not in manifest.tools:
        raise typer.BadParameter(f"unknown tool: {requested_tool}", param_hint="--tool")
    return [(requested_tool, manifest.tools[requested_tool])]


def _render_plan(
    plan: InstallPlan,
    *,
    target: str,
    install_root: Path | None,
) -> None:
    """Render one resolved plan to the console."""
    effective_install_root = _effective_install_root(plan.tool.install_root, install_root)

    table = Table(title=f"{plan.name} plan", show_header=False)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    table.add_row("target", target)
    table.add_row("version", plan.tool.version)
    table.add_row("platform", f"{plan.os_name}/{plan.architecture}")
    table.add_row("url", plan.asset.url)
    table.add_row("archive", plan.asset.archive)
    table.add_row("install_root", str(effective_install_root))
    if plan.integrity.checksum_url:
        table.add_row("checksums", plan.integrity.checksum_url)
    if plan.integrity.signature_url:
        table.add_row("signature", plan.integrity.signature_url)

    console.print(table)


@app.command()
def plan(
    tool: Annotated[str | None, typer.Option(help="Plan only the named tool.")] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
) -> None:
    """Print the resolved install plan."""
    runtime = _resolve_runtime_options(
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        healthcheck=None,
    )
    manifest_model = load_manifest(Path(runtime["manifest"]))

    for name, tool_definition in _selected_tools(manifest_model, tool):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
        )
        _render_plan(
            plan_model,
            target=str(runtime["target"]),
            install_root=runtime["install_root"],
        )


@app.command()
def install(
    tool: Annotated[str | None, typer.Option(help="Install only the named tool.")] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(help="Path to the tool manifest TOML file."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(help="Named target context for the current build or host."),
    ] = None,
    system_name: Annotated[
        str | None,
        typer.Option("--system", help="Override the detected operating system."),
    ] = None,
    architecture: Annotated[
        str | None,
        typer.Option(help="Override the detected architecture."),
    ] = None,
    install_root: Annotated[
        Path | None,
        typer.Option(help="Override the configured install root."),
    ] = None,
    healthcheck: Annotated[
        bool | None,
        typer.Option(
            "--healthcheck/--no-healthcheck",
            help="Run the configured healthcheck after installation.",
        ),
    ] = None,
) -> None:
    """Install the selected tools."""
    runtime = _resolve_runtime_options(
        manifest=manifest,
        target=target,
        system_name=system_name,
        architecture=architecture,
        install_root=install_root,
        healthcheck=healthcheck,
    )
    manifest_model = load_manifest(Path(runtime["manifest"]))

    for name, tool_definition in _selected_tools(manifest_model, tool):
        plan_model = build_plan(
            name,
            tool_definition,
            os_name=str(runtime["system_name"]),
            architecture=str(runtime["architecture"]),
            target=str(runtime["target"]),
        )
        effective_install_root = _effective_install_root(
            tool_definition.install_root,
            runtime["install_root"],
        )
        if runtime["install_root"] is None and effective_install_root != tool_definition.install_root:
            console.print(
                f"Using fallback install root {effective_install_root} because "
                f"{tool_definition.install_root} is not writable."
            )
        installed_path = install_tool(
            plan_model,
            install_root=effective_install_root,
            healthcheck=bool(runtime["healthcheck"]),
        )
        console.print(f"Installed {name} to {installed_path}")
