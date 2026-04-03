# Workstation Usage

This document describes how to use `dev-container-fortress` directly on a workstation.

> [!IMPORTANT]
> The direct workstation path is still in scaffold phase.
> The repository has local bootstrap, Brew bundle definitions, and Ansible structure, but the full host provisioning flow is not complete yet.

## Current Status

Works today:

- local workspace bootstrap with `uv`
- local development and testing of the `ft` tool
- repository linting and tests

Scaffolded but not complete yet:

- full Ansible-driven workstation provisioning
- host-side `shell-config` cloning and bootstrap integration
- tmux integration
- host-side corporate CA support

## Local Workspace Bootstrap

From the repository root:

```zsh
cd /home/timl/projects/tboss/dev-container-fortress
zsh ./bootstrap.zsh
```

This will:

1. install `uv` if it is missing
2. create or refresh the local project environment
3. install the Python dependencies needed for local development

## Validate the Local Tooling

After bootstrap:

```zsh
.venv/bin/ruff check ft
.venv/bin/pytest ft/tests
.venv/bin/ft plan --manifest /home/timl/projects/tboss/dev-container-fortress/ft/tools/tools.toml --target ubuntu --tool tenv
```

If you want to test installation on your workstation without writing into system paths, either let `ft` fall back to `~/.local/bin` automatically or pass an explicit user-writable install root.

## Direct Host Provisioning

The long-term intended workstation flow is:

1. install Ansible prerequisites
2. run the host playbook
3. install Homebrew where needed
4. install the Brew bundle
5. install `tenv`
6. install and bootstrap `shell-config`
7. install tmux and other user tools

That flow is not fully implemented yet.

See [Ansible README](/home/timl/projects/tboss/dev-container-fortress/ansible/README.md) for the current host-automation layer status.

## Corporate CA Status

Host-side corporate CA support is not implemented yet.

> [!NOTE]
> Corporate CA support currently exists only for container and devcontainer builds. See [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) and [Devcontainer Usage](/home/timl/projects/tboss/dev-container-fortress/docs/devcontainer-usage.md).
