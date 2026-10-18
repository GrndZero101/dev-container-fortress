# M5a Disposable Daily-Driver Container

## Status

- [ ] Milestone complete
- [x] Next candidate milestone

## Objective

Define and implement the first real "daily driver" container workflow so Dev
Fortress can be used to develop Dev Fortress, `shell-config`, and adjacent
operator repos inside a reproducible container on a thin disposable host such
as Ubuntu EC2.

The goal is not merely to validate Docker image builds. The goal is to prove a
repeatable operator workstation loop that can come up on a fresh host in
minutes, mount live working copies, handle day-to-day auth surfaces, and be
safe to destroy and recreate frequently without hidden snowflake state.

## Exit Criteria

- [x] One supported daily-driver container contract is documented for Ubuntu-first use
- [x] The contract clearly separates thin host responsibilities from container responsibilities
- [x] `ft` exposes a first-class operator workflow for the daily-driver container instead of requiring ad hoc `docker run` commands
- [x] The workflow supports bind-mounted local working copies of `dev-container-fortress` and `shell-config`
- [x] The workflow supports a small explicit set of persisted state mounts for caches and auth material
- [x] The initial auth and secrets contract is explicit for SSH, Git HTTPS/OAuth, and GPG-backed `pass` or `gopass`
- [x] Optional heavy CLI layers such as `gh`, `glab`, `aws`, and `az` are modeled as opt-in image or tool profiles rather than mandatory base-image contents
- [x] A disposable Ubuntu EC2 host can be provisioned, bootstrapped, used for real development inside the daily-driver container, and destroyed again with the same documented operator loop
- [x] The recommended loop is documented truthfully in user-facing docs once implemented

## Non-Goals

- [ ] Solving full cross-platform parity in the first pass
- [ ] Making the daily-driver container the only supported development path
- [ ] Baking private keys, cloud tokens, or secret material directly into images
- [ ] Supporting every identity provider or enterprise SSO workflow in the first pass
- [ ] Building one giant kitchen-sink image as the default baseline
- [ ] Replacing the existing disposable validation targets before the daily-driver path is proven

## Design Direction

Recommended operator surface:

- add a new `ft workspace ...` group for mounted day-to-day development
- keep `ft container ...` focused on disposable validation targets

See [daily-driver design](../daily-driver-design.md)
for the concrete proposed command contract.

### Host Versus Container Ownership

The disposable host should stay thin and convergent.

The host should own only:

- SSH reachability
- Docker Engine and `buildx`
- workspace checkout locations
- persisted state directories that survive container replacement when desired
- optional agent or socket handoff points

The daily-driver container should own:

- shell UX
- `ft`
- language and operator tool layers
- `shell-config`
- git, forge, and cloud CLIs
- interactive development workflow

### Supported First Pass

The first supported daily-driver path should be Ubuntu-first and should target:

- local Docker hosts
- Ubuntu under WSL2
- disposable Ubuntu EC2 hosts bootstrapped by Dev Fortress

That gives one honest Linux-first path before broadening the matrix.

### Runtime Contract

The first pass should define a small, explicit runtime contract rather than
trying to infer everything from an unstructured host.

Required bind mounts:

- live `dev-container-fortress` checkout
- live `shell-config` checkout when actively developing `shell-config`

Candidate persisted mounts:

- `${HOME}/.cache`
- `${HOME}/.local/state`
- `${HOME}/.local/share/zoxide` and `${HOME}/.local/share/atuin`, never all of
  `${HOME}/.local/share`, which the image owns
- `${HOME}/.config/gh`
- `${HOME}/.config/glab`
- `${HOME}/.aws`
- `${HOME}/.azure`
- password-store and GPG-agent-adjacent paths once the secrets contract is chosen

The contract should say which paths are:

- required
- optional
- safe to persist
- expected to remain host-owned

### Auth and Secrets Contract

The first pass should prefer runtime handoff over image-baked secrets.

Supported design direction:

- SSH: forward an agent or mount an explicit SSH state path; do not bake private keys into images
- Git HTTPS/OAuth: prefer mounted config/state or host-driven device or browser login flows
- GPG: define one explicit supported path for agent and key access before claiming support
- `pass` or `gopass`: define the password-store location and restore workflow for fresh hosts and containers

The daily-driver container should not claim to solve secrets management in
isolation. It should consume the secrets baseline chosen by `M7a`.

### Image and Tool Layering

The default base image should remain lean.

Optional daily-driver layers should be modeled explicitly, likely as one or
both of:

- image variants such as `base`, `gitforge`, `secrets`, `aws`, `azure`
- `ft` tool profiles that can be selected at build or runtime

The critical design rule is that heavy tools such as `aws` and `az` remain
opt-in and do not become mandatory weight for all users and all targets.

## Issue Drafts

### M5a-1 Define the daily-driver runtime contract

- [x] Problem: the repo has disposable validation containers, but no explicit contract for a mounted real-development container
- [x] Scope: define required mounts, optional persisted mounts, naming, lifecycle, and ownership boundaries
- [x] Acceptance: one Ubuntu-first runtime contract is documented clearly enough to implement without guesswork

### M5a-2 Add first-class `ft` operator commands for the workflow

- [x] Problem: the current `ft container ...` flow is shaped for disposable test targets, not a mounted day-to-day development session
- [x] Scope: implement the proposed `ft workspace build`, `up`, `enter`, `exec`, `down`, `reset`, `status`, and `doctor` commands for the daily-driver container
- [x] Acceptance: the operator workflow can be run through `ft` rather than raw `docker run`

### M5a-3 Support live repo bind mounts

- [x] Problem: daily-driver use requires editing local clones of `dev-container-fortress` and `shell-config` instead of copying sources into the image
- [x] Scope: support bind-mounted working copies and document the expected in-container workspace layout
- [x] Acceptance: Dev Fortress and `shell-config` can both be edited live from inside the container

### M5a-4 Define persisted state and auth mount policy

- [x] Problem: disposable hosts and containers need a truthfully scoped story for what should persist across rebuilds and what should not
- [x] Scope: define persisted cache, CLI config, SSH, forge, cloud, and secrets-adjacent mount policy
- [x] Acceptance: auth and persistence boundaries are explicit enough for repeatable use on local hosts and disposable EC2

### M5a-5 Add optional tool-layer selection

- [x] Problem: the daily-driver use case wants tools such as `gh`, `glab`, `aws`, and `az`, but they should not bloat the default base image
- [x] Scope: define image-layer or tool-profile selection for heavy optional CLIs
- [x] Acceptance: at least one supported opt-in mechanism exists for heavier daily-driver tooling

### M5a-6 Prove the disposable EC2 operator loop

- [x] Problem: the strongest reproducibility claim is not proven until a real disposable cloud host can be used for actual development inside the container
- [x] Scope: validate the end-to-end EC2 flow: provision, bootstrap, mount repos, work inside container, and destroy
- [x] Acceptance: the documented Ubuntu EC2 loop works end to end and is worth repeating daily

## Verification Notes

- [x] A fresh Ubuntu EC2 host can be provisioned through the repo-owned infra path
- [x] `ft host bootstrap` prepares the host without requiring workstation-only snowflake state
- [x] The daily-driver container can start against bind-mounted `dev-container-fortress` and `shell-config` checkouts
- [ ] Normal development tasks work from inside the container, including editing, git operations, shell-config iteration, and Fortress self-hosting checks
- [x] Replacing the container does not lose intentionally persisted state
- [x] Destroying and recreating the EC2 host does not require undocumented operator recovery steps

## Progress Notes

Status sweep on 2026-10-17. Most of the workspace slice already landed on
`main` (mainly `b8b8c06`, `27ec638`, and `ec92234`); the milestone file had not
been updated.

Verified locally with `ubuntu-base`:

- `ft workspace build`, `up`, `validate`, `exec`, and `down` work end to end
- both checkouts are bind-mounted live: a file written inside the container
  appears on the host with the operator's ownership, and git works in both
- `ft workspace exec` failed whenever stdin was not a terminal because it always
  requested a TTY; fixed in the same sweep for `ft container exec` too

Fixed on 2026-10-18 on `feat/m0005a-disposable-daily-driver-container`:

- the blanket `share` mount over `${XDG_DATA_HOME}` hid the image's `uv` tools,
  managed Python, `ft`, Neovim runtime, and prewarmed zinit plugins. It is
  replaced by an allowlist of narrow mounts: `state` (`${XDG_STATE_HOME}`, which
  holds zsh history), `zoxide`, and `atuin`. The rule now lives in the persisted
  state contract in `docs/container-standards.md`
- zsh history lives under `${XDG_STATE_HOME}`, so it was never persisted before
- `ft workspace validate` now runs `ft`, `uv`, `python3.14`, and `nvim` instead
  of trusting `PATH`
- the repo devcontainer definitions persist the same three paths as named
  volumes, and the images pre-create them with `vscode` ownership
- verified with `ubuntu-base`: validate passes, and zoxide data, `state`, and
  `atuin` contents survive `ft workspace up` replacing the container
- verified the Ubuntu devcontainer with the `devcontainer` CLI: the three named
  volumes mount as `vscode`, `postCreate` passes, and zoxide data and `state`
  survive `devcontainer up --remove-existing-container`

> [!NOTE]
> Older workspace state directories still contain an unused `share/`
> subdirectory. It only holds a zoxide database and re-downloaded zinit
> plugins, so remove it by hand:
> `rm -rf ~/.local/state/dev-container-fortress/workspaces/*/share`

### EC2 loop run on 2026-10-18

Followed `docs/ec2-development-loop.md` on a t4g.medium arm64 Spot host in
`ap-southeast-1` (tboss-mgmt). This note was written and committed from inside
the `ubuntu-full` workspace on that host.

- `capacity select`, `plan`, and `apply` provisioned the host and imported it
  into `hosts.toml`
- `ft host validate` failed on the first converge: Homebrew poured seven
  formulae twice in one run and the second pour deleted the first ("Bottle
  destination already exists"). A rerun converged, and the idempotency pass
  reported `changed=0`
- `ft deploy init --dev-branch` cloned both repos; `ft doctor` and the 168
  tests passed on the host
- the first arm64 `ubuntu-full` build failed: `install-aws-cli` always fetched
  the x86_64 bundle (fixed in `f5fcd9a`, pulled onto the host with Git)
- after the fix, `ft workspace validate ubuntu-full` passed every check, the
  tests passed inside the workspace, and zoxide and `state` contents survived
  `ft workspace up` replacing the container
- this note was committed inside the workspace and pushed from it as `1476c0a`
  after `gh auth login --web` (device flow) and `gh auth setup-git`, then
  pulled on the workstation. `gh auth logout` ran before teardown
- `ft infra aws-disposable-ubuntu destroy` removed all six resources and the
  instance terminated

Gaps found while dogfooding the loop:

- the role tracks the Homebrew development branch (the host ran
  `7.0.9-157-g013821d`) rather than the latest stable tag, which makes host
  bootstrap non-deterministic and may explain the duplicate pour
- convergence needs two passes: the second pass still changed the Linuxbrew
  formulae and `neovim_kickstart` tasks
- host and workspace share one `.venv` in the bind-mounted checkout, so each
  side's `uv run` recreates it for its own interpreter
- `--shell-config-stage-from` copies into `.local/sources/`, which was not
  ignored by Git (fixed in this commit)
- the workspace has no Git identity on first use. The identity must be the
  GitHub noreply address: GitHub declined a push authored with the account's
  private email
- push access works through `gh auth login --web` inside the workspace, but
  the runbook does not document it. The first device code expired unused, and
  the token is stored in plain text in the `config-gh` mount because the
  container has no keyring. Ubuntu's `gh` 2.45 also lacks `--skip-ssh-key`
- `destroy` leaves the imported target in `hosts.toml` with the old address;
  the next `apply` overwrites it
- `ft host ssh <target> -- <command>` is still missing (already an `M6` gap),
  and `ft host show` truncates the managed key path

The loop works end to end, but only with steps the runbook did not cover, so
the EC2 exit criterion and the `M5a-6` acceptance stay open until a rerun from
the runbook alone passes.

Follow-ups done after the run:

- `docs/ec2-development-loop.md` now covers the workspace Git identity (with the
  noreply caveat), the `gh` device-flow login, a GitLab and corporate fallback,
  and the commit, push, and pull round trip
- the runbook's `~/...` paths never worked through `ft deploy exec`, which
  quotes each argument; it now uses `../shell-config` and sibling discovery
- the images set `UV_PROJECT_ENVIRONMENT=.venv-container`, so the host `.venv`
  and the container environment no longer overwrite each other
- `test_workspace_auth_checks_reflect_profile_mounts` read the real `BROWSER`
  and failed inside workspaces; it now clears it

Stable Homebrew and one-pass host convergence moved to `M5b`, which owns the
fresh and brownfield host onramp.

### EC2 loop rerun on 2026-10-18, runbook only

Followed `docs/ec2-development-loop.md` alone on an m8g.large (Graviton4,
2 vCPU, 8 GiB) arm64 Spot host. This note was committed from inside the
`ubuntu-full` workspace on that host.

- `ft host validate` passed first time in under 7 minutes: one real converge,
  then an idempotency pass with `changed=0`. The Homebrew duplicate-pour race
  did not recur
- `ft deploy init --dev-branch`, `ft doctor`, and the 168 tests passed on the host
- the runbook's `ubuntu-full` build passed in 1 minute 40 seconds with the
  `../shell-config` path, and `up` and `validate` passed without
  `--shell-config-checkout`, using sibling discovery
- the tests passed inside the workspace in `.venv-container`, and the host
  `.venv` was untouched
- the host `.venv` uses Homebrew's Python 3.15 rather than the uv-managed 3.14,
  because `ft deploy init` does not run `bootstrap.zsh` and nothing pins the
  version; tracked for `M5b`
- the first `gh` device code expired unused after its 15 minutes, so start the
  login only when someone is ready to enter the code. The push round trip was
  already proven on the first run, so this commit came back to the local clone
  with `git format-patch` and `git am` instead, keeping its hash
- the host was inspected over `ft host ssh` and VS Code Remote-SSH. VS Code on
  Windows reads the Windows OpenSSH config, so it needs
  `ft host ssh-config --windows`; with WSL interop disabled the Windows
  profile cannot be inferred and `--windows-ssh-dir` is required
- `ft infra aws-disposable-ubuntu destroy` removed all six resources and left
  an empty state

The rerun passed from the runbook alone, which closes the EC2 exit criterion
and the `M5a-6` acceptance. The shell-config iteration part of the "normal
development tasks" check was not exercised on EC2, so that box stays open.

Open:

1. The separate `tboss-workspace` devcontainers persist cache and auth paths but
   not `state`, `zoxide`, or `atuin`; aligning them is tracked in that repo's
   `TODO.md`.

## Branch and Merge Plan

- [x] Branch from `main` as `feat/m0005a-disposable-daily-driver-container`
- [x] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once the proposed operator contract is stable
- [ ] Squash merge into `main`
