# Container Standards

This document defines the current container contract for
`dev-container-fortress`.

> [!IMPORTANT]
> Update this file whenever a significant container design choice changes.
> Examples: filesystem layout, runtime user model, bootstrap strategy, `uv`
> installation method, privilege model, or tool installation contract.

## Purpose

The container targets should behave like durable developer environments, not
just throwaway build images.

That means they should:

- be reproducible to build
- be non-interactive on first launch
- run day-to-day as a normal user
- follow XDG-style user layout where practical
- keep privileged setup in build-time layers
- align cleanly with VS Code devcontainers

## Runtime User Contract

- The final runtime container should default to a normal non-root user.
- The current standard runtime user is `vscode`.
- Root may be used during Docker build steps for package installation and system
  setup.
- `sudo` should be available for the runtime user for developer-environment
  workflows, but the container should not launch as root by default.

## Filesystem Layout Contract

- Prefer the runtime user's home directory and XDG paths over custom
  application-owned directories such as `/opt/<project>`.
- The current expected runtime environment is:
  - `HOME=/home/vscode`
  - `XDG_CACHE_HOME=$HOME/.cache`
  - `XDG_DATA_HOME=$HOME/.local/share`
  - `XDG_CONFIG_HOME=$HOME/.config`
  - `PATH=$HOME/.local/bin:$PATH`
- Repo-specific runtime data may live below an XDG-owned subtree such as
  `$XDG_DATA_HOME/dev-container-fortress/`.

## Bootstrap Contract

- Do not use `pip install uv` against distro-managed system Python in container
  builds.
- Build-time `uv` should come from Astral's official container image.
- Runtime `uv` should be installed with Astral's shell installer so the runtime
  user can use `uv` as intended inside a persistent environment.
- Managed Python versions required by repo-owned tools should be installed via
  `uv`, not assumed from the distro Python version.
- Optional corporate CA trust should be an explicit opt-in, not a default behavior.
- When enabled, corporate CA material should come from an explicitly provided directory of PEM-formatted `.crt` files.
- The build should validate those `.crt` files before installation and install them into the distro trust store before repo-managed network fetches such as the Astral installer or downloader-managed tool downloads.

## Tool Installation Contract

- User-facing Python CLI tools should prefer `uv tool install` in the final
  runtime image.
- Tool executables should land in the user's XDG-aligned bin directory through
  `uv` defaults.
- Repo-owned runtime tool configuration should be explicit and data-driven.
- External binary downloads should prefer pinned versions and checksum
  verification.

## Shell Contract

- The runtime shell experience should be non-interactive on first launch.
- If Zsh is the default shell, minimal startup files should be pre-created so
  `zsh-newuser-install` does not block container startup.
- Shell behavior itself still belongs in `shell-config`, not in this repository.

## Devcontainer Contract

- `.devcontainer/` should remain a thin wrapper around the container target.
- The repository may expose multiple devcontainer definitions when it supports multiple container targets.
- The current standard definitions are `.devcontainer/ubuntu/devcontainer.json` and `.devcontainer/alpine/devcontainer.json`.
- Each devcontainer should use the same runtime user as its container image.
- Post-create behavior should validate or lightly bootstrap the environment, not duplicate the core image provisioning logic.
- Devcontainer build args may expose opt-in environment hooks such as `DEV_CONTAINER_FORTRESS_CA_CERT_DIR` when they are needed for corporate networks.

## Portability Contract

- Ubuntu and Alpine should converge on the same runtime model where practical.
- Differences between distro package names or bootstrap details should not
  change the higher-level container contract without updating this document.

## Current Ubuntu Reference

The Ubuntu image currently implements this contract by:

- using Astral's distroless image for build-time `uv`
- installing runtime `uv` with Astral's installer
- creating a non-root `vscode` user
- using XDG-style home-directory layout
- installing `ft` as a `uv` tool
- installing `tenv` through `ft`

## Current Alpine Reference

The Alpine image should follow the same contract as Ubuntu by:

- using Astral's distroless image for build-time `uv`
- installing runtime `uv` with Astral's installer
- creating a non-root `vscode` user
- using XDG-style home-directory layout
- installing `ft` as a `uv` tool
- installing `tenv` through `ft`
