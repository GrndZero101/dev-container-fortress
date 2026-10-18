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
- Design host automation as convergent desired state, not one-shot setup.
- Prefer built-in Ansible modules over custom shell-heavy orchestration where practical.
- Keep “done” meaningful: code, docs, and verification should move together.

## Current Direction

- Build a shell and terminal environment that feels intentional, high-signal,
  and developer-heavy without becoming opaque.
- Prefer Catppuccin Mocha where the underlying tool supports it cleanly.
- Prefer explicit, debuggable configuration over clever hidden behavior.
- Keep features understandable across shell startup, container startup, and
  workstation login flows.
- Make existing aligned workstations and fresh hosts converge toward the same
  declared Dev Fortress baseline.
- Build toward milestone-based squash merges rather than unbounded branch drift.
- Serve four use cases: a direct Ubuntu host (physical, virtual, or cloud), WSL2
  Ubuntu on Windows, a VS Code devcontainer, and a devcontainer CLI terminal
  mode. Treat every one as a long-lived, composable development environment
  rather than a tightly pinned build artifact.

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
[M1 draft](milestones/M1-ssh-target-foundation.md)

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
[M2 draft](milestones/M2-disposable-ubuntu-remote-loop.md)

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
[M3 draft](milestones/M3-thin-host-bootstrap-contract.md)

### `M3a` One-Liner Installer and Onramp

Status: `done`

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

Delivered:

- POSIX `install.sh` with repo, ref, and destination overrides that runs
  cleanly with no terminal attached
- README and `DEVELOPMENT.md` onboarding that leads with the one-liner and a
  clone fallback
- `sh -n` syntax checks for the installer in pre-commit and CI

Details:
[M3a draft](milestones/M3a-one-liner-installer-and-onramp.md)

### `M4` First Real Host Roles

Status: `done`

Objective:
Start converting the thin bootstrap contract into small, real Ansible roles.

Exit criteria:

- at least one real role exists under `ansible/roles/`
- the host playbook uses real roles where appropriate
- the disposable Ubuntu target can exercise at least one meaningful role in
  check mode and normal mode where safe
- first host roles are safe to rerun on already-aligned hosts and converge them
  toward the intended baseline
- docs explain what is now truly provisioned versus still scaffolded

Non-goals:

- full workstation provisioning
- Brew integration across all platforms
- tmux and editor automation
- forcing every host difference through opaque imperative fix-up logic

Delivered:

- real, rerunnable roles under `ansible/roles/` that `M5` and `M9a` build on
- an explicit table of Dev Fortress-managed versus user-owned host state

Details:
[M4 draft](milestones/M4-first-real-host-roles.md)

### `M4a` Disposable Cloud Ubuntu Host Loop

Status: `done`

Objective:
Create the first Terraform-backed disposable Ubuntu VM loop so Dev Fortress can
exercise its SSH and bootstrap model against a real cloud host at low cost,
likely EC2 Spot first.

Candidate areas:

- Terraform-backed disposable Ubuntu host, likely EC2 Spot first
- machine-readable cheapest-instance selection with a fallback fixed shape
- target registration handoff from Terraform outputs into `ft host ...`
- canonical provision -> probe -> bootstrap -> destroy workflow

Current state:

- real EC2 Ubuntu provisioning is proven
- `ft host doctor --probe` and `ft host bootstrap` are proven against a live VM
- Session Manager access is proven on the disposable host
- teardown is proven through Terraform and `ft infra aws-disposable-ubuntu destroy`
- Spot capacity selection ships as `ft infra aws-disposable-ubuntu capacity select`

Details:
[M4a draft](milestones/M4a-disposable-cloud-ubuntu-host-loop.md)

### `M5` Host Bootstrap Expansion

Status: `done`

Objective:
Expand host provisioning from “reachable and inspectable” into a meaningful
host setup path.

Exit criteria:

- host playbook provisions a small but real baseline
- shell-config installation and bootstrap are automated where intended
- shell-config is validated first on a minimally prepared Linux host before
  Homebrew becomes the preferred steady-state tool substrate
- host-side prerequisite handling is clearer across Linux, macOS, and WSL
- reruns on previously configured or manually aligned hosts level-set drift
  safely rather than assuming a pristine machine
- bootstrap assumptions and carve-outs are documented

Delivered:

- verified Ubuntu-first WSL2 bootstrap path against `localhost`
- real host baseline through Ansible roles for XDG layout, native bootstrap
  prerequisites, `shell-config`, fortress profile-local `zinit`, readiness
  reporting, and Ubuntu Linuxbrew uplift
- convergent local validation through `ft host validate` with final
  `PLAY RECAP` parsing and `changed=0` enforcement
- explicit documentation for the remaining local WSL login-shell carve-out

Details:
[M5 draft](milestones/M5-host-bootstrap-expansion.md)

### `M5a` Disposable Daily-Driver Container

Status: `now`

Objective:
Define and prove the first real day-to-day development container workflow so a
thin host such as disposable Ubuntu EC2 can run a bind-mounted Fortress
workstation container for live development.

Candidate areas:

- first-class `ft` workflow for a mounted daily-driver container
- bind-mounted live working copies of `dev-container-fortress` and `shell-config`
- explicit persisted-state and auth mount policy
- optional heavy tool layers such as `gh`, `glab`, `aws`, and `az`
- proof of the provision -> bootstrap -> develop -> destroy EC2 loop

Design rule:

- keep the host thin and convergent; keep the real workstation inside the container
- keep container tool layers repo-owned and image-managed rather than
  Homebrew-backed
- keep host userland tooling aligned to the Homebrew-preferred steady-state
  substrate established in `M5`

Recommended command direction:

- introduce `ft workspace ...` for the mounted workstation path
- keep `ft container ...` focused on disposable validation targets

Current state:

- `ft workspace ...` profiles, live bind mounts, tool layers, and the auth
  contract are implemented and verified locally
- persisted state is an explicit allowlist (`state`, `zoxide`, `atuin`) shared
  by workspaces and devcontainers; the image owns the rest of `${XDG_DATA_HOME}`
- the disposable EC2 develop-in-container loop is documented but not yet proven

Details:
[M5a draft](milestones/M5a-disposable-daily-driver-container.md)

### `M5b` Zero to Hero: Workstation Composability

Status: `next`

Objective:
Take a brand-new or existing Ubuntu machine to a working Dev Fortress
workstation from one `curl | sh` command with sane defaults, while keeping
host or workspace mode, tmux profiles, and the identity step composable.

Exit criteria:

- one command converges a fresh Ubuntu 24.04 host, WSL2 Ubuntu, or Ubuntu EC2
  instance, with `host` mode as the default and a thin `workspace` mode
- the installer installs its own prerequisites, registers `localhost`, and runs
  the host bootstrap, with at most one `sudo` prompt
- stable Homebrew and one-pass convergence; re-runs on brownfield hosts are safe
- a Git identity step with a manual corporate and GitLab fallback
- tmux profiles (`minimal`, `full`, `raidboss`) ported from `dotfiles`
- one consolidated "Zero to Hero" quickstart

Non-goals:

- macOS hosts, which come next, and integrating the separate `dotfiles` repo

Details:
[M5b draft](milestones/M5b-zero-to-hero-workstation-composability.md)

### `M5c` Composable Container Workspaces

Status: `planned`

Objective:
Make the container targets long-lived, composable development environments by
standardizing their userland on Homebrew and making the VS Code devcontainer
and devcontainer CLI terminal mode genuinely useful.

Exit criteria:

- container userland tools come from Homebrew, using the same bundle model as
  the hosts
- Claude Code is installed in every container target through its native
  installer
- one recommended way to get code into a devcontainer (bind mount or volume
  clone), with the other one as a documented variant
- a devcontainer CLI terminal mode works end to end
- `ft workspace` and `.devcontainer/` share one definition or document why
  they differ

Non-goals:

- byte-for-byte reproducible image builds, and new container distros

Details:
[M5c draft](milestones/M5c-composable-container-workspaces.md)

### `M6` Operator CLI Maturity

Status: `next`

Objective:
Make `ft` feel like the stable operator surface for humans and agentic tooling.

Exit criteria:

- grouped command structure is stable and documented
- root and group help UX are intentionally strong
- JSON output for the most important validation paths is typed and useful
- the remaining `just` layer is clearly a convenience shim, not the logic home

Known gaps found while dogfooding:

- `ft host ssh <target> -- <command>` for one-off remote commands; today only an
  interactive session works, so scripts fall back to raw `ssh`
- an OS or workspace option on `ft infra aws-disposable-ubuntu`, so Arch hosts
  do not need `TF_WORKSPACE`, `TF_VAR_*`, and a shared capacity file swap

Details:
[M6 draft](milestones/M6-operator-cli-maturity.md)

### `M6a` Python Maintainability Refactor

Status: `next`

Objective:
Refactor the growing Python implementation behind `ft` into smaller,
domain-oriented modules so the codebase stays DRY, KISS, YAGNI, and easier to
change safely as the operator surface expands.

Exit criteria:

- `ft/src/ft/cli.py` is reduced to thin Typer command wiring and light argument
  handling
- host, SSH, infra, interactive selection, and container logic are split into
  focused modules with coherent responsibilities
- new behavior is added behind reusable functions rather than copied across CLI
  commands
- tests are less concentrated in one monolithic CLI test file
- the refactor does not change the public `ft` command surface unintentionally

Details:
Track as a maintainability-focused follow-on once the current M5 operator loop
stabilizes.

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
[M7 draft](milestones/M7-local-verification-workflow.md)

### `M7a` Secrets Management

Status: `next`

Objective:
Establish a secrets-management baseline suitable for daily-driver operator
workflows across both persistent and ephemeral environments.

Current first-pass decision:

- use GPG plus `pass` as the supported local baseline
- install secrets tooling through the `ubuntu-secrets` workspace image layer
- keep container GPG and pinentry on the base package manager for now while
  host targets prefer Homebrew where supported
- mount GPG and password-store state at runtime rather than baking secrets into
  Docker images
- treat `rustic` as the likely general backup/restore primitive, with secrets
  as the first high-value profile
- leave `gopass`, `op`, and concrete `rustic` automation as follow-up work

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
[M7a draft](milestones/M7a-secrets-management.md)

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
[M8 draft](milestones/M8-shell-ux-polish.md)

### `M9` Host and Cloud Targets

Status: `later`

Objective:
Extend the shared SSH and bootstrap model to non-container remote targets.

This remains the broader milestone bucket.
The first narrow real-VM enabling step now lives in `M4a`.

Candidate areas:

- Terraform-backed disposable workstation targets, likely EC2 first
- clearer `ft host ...` versus `ft infra ...` boundaries
- workstation-oriented target creation and discovery

Details:
[M9 draft](milestones/M9-host-and-cloud-targets.md)

Non-goal for early work:

- cloud-specific control planes before the SSH and Ansible model is stable

### `M9a` Arch Linux Target

Status: `done`

Objective:
Add Arch Linux as a supported container and host target with the same
reproducibility and verification contract as Ubuntu and Alpine.

Exit criteria:

- an archive-pinned Arch container image passes the `ft container` validation loop
- `ft host bootstrap` converges an Arch host idempotently, using pacman rather
  than Homebrew for the steady-state toolchain
- unsupported combinations such as Arch on arm64 fail clearly
- the Arch image is built, smoke-tested, and published by CI

Non-goals:

- Arch on arm64, AUR packages, and Terraform-backed Arch cloud hosts

Details:
[M9a draft](milestones/M9a-arch-linux-target.md)

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

### CI/CD

The local `ft` loop (see `M7`) stays the primary verification surface for now.

- branch and pull-request CI now gates image builds and GHCR publishing on
  pre-commit, pytest, and Terraform checks (`ci.yml`, landed with `M9a`)
- possible follow-ups: Buildx layer caching, arm64 image builds, and branch
  protection that requires the `CI` checks

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
