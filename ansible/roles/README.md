# Roles

This directory is where host bootstrap moves from thin contract checks into
real provisioning work.

Current state:

- `playbooks/host.yml` is still the thin bootstrap entrypoint
- the first convergent host roles now exist for contract validation, XDG layout,
  Ubuntu and Alpine baseline packages, and shell-config readiness reporting
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
- `dev_fortress_shell_config_ready`
- future `shell_config_bootstrap`
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

### `dev_fortress_shell_config_ready`

Reports whether the target currently looks ready for the later shell-config
handoff, while keeping the boundary between Dev Fortress-managed state and
user-owned customization explicit.
