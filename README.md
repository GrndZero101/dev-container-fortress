# Dev Container Fortress

`dev-container-fortress` is the higher-level developer environment project that
orchestrates a portable workstation setup across laptops, containers, and VS Code
dev containers.

> [!NOTE]
> This repository is intended to consume [`shell-config`](../shell-config/README.md)
> as a component rather than reimplement shell behavior itself.

## Targets

- Direct installation on macOS, Linux, and WSL using Ansible plus Homebrew
- Docker container images for Ubuntu and Alpine
- VS Code dev containers layered on top of the Docker image

## Design Goals

- Fast bootstrap on a new machine
- Repeatable and auditable setup
- Shared environment shape across laptops and containers
- Clear separation between shell UX and full environment provisioning
- Support for both Intel and ARM hosts where practical

## Repository Layout

```text
dev-container-fortress/
├── ansible/
├── brew/
├── containers/
├── .devcontainer/
└── docs/
```

## Components

### `ansible/`

Host-oriented provisioning for:

- macOS
- Ubuntu
- WSL

Responsibilities:

- install Homebrew when appropriate
- install host packages
- install `uv`
- install `tenv`
- install and bootstrap `shell-config`
- install tmux and related user config

### `brew/`

Homebrew bundle definitions for direct host installs.

Use Brew as the main source of truth for host-side CLI tooling such as:

- `zsh`
- `tmux`
- `git`
- `fzf`
- `fd`
- `ripgrep`
- `eza`
- `bat`
- `zoxide`
- `starship`
- `jq`
- `yq`
- `direnv`
- `uv`
- `tenv`

### `containers/`

Container build logic for:

- Ubuntu
- Alpine

The container strategy is intentionally different from the host strategy:

- use distro packages for low-level system prerequisites
- use a Python + `uv` installer for pinned userland binaries
- avoid running Homebrew inside containers

The first container-managed DevOps tool is `tenv`, which then manages Terraform
and OpenTofu versions inside the environment.

### `.devcontainer/`

VS Code wrapping for the container images, including:

- `ubuntu/devcontainer.json`
- `alpine/devcontainer.json`
- extension recommendations
- lightweight post-create validation

## Planned Bootstrap Flow

### Local workspace bootstrap

1. Run `zsh ./bootstrap.zsh`
2. Let the bootstrap install `uv` automatically if it is missing
3. Use the synced environment for tests, linting, and local tooling work

> [!NOTE]
> Local `ft install` runs now prefer the manifest install root when it is
> writable, but automatically fall back to `~/.local/bin` for non-root local
> testing when paths such as `/usr/local/bin` are not writable.

### Direct host install

1. Install Ansible prerequisites
2. Run the host playbook
3. Install Homebrew where needed
4. Install the Brew bundle
5. Install `tenv`
6. Install and bootstrap `shell-config`
7. Install tmux and other user tools

### Docker build

1. Build the base image from `containers/<target>/Dockerfile` with `docker buildx build`
2. Install pinned CLI tools with the Python + `uv` tool installer package
3. Install `tenv`
4. Install and bootstrap `shell-config`
5. Install tmux and environment-level configuration

### VS Code dev container

1. Choose either `.devcontainer/ubuntu/devcontainer.json` or `.devcontainer/alpine/devcontainer.json`
2. Reuse the matching Dockerfile from `containers/`
3. Apply VS Code-specific configuration and extensions
4. Run a lightweight post-create validation step

## Current Status

This repository is currently in scaffold phase.

The first pass provides:

- the initial repository structure
- local `uv` bootstrap scaffolding
- an installable `ft` Python package
- downloader tests and reusable tool configuration
- Ansible role and playbook scaffolding
- Brew bundle scaffolding
- Dockerfile scaffolding for Ubuntu and Alpine
- the first real container-side tool definition for `tenv`
- initial VS Code devcontainer scaffolding for Ubuntu and Alpine

## Next Steps

1. Implement the Ansible roles
2. Add optional corporate CA support for local and container builds
3. Add SSH-enabled disposable container scaffolding for Ansible testing
4. Decide the tmux component structure
5. Integrate `shell-config` bootstrap end to end
