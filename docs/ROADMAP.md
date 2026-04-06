# Dev Fortress Roadmap

## Overview

This document is the roadmap for Dev Fortress.
It is intentionally milestone-oriented rather than task-exhaustive.

Use it to track:

- strategic direction
- milestone scope
- milestone exit criteria
- ordering and dependencies
- ideas that are not yet ready to become implementation work

Do not use this file as the primary home for fine-grained execution tracking.
Concrete implementation work should live in the matching milestone draft under
`docs/milestones/`, then be copied into GitHub milestones and issues later when
that workflow becomes worth the overhead.

> [!NOTE]
> Operational truth belongs in the relevant README and usage documents once work
> is implemented.

## Workflow Standard

Recommended planning model for this repository:

1. Roadmap document for strategy and milestone framing
2. Milestone draft files under `docs/milestones/`
3. GitHub milestones and issues copied from those drafts when desired
4. Feature branches for milestone implementation
5. Squash merge into the main branch once milestone exit criteria are met

Recommended branch naming:

- Use milestone-aligned branch names by default: `feat/<sortable-milestone-id>-<short-name>`
- Convert roadmap milestone IDs into zero-padded sortable branch IDs
- Keep milestone letter suffixes when present
- Prefer hyphens over underscores in the descriptive suffix
- Examples:
  - `feat/m0003a-installer-onramp`
  - `feat/m0004-first-real-host-roles`
  - `docs/m0007-local-verification-workflow`

Sortable branch ID examples:

- `M3a` -> `m0003a`
- `M4` -> `m0004`
- `M7a` -> `m0007a`

Recommended issue types:

- `epic`
- `feature`
- `task`
- `spike`
- `bug`
- `docs`

Recommended milestone states inside this document:

- `done`
- `now`
- `next`
- `later`
- `icebox`

Each milestone should have:

- one-sentence objective
- clear exit criteria
- explicit non-goals
- a matching markdown file under `docs/milestones/`

## Planning Principles

- Prefer small, mergeable milestones over broad “phase” work.
- Keep milestones outcome-shaped rather than component-shaped.
- Treat `ft` as the main operator surface.
- Keep shell UX in `shell-config` and environment provisioning in this repo.
- Prove transport and bootstrap paths before deepening workstation automation.
- Keep “done” meaningful: code, docs, and verification should move together.

## Current Direction

- Build a shell and terminal environment that feels intentional, high-signal,
  and developer-heavy without becoming opaque.
- Prefer Catppuccin Mocha where the underlying tool supports it cleanly.
- Prefer explicit, debuggable configuration over clever hidden behavior.
- Keep features understandable across shell startup, container startup, and
  workstation login flows.
- Build toward milestone-based squash merges rather than unbounded branch drift.

## Milestones

### `M0` Shell and Container Baseline

Status: `done`

Objective:
Establish the repo structure, container targets, shell-config integration, and
the first usable `ft` CLI baseline.

Delivered:

- packaged `ft` operator CLI foundation
- Ubuntu and Alpine disposable container targets
- shell-config integration in container builds
- initial validation and completion workflows
- `just` as a thin front door over the emerging CLI

### `M1` SSH Target Foundation

Status: `done`

Objective:
Define a shared host target model and prove the first thin SSH-based control
plane.

Exit criteria:

- named host target manifest exists
- managed SSH key paths are XDG-aligned
- `ft host list`, `show`, `inventory`, `ssh-key`, `doctor`, and `bootstrap`
  exist and work at a basic level
- generated Ansible inventory is driven from the shared target model

Delivered:

- host target manifest model
- managed SSH key generation
- inventory rendering
- host doctor and probe support
- thin inventory-driven bootstrap path

Details:
[M1 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M1-ssh-target-foundation.md)

### `M2` Disposable Ubuntu Remote Loop

Status: `done`

Objective:
Prove one real end-to-end remote path against a disposable Ubuntu SSH target.

Exit criteria:

- Ubuntu disposable target starts an SSH daemon
- managed public key can be authorized for the disposable target
- SSH probe succeeds against the live disposable target
- `ft host bootstrap --check` succeeds against that target

Delivered:

- SSH-enabled Ubuntu disposable target
- managed public-key enrollment support
- managed known-hosts path for disposable targets
- live end-to-end verification loop through Docker, SSH, and Ansible check mode

Details:
[M2 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M2-disposable-ubuntu-remote-loop.md)

### `M3` Thin Host Bootstrap Contract

Status: `done`

Objective:
Replace fake workstation-role assumptions with a real thin bootstrap contract.

Exit criteria:

- host playbook no longer references missing roles
- bootstrap proves reachability and target metadata cleanly
- target user XDG directory preparation is explicit
- readiness reporting is useful for humans and agents

Delivered:

- task-based thin host bootstrap playbook
- shell-config presence and baseline tool checks
- documentation aligned with the actual thin-bootstrap behavior

Details:
[M3 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M3-thin-host-bootstrap-contract.md)

### `M3a` One-Liner Installer and Onramp

Status: `now`

Objective:
Add a real one-liner install path and align top-level onboarding around it.

Exit criteria:

- a repo-owned installer entrypoint exists for clone-and-bootstrap onboarding
- the installer is safe for non-interactive use on supported developer platforms
- `README.md` quickstart leads with the installer and a truthful clone fallback
- `DEVELOPMENT.md` reflects the same onboarding path

Non-goals:

- full workstation provisioning
- curl-installed binary distribution of `ft`
- deep package-manager bootstrap beyond the repo bootstrap itself

Details:
[M3a draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M3a-one-liner-installer-and-onramp.md)

### `M4` First Real Host Roles

Status: `next`

Objective:
Start converting the thin bootstrap contract into small, real Ansible roles.

Exit criteria:

- at least one real role exists under `ansible/roles/`
- the host playbook uses real roles where appropriate
- the disposable Ubuntu target can exercise at least one meaningful role in
  check mode and normal mode where safe
- docs explain what is now truly provisioned versus still scaffolded

Non-goals:

- full workstation provisioning
- Brew integration across all platforms
- tmux and editor automation

Details:
[M4 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M4-first-real-host-roles.md)

### `M5` Host Bootstrap Expansion

Status: `next`

Objective:
Expand host provisioning from “reachable and inspectable” into a meaningful
host setup path.

Exit criteria:

- host playbook provisions a small but real baseline
- shell-config bootstrap handoff is automated where intended
- host-side prerequisite handling is clearer across Linux, macOS, and WSL
- bootstrap assumptions and carve-outs are documented

Details:
[M5 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M5-host-bootstrap-expansion.md)

### `M6` Operator CLI Maturity

Status: `next`

Objective:
Make `ft` feel like the stable operator surface for humans and agentic tooling.

Exit criteria:

- grouped command structure is stable and documented
- root and group help UX are intentionally strong
- JSON output for the most important validation paths is typed and useful
- the remaining `just` layer is clearly a convenience shim, not the logic home

Details:
[M6 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M6-operator-cli-maturity.md)

### `M7` Local Verification Workflow

Status: `next`

Objective:
Make repeat testing fast, obvious, and reliable for both humans and agents.

Exit criteria:

- one clear local verification loop exists for disposable targets
- the loop covers build, up, SSH, validation, logs, and teardown
- the “recommended workflow” is documented and stable
- verification does not depend on tribal knowledge

Details:
[M7 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M7-local-verification-workflow.md)

### `M7a` Secrets Management

Status: `next`

Objective:
Establish a secrets-management baseline suitable for daily-driver operator
workflows across both persistent and ephemeral environments.

Exit criteria:

- GPG setup and key-management workflow is documented for local use
- backup, restore, transfer, and offline key-handling guidance exists
- `pass` or `gopass` setup is documented against the chosen GPG workflow
- `op` CLI integration expectations are documented and wired where appropriate
- secure backup and restore guidance exists for secret material across multiple environments
- the secrets workflow includes an explicit restore story for fresh or disposable environments
- the supported secrets-management baseline is explicit in operator docs

Non-goals:

- enterprise vault orchestration beyond local operator workflows
- fully automated hardware-token provisioning
- cross-platform parity in the first pass
- picking every secret-related tool in the first pass if one baseline path is enough

Details:
[M7a draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M7a-secrets-management.md)

### `M8` Shell UX Polish

Status: `later`

Objective:
Refine the fortress shell experience once the environment automation baseline is
stable enough not to churn underneath it.

Candidate areas:

- prompt-engine diagnostics
- prompt theme selection strategy
- richer HUD/debug surfaces
- `bat` man-page integration
- `eza` tree defaults
- optional `gum` polish after operator flows settle

Details:
[M8 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M8-shell-ux-polish.md)

### `M9` Host and Cloud Targets

Status: `later`

Objective:
Extend the shared SSH and bootstrap model to non-container remote targets.

Candidate areas:

- Terraform-backed disposable workstation targets, likely EC2 first
- clearer `ft host ...` versus `ft infra ...` boundaries
- workstation-oriented target creation and discovery

Details:
[M9 draft](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M9-host-and-cloud-targets.md)

Non-goal for early work:

- cloud-specific control planes before the SSH and Ansible model is stable

## Idea Pools

These are intentionally not milestones yet.
Promote them only when they become concrete enough to deserve milestone scope.

### Tooling and UX

- `bat` as a cleaner man-page viewer
- `delta` for richer git diff rendering
- `lazygit` as an optional companion tool
- `yazi` as a vim-like file workflow layer
- `fastfetch` as a welcome or diagnostics surface
- `rustic` a backup tool
- `tmux` strategy and Catppuccin-friendly theme integration

### Prompt and Shell Exploration

- prompt-engine validation helpers
- alternative prompt theme variants
- reference `oh-my-posh` comparison profile
- possible alternative shell exploration such as `fish` or `pwsh`
- Look at profile sets for `shell-config` (beginer, operator, fortress elite)
  - Will look at things like whether to use vi mode by default

### Build and Caching

- prewarming fortress `zinit` plugins in Docker builds
- pinned plugin cache strategy across Ubuntu and Alpine
- explicit build modes for prewarmed versus lean shells

### Onboarding and Toolchain

- recommended fortress toolchain guide
- installation guidance for operator-favorite tools
- possible `csm` diagnostics for recommended tools
- markdown lint/format standard once the team settles on one

### Offline Spin

- airgap / firefighting capability. For use where the internet is not available.

## Definition of Done

A milestone is ready for squash merge when:

- the scoped code changes are implemented
- the relevant docs are updated
- tests are added or updated where appropriate
- live verification has been run for risky or integration-heavy changes
- backlog or roadmap state has been updated to match reality

## Next Planning Move

When a new milestone begins:

1. write one short objective
2. define 3-5 exit criteria
3. create or update the matching milestone file under `docs/milestones/`
4. implement on a feature branch
5. copy the milestone draft into GitHub when useful
6. squash merge once the exit criteria are met
