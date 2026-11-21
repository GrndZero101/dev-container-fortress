# Workstation Usage

This guide covers what sits underneath the one-command install: the
host-target model, converging a machine with `ft host ...`, and bootstrapping
other machines over SSH.

> [!TIP]
> To set up the machine you are on, follow the
> [quickstart](../quickstart.md). The
> [support matrix](../../README.md#support-matrix) records which platforms
> work today.

Every command and flag is in the
[`ft host` reference](../reference/cli.md#ft-host).

## Host Targets

A host target is a named machine that `ft` can probe and converge. Your
targets live in
`${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml`. `ft`
layers that file over the repo's
[`ft/targets/hosts.example.toml`](../../ft/targets/hosts.example.toml), which
defines `localhost` and the disposable Docker SSH targets, so those work with
no setup.

To add your own targets, start from the example:

```zsh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress"
cp ft/targets/hosts.example.toml \
  "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml"
```

A target records:

- a name
- a kind, such as `workstation`, `cloud`, or `docker`
- a connection type, `local` or `ssh`
- the SSH user, host, and port when needed
- an auth method and a stable SSH key name
- tags for grouping and selection

Inspect them with:

```zsh
ft host list
ft host show localhost
ft host inventory
```

`ft host inventory` prints the Ansible inventory that `ft` generates from the
same model.

## Converge This Machine

The installer's `host` mode ends by converging `localhost`. Run the same step
directly at any time:

```zsh
ft host bootstrap localhost --check -K
ft host bootstrap localhost -K
ft host validate localhost -K
```

- `--check` previews the run where the Ansible modules support check mode
- `-K` asks for your `sudo` password
- `validate` runs a check-mode pass, a real pass, and a second pass that must
  report no changes
- `--mode workspace` stops after the native packages and Docker, for a thin
  host that runs a [workspace](workspace-usage.md)

Under the hood, `ft host bootstrap` renders a temporary inventory and runs
`ansible/playbooks/host.yml` against it. The
[Ansible README](../../ansible/README.md) documents that layer.

## Bootstrap a Remote Ubuntu Host

The remote host can be an EC2 instance, a VM, or an existing workstation
reachable over SSH. For a disposable EC2 host that Terraform creates and
registers for you, use the [EC2 development loop](ec2-development-loop.md)
instead.

Add a target to your `hosts.toml`, based on `ubuntu-remote-example`:

- set `name` to something stable, such as `dev-fortress-ec2-dev`
- set `host` to the DNS name or IP address
- keep `user = "ubuntu"` for a stock Ubuntu cloud image
- keep `auth_method = "ssh_key"` and set `ssh_key_name` to a name for this
  target
- keep `ansible_python_interpreter = "/usr/bin/python3"` unless the host needs
  another interpreter

Then run:

```zsh
ft host show dev-fortress-ec2-dev
ft host ssh-key dev-fortress-ec2-dev
ft host ssh-key-enroll dev-fortress-ec2-dev
ft host doctor dev-fortress-ec2-dev --probe
ft host bootstrap dev-fortress-ec2-dev --check
ft host bootstrap dev-fortress-ec2-dev
```

Each step is safe to repeat:

- `ssh-key` creates the managed ed25519 key pair for the target
- `ssh-key-enroll` appends the public key on the host when it is not already
  there
- `doctor --probe` refreshes the managed known-hosts entry and proves SSH works
- `bootstrap --check` previews the run
- `bootstrap` converges the host

`ft host ssh <target>` opens a shell on the host, and
`ft host ssh-config <target> --install` writes an SSH config entry for it. On
WSL2, add `--windows` so VS Code on Windows can reach the host.

Managed keys and known-hosts files live under the Dev Fortress XDG trees, not
in `~/.ssh`.

## What Bootstrap Converges

- XDG base directories for the target user
- baseline packages on Ubuntu, Alpine, and Arch
- the native prerequisites: `python3`, `git`, `curl`, and `zsh`
- a `shell-config` clone and bootstrap, with the profile-local `zinit`
- zsh as the login shell, for remote targets and for `localhost` when the
  installer runs in `host` mode
- on Ubuntu `workstation` and `cloud` targets: Docker CE with the `buildx` and
  Compose plugins
- on Ubuntu: Homebrew and the tool pool, including `tmux`, `helix`, `neovim`,
  `yazi`, `lazygit`, `kubernetes-cli`, `pass`, `rustic`, and `git-delta`. Arch
  uses pacman instead, and Homebrew is skipped there
- on Ubuntu: a `kickstart.nvim` clone in
  `${XDG_CONFIG_HOME:-$HOME/.config}/nvim-kickstart` with an `nvim-kickstart`
  launcher, which leaves an existing `~/.config/nvim` alone
- the optional components you selected with `ft options`: Claude Code, and at
  most one tmux profile

[`ansible/roles/README.md`](../../ansible/roles/README.md) lists the roles and
which files they manage.

> [!NOTE]
> Docker without `sudo` needs a new login after the Docker role adds your user
> to the `docker` group. Open a new terminal or log in again; Ubuntu 26.04
> ships no `newgrp` or `sg`.

## Not Covered Yet

- host-side corporate CA support. It exists only for image builds; see
  [Container Usage](container-usage.md#optional-corporate-ca-support)
- macOS host convergence
- editor configuration beyond the kickstart Neovim launcher

## Disposable SSH Targets

The Ubuntu, Alpine, and Arch test containers also run as SSH hosts, so the
same `ft host ...` flow can be rehearsed against them without a real machine.
See [Container Usage](container-usage.md#disposable-ssh-targets) and the
[target validation runbook](../project/target-validation.md).
