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

Implemented foundation work now available:

- host-target modeling through `ft host ...`
- XDG-aligned Dev Fortress SSH key path conventions
- generated minimal Ansible inventory output from the shared host-target model

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
5. install the `ft` zsh completion artifact into the XDG data tree

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
- `ansible-playbook --syntax-check` for the repo-owned host playbook
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

Today that playbook is intentionally thin, but it is now a real convergence
loop for the first supported Linux baselines. It proves reachability and the
shared target contract, ensures the target user's XDG base directories exist,
converges baseline packages on Ubuntu and Alpine, and reports whether baseline
tools such as `python3`, `git`, and `zsh` are present. Full workstation-style
roles are still follow-up work.

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
- shell-config readiness checks for `python3`, `git`, and `zsh`

It does not yet converge the full workstation stack such as Homebrew, tmux,
editor tooling, or shell-config installation. Those remain follow-up milestones.

## Corporate CA Status

Host-side corporate CA support is not implemented yet.

> [!NOTE]
> Corporate CA support currently exists only for container and devcontainer builds. See [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) and [Devcontainer Usage](/home/timl/projects/tboss/dev-container-fortress/docs/devcontainer-usage.md).
