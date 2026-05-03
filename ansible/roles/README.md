# Roles

This directory is where host bootstrap moves from thin contract checks into
real provisioning work.

Current state:

- `playbooks/host.yml` is still the thin bootstrap entrypoint
- the first convergent host roles now exist for contract validation, XDG layout,
  Ubuntu and Alpine baseline packages, shell-config bootstrap, and shell-config
  readiness reporting
- more host setup should continue to land incrementally as milestone-backed slices

Role guidance:

- keep roles small and composable
- prefer one clear responsibility per role
- keep platform-specific behavior explicit
- avoid burying high-level orchestration decisions inside deep role trees
- document required variables and assumptions near the role
- make reruns safe on already-aligned hosts
- prefer built-in Ansible modules over shell-heavy implementations where practical

What belongs in a role:

- repeatable host setup with clear ownership
- package prerequisites
- filesystem and XDG preparation
- shell-config handoff or validation
- small, testable provisioning contracts

What should stay outside a role:

- early target reachability checks
- inventory generation
- thin bootstrap flow wiring in `ft`
- one-off experimental logic that has not earned a stable contract yet

Expected early role candidates:

- `dev_fortress_target_contract`
- `dev_fortress_xdg_layout`
- `dev_fortress_ubuntu_base_packages`
- `dev_fortress_alpine_base_packages`
- `dev_fortress_native_bootstrap_prereqs`
- `dev_fortress_docker`
- `dev_fortress_shell_config_bootstrap`
- `dev_fortress_shell_config_zinit`
- `dev_fortress_login_shell`
- `dev_fortress_linuxbrew`
- `dev_fortress_neovim_kickstart`
- `dev_fortress_shell_config_ready`
- future `uv_prereqs`

As roles land, update this file so it reflects current reality rather than a
wishlist.

## Current Roles

### `dev_fortress_target_contract`

Validates the generated inventory contract plus the minimum gathered facts the
rest of the bootstrap flow depends on.

### `dev_fortress_xdg_layout`

Converges the target user's XDG base directories using built-in filesystem
modules.

### `dev_fortress_ubuntu_base_packages`

Linux-first package baseline for Ubuntu hosts.
Uses Ansible's package modules so reruns level-set the machine instead of
depending on imperative shell steps.

### `dev_fortress_alpine_base_packages`

Linux-first package baseline for Alpine hosts.
Uses the native `community.general.apk` module so reruns stay declarative and
aligned with Alpine's package-manager model instead of falling back to shell
wrappers.

### `dev_fortress_native_bootstrap_prereqs`

Converges the minimum native command substrate required before `shell-config`
bootstrap runs on supported Linux targets, then asserts that the substrate is
actually present. The current contract is intentionally small:
`python3`, `git`, `curl`, and `zsh`.

### `dev_fortress_docker`

Installs Docker CE on Ubuntu workstation and cloud targets using Docker's
official apt repository, converges a small managed `daemon.json`, enables the
`docker` and `containerd` services under systemd, and adds the target user to
the `docker` group. This role is intentionally not applied to disposable
`kind = "docker"` SSH targets.

### `dev_fortress_shell_config_bootstrap`

Clones `shell-config`, runs the repo-owned `csm bootstrap` entrypoint, and
persists the selected profile into the target user's XDG state directory.
This is intentionally done before Homebrew uplift so Dev Fortress can validate
the shell on a minimally prepared host first.

### `dev_fortress_shell_config_zinit`

Installs the fortress profile-local `zinit` checkout when the selected profile
expects it. The role is intentionally convergent: it installs `zinit` when it
is missing, but does not treat every bootstrap run as an implicit plugin
manager update cycle.

### `dev_fortress_login_shell`

Converges the target user's login shell to `zsh` using the native Ansible user
module. This stays configurable per target and defaults to enabled for
non-local targets so real SSH and cloud hosts actually enter the Dev Fortress
shell on login.

### `dev_fortress_linuxbrew`

Installs Linuxbrew for supported Ubuntu targets in the standard supported
prefix, persists a managed shellenv snippet, and converges the current
fortress operator tool pool after `shell-config` bootstrap.

### `dev_fortress_neovim_kickstart`

Clones `kickstart.nvim` into a parallel XDG config directory and installs a
repo-managed `nvim-kickstart` wrapper that launches Neovim with
`NVIM_APPNAME=nvim-kickstart`. This keeps the IDE-style starter config
available without overwriting an existing user-owned `~/.config/nvim`.

### `dev_fortress_shell_config_ready`

Reports whether the target currently looks ready for the later shell-config
install or current shell-config state, while keeping the boundary between Dev
Fortress-managed state and user-owned customization explicit.
