# Roles

This directory is where host bootstrap moves from thin contract checks into
real provisioning work.

Current state:

- `playbooks/host.yml` is still the thin bootstrap entrypoint
- the first convergent host roles now exist for contract validation, XDG layout,
  Ubuntu, Alpine, and Arch baseline packages, shell-config bootstrap, and shell-config
  readiness reporting
- more host setup should continue to land incrementally as milestone-backed slices

Host modes:

`dev_container_fortress_host_mode` picks how much of the playbook runs, and
`ft host bootstrap --mode` renders it. `host`, the default, runs every role.
`workspace` stops after the bootstrap floor (target contract, XDG layout,
native packages, bootstrap prerequisites) and Docker, for a thin host that runs
a daily-driver workspace container. It skips `shell-config`, zinit, the login
shell, Linuxbrew, Neovim kickstart, the optional tmux and Claude Code
components, and the readiness report. `install.sh --mode workspace` uses it.

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
- `dev_fortress_arch_base_packages`
- `dev_fortress_native_bootstrap_prereqs`
- `dev_fortress_docker`
- `dev_fortress_shell_config_bootstrap`
- `dev_fortress_shell_config_zinit`
- `dev_fortress_login_shell`
- `dev_fortress_linuxbrew`
- `dev_fortress_neovim_kickstart`
- `dev_fortress_claude_code`
- `dev_fortress_shell_config_ready`
- future `uv_prereqs`

As roles land, update this file so it reflects current reality rather than a
wishlist.

## Managed Versus User-Owned State

Host bootstrap converges only the state below. Rerunning it resets these paths
to the declared baseline, so do not hand-edit them.

| State | Path | Owner on rerun |
| --- | --- | --- |
| `shell-config` checkout | `${XDG_CONFIG_HOME}/shell-config` by default | Dev Fortress keeps it on the configured branch; local edits make the update fail instead of being discarded |
| Active profile marker | `${XDG_STATE_HOME}/shell-config/active-profile` | Dev Fortress rewrites it with the selected profile |
| Fortress profile `zinit` | `${XDG_DATA_HOME}/shell-config/<profile>/zinit/zinit.git` | Dev Fortress installs it when missing; plugin updates stay manual |
| Bootstrap `ZDOTDIR` | `${XDG_CACHE_HOME}/dev-container-fortress/csm-bootstrap-zdotdir` | Dev Fortress scratch space |
| Login shell | the target user's passwd entry | Dev Fortress sets `zsh` where enabled |
| Homebrew shellenv | the marked `DEV FORTRESS HOMEBREW` blocks in `~/.zprofile` and `~/.profile` | Dev Fortress owns only the text between the markers |
| Kickstart Neovim | `${XDG_CONFIG_HOME}/nvim-kickstart` and `~/.local/bin/nvim-kickstart` | Dev Fortress |
| Docker daemon config | `/etc/docker/daemon.json` | Dev Fortress owns the whole file on `workstation` and `cloud` targets |
| tmux profiles (`tmux-*` options) | `${XDG_DATA_HOME}/dev-container-fortress/tmux-profiles/` and `${XDG_CONFIG_HOME}/tmux/plugins/` | Dev Fortress rewrites the profiles; plugins are cloned when missing and updated with tpm (prefix + U) |
| Active tmux profile | the `${XDG_CONFIG_HOME}/tmux/tmux.conf` link, and `${XDG_STATE_HOME}/dev-container-fortress/tmux-profile` | Dev Fortress links only when the selected profile changes, so a `csm tmux-profile` choice survives; it never replaces a file it did not link |
| Claude Code (`claude-code` option) | `~/.local/bin/claude` and `${XDG_DATA_HOME}/claude` | Dev Fortress installs it when selected and the launcher is missing; Claude Code updates itself after that |

Dotfile linking is delegated to `shell-config` itself. Its `csm bootstrap`
links the profile's dotfiles and moves a pre-existing file aside instead of
deleting it.

> [!TIP]
> Anything a run leaves for you to act on is printed once more at the end,
> just above the play recap: each file `csm` moved aside, an existing
> `~/.zshrc` that the managed zsh no longer reads, and a tmux profile link held
> back by an existing config. Roles queue these in a `<role>_notices` list, and
> the `host.yml` post task joins them. Carry personal zsh settings into
> `env.zsh` or `aliases.zsh` under
> `${XDG_CONFIG_HOME}/shell-config.local/<profile>/`.

Everything else stays user-owned. That includes `~/.config/nvim`, content
outside the marked blocks in `~/.zprofile` and `~/.profile`, and any
customization layered on top of the `shell-config` profile.

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

### `dev_fortress_arch_base_packages`

Linux-first package baseline for Arch hosts using `community.general.pacman`.
It fails early on anything other than x86_64. Because Arch does not support
partial upgrades, it runs a full system upgrade first unless
`dev_container_fortress_arch_full_upgrade` is set to `false`. When that upgrade
replaces the running kernel on a `workstation` or `cloud` target, it reboots
`cloud` targets automatically and stops `workstation` targets with a reboot
request, controlled by `dev_container_fortress_arch_reboot_after_kernel_upgrade`.

### `dev_fortress_native_bootstrap_prereqs`

Converges the minimum native command substrate required before `shell-config`
bootstrap runs on supported Linux targets, then asserts that the substrate is
actually present. The current contract is intentionally small:
`python3`, `git`, `curl`, and `zsh`.

### `dev_fortress_docker`

Installs Docker CE on Ubuntu workstation and cloud targets using Docker's
official apt repository, or Docker from the official repositories on Arch
targets, converges a small managed `daemon.json`, enables the
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

Precedence: the `dev_container_fortress_manage_login_shell` inventory variable,
then the `DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL` environment variable, then
the non-local default. `install.sh` sets the environment variable to `1` in
host mode, because running the one-liner asks for a Dev Fortress workstation;
a plain `ft host bootstrap localhost` leaves the operator's shell alone.

### `dev_fortress_linuxbrew`

Installs Linuxbrew for supported Ubuntu targets in the standard supported
prefix, persists a managed shellenv snippet, and converges the current
fortress operator tool pool after `shell-config` bootstrap.

The Homebrew checkout tracks the newest stable `X.Y.Z` release tag, the same
target that Homebrew's own installer and `brew update` choose, so Homebrew's
auto-update and a later bootstrap pass agree. Set
`dev_container_fortress_homebrew_version` to a tag, branch (`main` for the
development branch), or commit to override it.

### `dev_fortress_neovim_kickstart`

Clones `kickstart.nvim` into a parallel XDG config directory and installs a
repo-managed `nvim-kickstart` wrapper that launches Neovim with
`NVIM_APPNAME=nvim-kickstart`. This keeps the IDE-style starter config
available without overwriting an existing user-owned `~/.config/nvim`.

### `dev_fortress_claude_code`

Installs Claude Code with its native installer (`https://claude.ai/install.sh`)
as the target user, without `become`, because the installer refuses to run
under `sudo` and installs into the user's home. The task is skipped when
`~/.local/bin/claude` already exists, so a re-run reports no change and never
fights Claude Code's own background updates.

It is the first optional component and runs only when `claude-code` is
selected. `ft` resolves the selection from `--options`,
`DEV_CONTAINER_FORTRESS_OPTIONS`, or `options.toml` (see `ft options`) and
renders `dev_container_fortress_claude_code_manage` into the inventory; the
playbook defaults it to `false`. It fails clearly on targets without
`/bin/bash`, such as the Alpine baseline.
`dev_container_fortress_claude_code_installer_url` points at an alternate
installer, such as an internal mirror.

### `dev_fortress_tmux`

Installs the Dev Fortress tmux profiles, ported from the `dotfiles` repo's
`tmux-minimal`, `tmux-full`, and `tmux-raidboss` packages, and links the
selected one. It runs only when a `tmux-*` option is selected; `ft` renders
`dev_container_fortress_tmux_profile` as `minimal`, `full`, `raidboss`, or
`none`, and `none` skips the role, leaving stock tmux. Everything runs as the
target user inside `$HOME`.

- every profile is templated into
  `${XDG_DATA_HOME}/dev-container-fortress/tmux-profiles/<name>/`, with
  absolute paths to its helper scripts and the tpm plugin directory, so
  `csm tmux-profile` can switch without a bootstrap
- the active profile is one symlink at `${XDG_CONFIG_HOME}/tmux/tmux.conf`.
  The role links only when the selected profile differs from the last one it
  applied, recorded in `${XDG_STATE_HOME}/dev-container-fortress/tmux-profile`,
  so a re-run keeps a `csm` choice, including `none`
- an existing `~/.tmux.conf`, or a `tmux.conf` that is not a link into the
  profiles directory, blocks the link; the run reports it and changes neither
- `full` and `raidboss` need tmux 3.8+, from Homebrew on Ubuntu; the role
  checks the version before linking and fails clearly
- `scripts/ensure-plugins.sh` clones missing tpm plugins. The role runs it for
  the active profile, and those profiles also run it at startup, so a profile
  chosen later with `csm` works on its first start
- each profile loads `${XDG_CONFIG_HOME}/tmux/local.conf` last, when present,
  for personal settings

### `dev_fortress_shell_config_ready`

Reports whether the target currently looks ready for the later shell-config
install or current shell-config state, while keeping the boundary between Dev
Fortress-managed state and user-owned customization explicit.
