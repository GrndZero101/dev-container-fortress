# Roles

This directory is where host bootstrap moves from thin contract checks into
real provisioning work.

Current state:

- `playbooks/host.yml` is still the thin bootstrap entrypoint
- real roles should be added incrementally as milestone-backed slices land
- the first role work is expected during `M4 First Real Host Roles`

Role guidance:

- keep roles small and composable
- prefer one clear responsibility per role
- keep platform-specific behavior explicit
- avoid burying high-level orchestration decisions inside deep role trees
- document required variables and assumptions near the role

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

- `base_packages`
- `xdg_layout`
- `shell_config_presence`
- `shell_config_bootstrap`
- `uv_prereqs`

As roles land, update this file so it reflects current reality rather than a
wishlist.
