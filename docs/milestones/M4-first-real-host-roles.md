# M4 First Real Host Roles

## Status

- [ ] Milestone complete
- [x] Active milestone

## Objective

Start converting the thin bootstrap contract into small, real Ansible roles.
Those roles should establish the first convergent desired-state baseline for
supported hosts rather than acting as one-shot bootstrap glue.

## Exit Criteria

- [x] At least one real role exists under `ansible/roles/`
- [x] The host playbook uses real roles where appropriate
- [x] The disposable Ubuntu target exercises at least one meaningful role in check mode and normal mode where safe
- [x] The disposable Alpine target validates the shared host contract and non-Ubuntu role gating safely
- [x] The first host roles are idempotent and safe to rerun on already-aligned hosts
- [x] The first host roles prefer built-in Ansible modules over shell-heavy task implementations
- [x] Docs explain what is truly provisioned versus still scaffolded

## Non-Goals

- [ ] Full workstation provisioning
- [ ] Brew integration across all platforms
- [ ] tmux and editor automation
- [ ] Rebuilding every host from scratch on each run
- [ ] Hiding provisioning behavior inside large custom shell tasks when a built-in Ansible module would do

## Issue Drafts

### M4-1 Scaffold first host role layout

- [x] Problem: `ansible/playbooks/host.yml` is still a thin bootstrap contract and needs a stable role/task structure
- [x] Scope: create the initial host role layout and move current bootstrap checks into clearer task organization
- [x] Acceptance: `host.yml` calls real role or task files
- [x] Acceptance: role layout is documented
- [x] Acceptance: role layout documents convergent desired-state expectations and managed boundaries
- [x] Acceptance: `ft host bootstrap dev-fortress-ubuntu --check` passes

### M4-2 Provision XDG and shell prerequisites

- [x] Problem: we verify directories and prerequisites but do not yet establish a minimum usable host baseline
- [x] Scope: create required XDG and shell-related directories with idempotent tasks
- [x] Acceptance: required directories are created by Ansible
- [x] Acceptance: tasks are idempotent
- [x] Acceptance: rerunning against an already-aligned host results in little or no change
- [x] Acceptance: verified against the disposable Ubuntu target

### M4-3 Install baseline Ubuntu package prerequisites

- [x] Problem: the host flow assumes tools like `git`, `zsh`, and Python are present
- [x] Scope: manage a minimal Ubuntu package baseline needed for host bootstrap
- [x] Acceptance: baseline package list is installed on Ubuntu
- [x] Acceptance: check mode remains useful where safe
- [x] Acceptance: built-in package modules are used where practical instead of shell wrappers
- [x] Acceptance: docs describe the supported baseline clearly

### M4-4 Define shell-config integration contract

- [x] Problem: the host bootstrap references `shell-config`, but the real integration boundary is not yet explicit
- [x] Scope: define what "shell-config ready" means at the host-bootstrap layer
- [x] Acceptance: integration contract is documented
- [x] Acceptance: bootstrap tasks validate or prepare the expected state
- [ ] Acceptance: the contract distinguishes Dev Fortress-managed state from user-owned customization
- [ ] Acceptance: no hidden assumptions remain in docs or tasks

### M4-5 Document first supported remote host flow

- [x] Problem: the implementation supports a disposable Ubuntu SSH loop, but the operator workflow needs one canonical guide
- [x] Scope: document build, key generation, enrollment, probe, and bootstrap
- [x] Acceptance: one operator-facing doc shows the full command sequence
- [x] Acceptance: commands are current and runnable
- [x] Acceptance: roadmap and milestone docs reflect M4 accurately

## Verification Notes

- [x] `pytest ft/tests/test_cli.py`
- [x] `ruff check ft/src/ft/cli.py ft/tests/test_cli.py`
- [x] `uv run --project ./ft ft container build ubuntu`
- [x] `uv run --project ./ft ft container build alpine`
- [x] `uv run --project ./ft ft host doctor dev-fortress-ubuntu --probe --config ft/targets/hosts.example.toml`
- [x] `uv run --project ./ft ft host doctor dev-fortress-alpine --probe --config ft/targets/hosts.example.toml`
- [x] `uv run --project ./ft ft host bootstrap dev-fortress-ubuntu --check --config ft/targets/hosts.example.toml`
- [x] `uv run --project ./ft ft host bootstrap dev-fortress-alpine --check --config ft/targets/hosts.example.toml`

## Branch and Merge Plan

- [ ] Branch from `main` as `feat/m4-first-real-host-roles`
- [ ] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once exit criteria are met
- [ ] Squash merge into `main`
