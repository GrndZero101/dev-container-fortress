# M4 First Real Host Roles

## Status

- [ ] Milestone complete
- [x] Next candidate milestone

## Objective

Start converting the thin bootstrap contract into small, real Ansible roles.

## Exit Criteria

- [ ] At least one real role exists under `ansible/roles/`
- [ ] The host playbook uses real roles where appropriate
- [ ] The disposable Ubuntu target exercises at least one meaningful role in check mode and normal mode where safe
- [ ] Docs explain what is truly provisioned versus still scaffolded

## Non-Goals

- [ ] Full workstation provisioning
- [ ] Brew integration across all platforms
- [ ] tmux and editor automation

## Issue Drafts

### M4-1 Scaffold first host role layout

- [ ] Problem: `ansible/playbooks/host.yml` is still a thin bootstrap contract and needs a stable role/task structure
- [ ] Scope: create the initial host role layout and move current bootstrap checks into clearer task organization
- [ ] Acceptance: `host.yml` calls real role or task files
- [ ] Acceptance: role layout is documented
- [ ] Acceptance: `ft host bootstrap dev-fortress-ubuntu --check` passes

### M4-2 Provision XDG and shell prerequisites

- [ ] Problem: we verify directories and prerequisites but do not yet establish a minimum usable host baseline
- [ ] Scope: create required XDG and shell-related directories with idempotent tasks
- [ ] Acceptance: required directories are created by Ansible
- [ ] Acceptance: tasks are idempotent
- [ ] Acceptance: verified against the disposable Ubuntu target

### M4-3 Install baseline Ubuntu package prerequisites

- [ ] Problem: the host flow assumes tools like `git`, `zsh`, and Python are present
- [ ] Scope: manage a minimal Ubuntu package baseline needed for host bootstrap
- [ ] Acceptance: baseline package list is installed on Ubuntu
- [ ] Acceptance: check mode remains useful where safe
- [ ] Acceptance: docs describe the supported baseline clearly

### M4-4 Define shell-config integration contract

- [ ] Problem: the host bootstrap references `shell-config`, but the real integration boundary is not yet explicit
- [ ] Scope: define what "shell-config ready" means at the host-bootstrap layer
- [ ] Acceptance: integration contract is documented
- [ ] Acceptance: bootstrap tasks validate or prepare the expected state
- [ ] Acceptance: no hidden assumptions remain in docs or tasks

### M4-5 Document first supported remote host flow

- [ ] Problem: the implementation supports a disposable Ubuntu SSH loop, but the operator workflow needs one canonical guide
- [ ] Scope: document build, key generation, enrollment, probe, and bootstrap
- [ ] Acceptance: one operator-facing doc shows the full command sequence
- [ ] Acceptance: commands are current and runnable
- [ ] Acceptance: roadmap and milestone docs reflect M4 accurately

## Verification Notes

- [ ] `pytest ft/tests/test_cli.py`
- [ ] `ruff check ft/src/ft/cli.py ft/tests/test_cli.py`
- [ ] `uv run --project ./ft ft container build ubuntu`
- [ ] `uv run --project ./ft ft host doctor dev-fortress-ubuntu --probe --config ft/targets/hosts.example.toml`
- [ ] `uv run --project ./ft ft host bootstrap dev-fortress-ubuntu --check --config ft/targets/hosts.example.toml`

## Branch and Merge Plan

- [ ] Branch from `main` as `feat/m4-first-real-host-roles`
- [ ] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once exit criteria are met
- [ ] Squash merge into `main`
