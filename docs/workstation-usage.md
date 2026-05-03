# Workstation Usage

This document describes how to use `dev-container-fortress` directly on a workstation.

> [!IMPORTANT]
> The direct workstation path is still maturing, but it is no longer only scaffold.
> The current first-class local host path is Ubuntu under WSL2 using the shared
> `ft host ...` and Ansible bootstrap flow against `localhost`.

For the current WSL2-first local bootstrap path, use
[WSL Bootstrap Runbook](/home/timl/projects/github/GrndZero101/tboss/dev-container-fortress/docs/wsl-bootstrap.md).

## Current Status

Works today:

- local workspace bootstrap with `uv`
- local development and testing of the `ft` tool
- repository linting and tests
- Ubuntu WSL2 local bootstrap through `ft host bootstrap localhost`
- `shell-config` clone and bootstrap during host provisioning
- fortress profile-local `zinit` installation during host provisioning
- Ubuntu Linuxbrew uplift after the native bootstrap substrate is in place
- Ubuntu Docker CE bootstrap for `workstation` and `cloud` targets

Current host-tooling policy:

- Homebrew is the preferred steady-state source for host userland tools
- native package managers are still used for bootstrap-floor prerequisites such
  as Docker Engine and similar base dependencies
- container-specific heavy tools should live in Dev Fortress images rather than
  being treated as required host userland by default

Scaffolded but not complete yet:

- cross-platform workstation parity beyond the Ubuntu-first path
- tmux integration
- host-side corporate CA support
- full host-side validation coverage outside the currently documented Ubuntu and disposable-target loops

Implemented foundation work now available:

- host-target modeling through `ft host ...`
- XDG-aligned Dev Fortress SSH key path conventions
- generated minimal Ansible inventory output from the shared host-target model
- local-target bootstrap through `ansible_connection = "local"`

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
4. make repo-local tooling such as `pre-commit`, `pytest`, and `ruff` available through `uv run`
5. install the live `ft` CLI into the user tool path from the local checkout
6. install the `ft` zsh completion artifact into the XDG data tree

## Validate the Local Tooling

After bootstrap:

```zsh
.venv/bin/ruff check ft
.venv/bin/pytest ft/tests
.venv/bin/ft plan --manifest /home/timl/projects/tboss/dev-container-fortress/ft/tools/tools.toml --target ubuntu --tool tenv
uv run pre-commit run --all-files
pre-commit run markdownlint-cli2 --all-files
```

If you want to test installation on your workstation without writing into system paths, either let `ft` fall back to `~/.local/bin` automatically or pass an explicit user-writable install root.

To make the same basic sanity checks run automatically before commits:

```zsh
uv run pre-commit install
```

The current baseline keeps the hooks intentionally light:

- file hygiene checks for YAML, JSON, merge markers, trailing whitespace, and EOF handling
- `markdownlint-cli2` for repo Markdown, aligned with the VS Code markdownlint ecosystem
- `ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" ansible-playbook --syntax-check`
  for the repo-owned host playbook
- `ansible-lint` for the Ansible tree under `ansible/`
- `ruff` lint and format for Python
- `zsh -n` syntax checks for repo-owned Zsh entrypoints under `scripts/` plus `bootstrap.zsh`

If you want to refresh the installed completion artifact manually after CLI
changes, use:

```zsh
uv run ft completion install zsh
```

## Host Target Foundation

The workstation path now includes the first thin host-target control plane under
`ft host ...`.

Start from the repo example:

```zsh
mkdir -p ${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress
cp /home/timl/projects/tboss/dev-container-fortress/ft/targets/hosts.example.toml \
  ${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml
```

Then inspect it with:

```zsh
uv run ft host list
uv run ft host show localhost
uv run ft host inventory
uv run ft host ssh-key-path dev-fortress-ubuntu
uv run ft host ssh-key-path dev-fortress-alpine
uv run ft host doctor localhost
uv run ft host ssh-key dev-fortress-ubuntu
uv run ft host ssh-key dev-fortress-alpine
uv run ft host ssh-key-enroll dev-fortress-ubuntu
uv run ft host ssh-key-enroll dev-fortress-alpine
uv run ft host doctor dev-fortress-ubuntu --probe
uv run ft host doctor dev-fortress-alpine --probe
uv run ft host bootstrap localhost --check
```

The current target model is intentionally small:

- named targets
- target kind such as `workstation` or `docker`
- connection type such as `local` or `ssh`
- SSH user, host, and port when needed
- auth method and stable SSH key name
- lightweight tags for grouping and future selection

This does not yet fully provision hosts or handle long-term SSH trust policy.
It does now support managed key generation and explicit public-key enrollment so
SSH reachability, inventory shape, and future Ansible bootstrap can share one
target contract before the broader workstation flow grows deeper.

For disposable Docker SSH targets, Dev Fortress now also maintains a managed
known-hosts file under `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/known_hosts/`
so probe and bootstrap no longer rely on discarding host trust state entirely.

## Direct Host Provisioning

The long-term intended workstation flow is:

1. install Ansible prerequisites
2. run the host playbook
3. install Homebrew where needed
4. install the Brew bundle
5. install `tenv`
6. install and bootstrap `shell-config`
7. install operator and testing helpers such as `gum` and `bats-core`
8. install tmux and other user tools

That flow is not fully implemented yet.

The current thin bootstrap direction is now:

```zsh
uv run ft host ssh-key dev-fortress-ubuntu
uv run ft host ssh-key dev-fortress-alpine
uv run ft container up ubuntu
uv run ft container up alpine
uv run ft host bootstrap localhost --check
uv run ft host doctor dev-fortress-ubuntu --probe
uv run ft host doctor dev-fortress-alpine --probe
uv run ft host bootstrap dev-fortress-ubuntu --ensure-ssh-keys
uv run ft host bootstrap dev-fortress-alpine --ensure-ssh-keys
```

Under the hood, `ft host bootstrap` renders a temporary inventory and runs:

```zsh
ansible-playbook \
  -i <(uv run ft host inventory) \
  /home/timl/projects/tboss/dev-container-fortress/ansible/playbooks/host.yml
```

Today that playbook is still intentionally narrow, but it is now a real
convergence loop for the first supported Linux baselines. It proves
reachability and the shared target contract, ensures the target user's XDG
base directories exist, converges baseline packages on Ubuntu and Alpine,
converges the native bootstrap substrate, installs Docker CE on Ubuntu
`workstation` and `cloud` targets, clones and bootstraps `shell-config`,
installs the fortress profile-local `zinit` checkout, applies Ubuntu Linuxbrew
uplift where enabled, and reports current readiness state for handoff. Full
workstation-style roles such as tmux and editor automation are still follow-up
work.

See [Ansible README](/home/timl/projects/tboss/dev-container-fortress/ansible/README.md) for the current host-automation layer status.

> [!NOTE]
> For the disposable Ubuntu and Alpine test targets, `ft container up <target>`
> can now authorize the managed public key automatically when the matching
> `ft host ssh-key <target>` command has already been run. `ft host
> ssh-key-enroll` remains useful for non-container or already-reachable remote
> targets.

## First Remote Ubuntu Host

The next intended operator step after the disposable Docker targets is a real
Ubuntu host reachable over SSH. That can be an EC2 instance, a VM, or an
existing workstation that is already broadly aligned with the Dev Fortress
baseline.

Start by copying the example host file into your user config area and adding a
real target based on `ubuntu-remote-example`:

```zsh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress"
cp /home/timl/projects/tboss/dev-container-fortress/ft/targets/hosts.example.toml \
  "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml"
```

Adjust the copied target so it matches the real host:

- set `name` to something stable such as `dev-fortress-ec2-dev`
- set `host` to the host DNS name or IP address
- keep `user = "ubuntu"` for a stock Ubuntu cloud image unless your image uses a different default
- keep `auth_method = "ssh_key"` and set `ssh_key_name` to a target-specific name
- keep `ansible_python_interpreter = "/usr/bin/python3"` unless the host needs a different interpreter path

Then run the canonical remote-host flow:

```zsh
uv run ft host show dev-fortress-ec2-dev
uv run ft host ssh-key dev-fortress-ec2-dev
uv run ft host ssh-key-enroll dev-fortress-ec2-dev
uv run ft host doctor dev-fortress-ec2-dev --probe
uv run ft host bootstrap dev-fortress-ec2-dev --check
uv run ft host bootstrap dev-fortress-ec2-dev
```

That sequence is intentionally convergent rather than one-shot:

- `ssh-key` creates the managed `dev_fortress_ed25519` keypair for that target name
- `ssh-key-enroll` appends the matching public key when it is not already present
- `doctor --probe` refreshes managed trust state and proves transport
- `bootstrap --check` previews convergence safely where the underlying modules support check mode
- `bootstrap` applies the first real host roles and should be safe to rerun on an already aligned host

Today the real host loop converges:

- XDG base directories for the target user
- baseline package prerequisites on supported Linux families such as Ubuntu and Alpine
- shell-config clone and bootstrap
- fortress profile-local `zinit` installation
- login-shell convergence to `zsh` for remote SSH targets
- Docker CE plus the `buildx` and Compose plugins on Ubuntu workstation/cloud targets
- Ubuntu Linuxbrew bootstrap and the current fortress-facing formula set

The current Ubuntu/WSL Linuxbrew tool pool now includes a broader operator
baseline such as `tmux`, `helix`, `neovim`, `yazi`, `lazygit`,
`kubernetes-cli`, `gopass`, `pass`, `rustic`, `syncthing`, `television`,
`git-delta`, and the existing shell-facing tools.

For Neovim specifically, host bootstrap now also clones
`kickstart.nvim` into `${XDG_CONFIG_HOME:-$HOME/.config}/nvim-kickstart`
and installs an `nvim-kickstart` launcher in `${HOME}/.local/bin`. That keeps
the IDE-style starter config available without overwriting an existing
`~/.config/nvim`.

It does not yet converge the full workstation stack such as tmux
configuration/integration, editor configuration, corporate CA handling, or
broader non-Ubuntu workstation parity. Those remain follow-up milestones.

> [!NOTE]
> Docker access without `sudo` still depends on refreshed group membership after
> the bootstrap run. On a fresh host, use `newgrp docker` or log in again after
> the Docker role has added your user to the `docker` group.

## Corporate CA Status

Host-side corporate CA support is not implemented yet.

> [!NOTE]
> Corporate CA support currently exists only for container and devcontainer builds. See [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) and [Devcontainer Usage](/home/timl/projects/tboss/dev-container-fortress/docs/devcontainer-usage.md).
