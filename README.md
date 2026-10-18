# Dev Container Fortress

## Overview

`dev-container-fortress` is a developer-environment orchestration repo for:

- host bootstrap and provisioning
- disposable Docker-based test targets
- VS Code devcontainers
- a shared operator CLI named `ft`

The project is intentionally split across layers:

- `ft` is the operator surface
- Ansible handles host orchestration
- Dockerfiles handle container construction
- `shell-config` owns shell UX rather than this repo reimplementing it

Tooling policy follows the same split:

- container images should install userland tools through repo-owned Dev Fortress
  mechanisms such as `ft`, shared installer scripts, and image-managed build
  logic
- host targets should converge on Homebrew for steady-state userland tools once
  the minimal native bootstrap substrate is in place
- Ansible should orchestrate and validate host state, including Homebrew-backed
  host tooling, rather than becoming the primary tool source itself

> [!IMPORTANT]
> This project is still in active buildout.
> The container and operator loops are already useful day to day, while the
> direct workstation path is still maturing.
> [!NOTE]
> `just` still exists, but it is now a thin compatibility shim.
> Treat `ft` as the primary interface.

## Associated Projects

| Project | Role |
| --- | --- |
| [`shell-config`](https://github.com/GrndZero101/shell-config) | Shell UX, profile behavior, and interactive environment shaping consumed by Dev Fortress |
| `tboss-workspace` | Thin VS Code devcontainer orchestrator that consumes published Dev Fortress images for multi-repo daily-driver work |

## Two Paths

Choose the path that matches your intent:

- `Operator install`: you want a working environment quickly and are happy for
  Dev Fortress to manage the installed `shell-config` checkout under your XDG
  config tree
- `Development install`: you are actively changing `dev-container-fortress`,
  `shell-config`, or both, and want local clone paths to be the source of truth

For active repository work, prefer the development path.

## Operator Install

The fastest operator path is the one-liner installer.

> [!IMPORTANT]
> On Ubuntu and WSL2 Ubuntu the only prerequisite is `curl`: the installer
> installs `git`, `zsh`, `python3`, and its other native prerequisites itself,
> behind one `sudo` password prompt. On other platforms only `--mode cli`
> works, and it needs `git` and `zsh` already installed.

### One-liner

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | sh
```

In the default `host` mode this installs the native prerequisites, clones or
refreshes the repo, ensures `uv` exists, and hands off to the repo bootstrap,
which provisions a uv-managed Python 3.14 runtime and installs a live `ft` CLI
plus a user-level Ansible. It then converges this machine with
`ft host bootstrap localhost`: Docker, `shell-config`, the zsh login shell, and
the Homebrew toolchain. Re-running the command is safe.

`sudo` asks for your password once. The installer keeps the `sudo` session
alive in the background so the Ansible run can reuse it, which means the
whole install must run in one terminal.

### Optional components

Large extras, starting with Claude Code (`claude-code`, about 270 MB), are not
installed unless you select them. Choose them in one of three ways:

| Way | Example | Lasts |
| --- | --- | --- |
| Flag or variable | `sh -s -- --options claude-code` | this run; overrides the saved choice |
| Checkbox picker | `sh -s -- --interactive`, or `uv run ft options pick` later | saved to `options.toml` |
| Config file | `enabled = ["claude-code"]` in `${XDG_CONFIG_HOME:-~/.config}/dev-container-fortress/options.toml` | every later bootstrap |

`uv run ft options` lists the choices and shows which ones the next
`ft host bootstrap` will install. Removing an option later stops managing it but
does not uninstall it.

The installer finishes with `ft identity`, which sets the global Git
`user.name` and `user.email`. It keeps an existing identity, uses the
`DEV_CONTAINER_FORTRESS_GIT_*` variables when they are set, and otherwise
prompts on a terminal for whatever is missing. Without a terminal it skips and
prints the `git config` commands, so it never blocks an unattended run. Run
`uv run ft identity --help` later to change it or to start a `gh` or `glab`
login.

> [!IMPORTANT]
> If your GitHub account keeps its email private, GitHub declines pushes from
> that address. Use the noreply address from GitHub → Settings → Emails. For a
> corporate forge or GitLab, use the address that forge expects, and fall back
> to plain `git config` and the forge's token flow when its login is blocked.

| Mode | What it does |
| --- | --- |
| `host` (default) | Prerequisites, `ft`, and the full `localhost` host bootstrap |
| `cli` | Prerequisites (Ubuntu only), the checkout, `uv`, `ft`, and Ansible; no host changes beyond packages |
| `workspace` | Thin host plus a daily-driver workspace; planned in `M5b` |

Pass flags through the pipe with `sh -s --`:

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  sh -s -- --mode cli --dir "$HOME/projects/dev-container-fortress"
```

On host bootstrap paths, Dev Fortress will also manage the installed
`shell-config` checkout unless you deliberately point it somewhere else.

> [!NOTE]
> Every flag also has an environment variable.

| Variable | Flag | Purpose |
| --- | --- | --- |
| `DEV_CONTAINER_FORTRESS_MODE` | `--mode` | Choose `host`, `cli`, or `workspace` |
| `DEV_CONTAINER_FORTRESS_DIR` | `--dir` | Choose the local checkout destination |
| `DEV_CONTAINER_FORTRESS_REF` | `--ref` | Pin a branch, tag, or commit |
| `DEV_CONTAINER_FORTRESS_REPO` | `--repo` | Use an alternate Git repository URL |
| `DEV_CONTAINER_FORTRESS_PYTHON_VERSION` | | Override the uv-managed Python version used by `bootstrap.zsh` |
| `DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL` | | Host mode makes zsh the login shell; set `0` to keep the current one |
| `DEV_CONTAINER_FORTRESS_OPTIONS` | `--options` | Optional components for this run, such as `claude-code`, or `none` |
| `DEV_CONTAINER_FORTRESS_INTERACTIVE` | `--interactive` | Set `1` to pick optional components in a checkbox list |
| `DEV_CONTAINER_FORTRESS_GIT_NAME` | | Git `user.name` to set without a prompt |
| `DEV_CONTAINER_FORTRESS_GIT_EMAIL` | | Git `user.email` to set without a prompt |
| `DEV_CONTAINER_FORTRESS_FORGE_LOGIN` | | `github` or `gitlab`: also start a forge login on a terminal |

Full example with all installer overrides:

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  DEV_CONTAINER_FORTRESS_MODE="host" \
  DEV_CONTAINER_FORTRESS_DIR="$HOME/projects/dev-container-fortress" \
  DEV_CONTAINER_FORTRESS_REF="main" \
  DEV_CONTAINER_FORTRESS_REPO="https://github.com/GrndZero101/dev-container-fortress.git" \
  DEV_CONTAINER_FORTRESS_PYTHON_VERSION="3.14" \
  sh
```

### Manual clone fallback

```sh
git clone https://github.com/GrndZero101/dev-container-fortress.git
cd dev-container-fortress
zsh ./bootstrap.zsh
```

Use the manual path when you want to inspect or edit the checkout before
running the bootstrap.

### First validation loop

```sh
uv run ft doctor
uv run ft container build ubuntu
uv run ft container up ubuntu
uv run ft container validate ubuntu
```

For the current host-target path, continue with:

```sh
uv run ft host bootstrap localhost --check
uv run ft host bootstrap localhost
```

## Development Install

For development, keep both repos cloned explicitly and treat those clones as
the source of truth:

```text
<workspace>/
  dev-container-fortress/
  shell-config/
```

Recommended setup:

```sh
git clone https://github.com/GrndZero101/dev-container-fortress.git
git clone https://github.com/GrndZero101/shell-config.git
cd dev-container-fortress
zsh ./bootstrap.zsh
```

Then use the local repos directly:

- run `ft` from the Dev Fortress checkout
- keep `shell-config` as a sibling checkout so workspace and container flows can
  see it automatically
- prefer local-source container and workspace flows over GitHub-backed staging

Recommended development loops:

```sh
ft workspace doctor ubuntu-full
ft workspace build ubuntu-full
ft workspace up ubuntu-full
ft workspace enter ubuntu-full
```

For VS Code-first multi-repo work, use the sibling `tboss-workspace` scaffold:

```text
tboss-workspace/
  .devcontainer/
  repos/
    dev-container-fortress/
    shell-config/
```

That scaffold consumes `ghcr.io/grndzero101/dev-container-fortress:ubuntu-full`
by default and keeps Dev Fortress image publishing separate from workspace
composition.

```sh
ft container build ubuntu \
  --shell-config-source local \
  --shell-config-stage-from /absolute/path/to/shell-config
```

> [!NOTE]
> The full contributor workflow lives in
> [DEVELOPMENT.md](DEVELOPMENT.md).

## Status

| Area | Status | Notes |
| --- | --- | --- |
| Local repo bootstrap | Working | `uv`-based local setup is in daily-use shape |
| `ft` CLI | Working | Main operator surface for container and early host workflows |
| Ubuntu disposable target | Working | End-to-end Docker, SSH, and Ansible check loop is proven |
| Alpine disposable target | Working | End-to-end Docker, SSH, and Ansible check loop is proven |
| Arch disposable target | Working | amd64 only; container loop and a disposable Arch EC2 host verified in `M9a` |
| VS Code devcontainers | Working | Thin wrappers over the container targets |
| Workspace daily-driver container | Working | `ft workspace ...` verified locally and on a disposable Ubuntu EC2 host in `M5a`, including amd64 and arm64 images |
| Host target model | Working foundation | `ft host ...` inventory, key, probe, and bootstrap contract exists |
| Real host provisioning roles | Working | Ubuntu roles converge WSL2 `localhost` and Ubuntu EC2 hosts; Arch and Alpine base roles exist |
| Full workstation bootstrap | Partial | Works on Ubuntu and WSL2 with several manual steps; the one-command onramp is `M5b` |

## :wrench: Operator Surface

| Interface | Role | Current guidance |
| --- | --- | --- |
| `ft` | Primary human and agent operator surface | Use this first |
| `ft deploy` | Remote EC2 development-host loop | Use `deploy init` to clone Git checkouts and `deploy exec` for remote commands |
| `ft infra aws-disposable-ubuntu capacity select` | EC2 capacity selector for the disposable daily-driver host | Use Spot for cost or on-demand for stability before Terraform plan/apply |
| `just` | Convenience shim | Keep for muscle memory, but do not treat it as the logic home |
| `ansible/` | Host automation layer | Thin today, expanding during host-role milestones |
| `containers/` | Disposable target implementation | Use for build/runtime contracts |
| `.devcontainer/` | VS Code integration | Thin wrapper over the matching container target |

## :world_map: Target Matrix

| Target type | Current state | Primary docs |
| --- | --- | --- |
| Ubuntu container | Supported | [Container Usage](docs/container-usage.md) |
| Alpine container | Supported | [Container Usage](docs/container-usage.md) |
| Arch container | New, amd64 only | [Container Usage](docs/container-usage.md) |
| Arch host bootstrap | New, x86_64 only, pacman instead of Homebrew | [Ansible README](ansible/README.md) |
| Ubuntu disposable SSH host loop | Supported foundation | [Workstation Usage](docs/workstation-usage.md) |
| macOS workstation | Planned / partial | [Workstation Usage](docs/workstation-usage.md) |
| Ubuntu workstation | Planned / partial | [Workstation Usage](docs/workstation-usage.md) |
| WSL workstation | Ubuntu-first active path | [WSL Bootstrap Runbook](docs/wsl-bootstrap.md) |
| VS Code devcontainers | Supported | [Devcontainer Usage](docs/devcontainer-usage.md) |

## :compass: Documentation Map

| Document | Audience | Purpose |
| --- | --- | --- |
| [README.md](README.md) | Everyone | Project overview plus operator-versus-development entry points |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Contributors | Clone layout, local bootstrap, checks, and iteration loops |
| [docs/container-usage.md](docs/container-usage.md) | Operators | Docker-based usage and validation |
| [docs/workstation-usage.md](docs/workstation-usage.md) | Operators | Host-target and workstation flow status |
| [docs/wsl-bootstrap.md](docs/wsl-bootstrap.md) | Operators | Step-by-step bootstrap path for Ubuntu under WSL2 |
| [docs/target-validation.md](docs/target-validation.md) | Operators | Current three-target validation runbook across Ubuntu, Alpine, and EC2 |
| [docs/ec2-development-loop.md](docs/ec2-development-loop.md) | Operators | Git-backed EC2 development-host loop |
| [docs/secrets-management.md](docs/secrets-management.md) | Operators | First-pass GPG and `pass` secrets baseline for workspace profiles |
| [docs/backup-restore.md](docs/backup-restore.md) | Operators | General `rustic`-oriented backup and restore direction |
| [docs/devcontainer-usage.md](docs/devcontainer-usage.md) | Operators | VS Code devcontainer usage |
| [docs/architecture.md](docs/architecture.md) | Maintainers | Layering and control-plane direction |
| [docs/container-standards.md](docs/container-standards.md) | Maintainers | Container runtime/build contract |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Maintainers | Milestone ordering and strategic direction |
| [docs/milestones/README.md](docs/milestones/README.md) | Maintainers | Active milestone workflow and draft format |

## :building_construction: Repository Layout

| Path | Purpose |
| --- | --- |
| `ft/` | Python package for the `ft` CLI, target model, and supporting logic |
| `ansible/` | Host playbooks, inventory contract, and future roles |
| `brew/` | Host-side Brew bundle definitions |
| `containers/` | Ubuntu, Alpine, and Arch container targets plus shared runtime helpers |
| `infra/` | Terraform-owned infrastructure layer for disposable and future repeatable host targets |
| `.devcontainer/` | VS Code wrappers for container targets |
| `docs/` | Usage guides, contracts, roadmap, and milestone drafts |

## :dart: Design Direction

- Keep `ft` as the stable operator front door for both humans and agents
- Keep shell behavior in [`shell-config`](../shell-config/README.md)
- Prefer explicit, debuggable contracts over magic
- Prove transport and bootstrap paths before deepening workstation automation
- Keep the container and host stories aligned where practical without forcing them to be identical
- Keep container userland tooling repo-owned and image-managed
- Keep host userland tooling Homebrew-managed after the native bootstrap floor, except on Arch where pacman already covers it

## :zap: Current Working Surface

Working today:

- local workspace bootstrap with `uv`
- packaged `ft` CLI with grouped `container`, `workspace`, `host`, and `tool` surfaces
- Ubuntu and Alpine disposable container flows
- Ubuntu-first mounted workspace flow through `ft workspace ...`
- VS Code devcontainer wrappers
- host target inventory, managed SSH keys, public-key enrollment, probe, and thin bootstrap
- disposable Ubuntu and Alpine end-to-end verification through Docker, SSH, and Ansible bootstrap

In progress:

- first real host provisioning roles
- clearer shell-config handoff for host targets
- smoother milestone-level verification workflow

> [!TIP]
> For active `shell-config` development, prefer
> `ft container build <target> --shell-config-source local --shell-config-stage-from /absolute/path/to/shell-config`
> so you are not fighting stale Docker cache from GitHub-backed clones.

## :rocket: Bootstrap Direction

| Flow | Shape today |
| --- | --- |
| Local repo bootstrap | `bootstrap.zsh` installs `uv`, syncs the environment, and enables repo-local tooling |
| Direct host bootstrap | thin host contract with `ft host doctor`, inventory rendering, SSH key workflow, and Ansible bootstrap |
| Docker build | Dockerfile plus Python/`uv`-driven userland tooling and `shell-config` integration |
| Devcontainer bootstrap | thin VS Code wrapper over the matching container target |

## :calendar: Current Milestone

The current implementation focus is
[M4 First Real Host Roles](docs/milestones/M4-first-real-host-roles.md).

Use these planning docs together:

- [docs/ROADMAP.md](docs/ROADMAP.md) for strategy and milestone ordering
- [docs/milestones/README.md](docs/milestones/README.md) for the execution workflow
- the active milestone draft under [docs/milestones](docs/milestones)

## Collaboration Model

> [!NOTE]
> This repository is developed through human-and-AI collaboration.
> Project direction, design intent, and acceptance decisions are human-led,
> while much of the implementation, iteration, and documentation work is
> carried out with agentic coding agents.

## License

Released under the MIT License.
See [LICENSE](LICENSE).
