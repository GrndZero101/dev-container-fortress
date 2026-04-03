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
├── devcontainer/
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
- install `terraform`
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
- `terraform`

### `containers/`

Container build logic for:

- Ubuntu
- Alpine

The container strategy is intentionally different from the host strategy:

- use distro packages for low-level system prerequisites
- use a Python + `uv` installer for pinned userland binaries
- avoid running Homebrew inside containers

### `devcontainer/`

VS Code wrapping for the container image, including:

- `devcontainer.json`
- extension recommendations
- container-specific mounts and post-create steps

## Planned Bootstrap Flow

### Direct host install

1. Install Ansible prerequisites
2. Run the host playbook
3. Install Homebrew where needed
4. Install the Brew bundle
5. Install and bootstrap `shell-config`
6. Install tmux and other user tools

### Docker build

1. Build the base image from `containers/<target>/Dockerfile`
2. Install pinned CLI tools with the Python + `uv` tool installer
3. Install and bootstrap `shell-config`
4. Install tmux and environment-level configuration

### VS Code dev container

1. Reuse the Docker image or Dockerfile
2. Apply VS Code-specific configuration and extensions
3. Run post-create bootstrap steps

## Current Status

This repository is currently in scaffold phase.

The first pass provides:

- the initial repository structure
- Ansible role and playbook scaffolding
- Brew bundle scaffolding
- Dockerfile scaffolding for Ubuntu and Alpine
- a Python + `uv` tool installer skeleton
- initial VS Code devcontainer scaffolding

## Next Steps

1. Implement the Ansible roles
2. Fill out the Brew bundles
3. Implement real binary download and checksum verification in the tool installer
4. Decide the tmux component structure
5. Integrate `shell-config` bootstrap end to end

