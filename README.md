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

## Quick Start

The fastest way to get running locally is the one-liner installer.

> [!IMPORTANT]
> Baseline prerequisites:
> `git` and `zsh`.
> For the container validation loop below, you also need Docker with `buildx`.
> `install.sh` checks the required baseline tools and warns if Docker or
> `buildx` are not available yet.

**Install with the one-liner**

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  DEV_CONTAINER_FORTRESS_DIR="$HOME/projects/dev-container-fortress" sh
```

This clones or refreshes the repo, ensures `uv` exists, and then hands off to
the repo bootstrap, which provisions a uv-managed Python 3.14 runtime for the
project environment.

> [!NOTE]
> `install.sh` supports a few environment variables for common onboarding
> overrides.

| Variable | Purpose |
| --- | --- |
| `DEV_CONTAINER_FORTRESS_DIR` | Choose the local checkout destination |
| `DEV_CONTAINER_FORTRESS_REF` | Pin a branch, tag, or commit |
| `DEV_CONTAINER_FORTRESS_REPO` | Use an alternate Git repository URL |
| `DEV_CONTAINER_FORTRESS_PYTHON_VERSION` | Override the uv-managed Python version used by `bootstrap.zsh` |

Full example with all installer overrides:

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  DEV_CONTAINER_FORTRESS_DIR="$HOME/projects/dev-container-fortress" \
  DEV_CONTAINER_FORTRESS_REF="main" \
  DEV_CONTAINER_FORTRESS_REPO="https://github.com/GrndZero101/dev-container-fortress.git" \
  DEV_CONTAINER_FORTRESS_PYTHON_VERSION="3.14" \
  sh
```

**Manual clone fallback**

```sh
git clone https://github.com/GrndZero101/dev-container-fortress.git
cd dev-container-fortress
zsh ./bootstrap.zsh
```

Use the manual path when you want to inspect or edit the checkout before
running the bootstrap.

**Validate the first local loop**

```sh
uv run ft doctor
uv run ft container build ubuntu
uv run ft container up ubuntu
uv run ft container validate ubuntu
```

> [!NOTE]
> For the full contributor workflow, see [DEVELOPMENT.md](/home/timl/projects/tboss/dev-container-fortress/DEVELOPMENT.md).

## Status

| Area | Status | Notes |
| --- | --- | --- |
| Local repo bootstrap | Working | `uv`-based local setup is in daily-use shape |
| `ft` CLI | Working | Main operator surface for container and early host workflows |
| Ubuntu disposable target | Working | End-to-end Docker, SSH, and Ansible check loop is proven |
| Alpine disposable target | Working | Container workflow is available; SSH host loop focus has been Ubuntu first |
| VS Code devcontainers | Working | Thin wrappers over the container targets |
| Host target model | Working foundation | `ft host ...` inventory, key, probe, and bootstrap contract exists |
| Real host provisioning roles | In progress | Current milestone is `M4 First Real Host Roles` |
| Full workstation bootstrap | Partial | Still scaffolded beyond the thin host bootstrap contract |

## :wrench: Operator Surface

| Interface | Role | Current guidance |
| --- | --- | --- |
| `ft` | Primary human and agent operator surface | Use this first |
| `just` | Convenience shim | Keep for muscle memory, but do not treat it as the logic home |
| `ansible/` | Host automation layer | Thin today, expanding during host-role milestones |
| `containers/` | Disposable target implementation | Use for build/runtime contracts |
| `.devcontainer/` | VS Code integration | Thin wrapper over the matching container target |

## :world_map: Target Matrix

| Target type | Current state | Primary docs |
| --- | --- | --- |
| Ubuntu container | Supported | [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) |
| Alpine container | Supported | [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) |
| Ubuntu disposable SSH host loop | Supported foundation | [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md) |
| macOS workstation | Planned / partial | [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md) |
| Ubuntu workstation | Planned / partial | [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md) |
| WSL workstation | Planned / partial | [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md) |
| VS Code devcontainers | Supported | [Devcontainer Usage](/home/timl/projects/tboss/dev-container-fortress/docs/devcontainer-usage.md) |

## :compass: Documentation Map

| Document | Audience | Purpose |
| --- | --- | --- |
| [README.md](/home/timl/projects/tboss/dev-container-fortress/README.md) | Everyone | Project overview and quick entry points |
| [DEVELOPMENT.md](/home/timl/projects/tboss/dev-container-fortress/DEVELOPMENT.md) | Contributors | Local bootstrap, checks, and iteration loops |
| [docs/container-usage.md](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md) | Operators | Docker-based usage and validation |
| [docs/workstation-usage.md](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md) | Operators | Host-target and workstation flow status |
| [docs/devcontainer-usage.md](/home/timl/projects/tboss/dev-container-fortress/docs/devcontainer-usage.md) | Operators | VS Code devcontainer usage |
| [docs/architecture.md](/home/timl/projects/tboss/dev-container-fortress/docs/architecture.md) | Maintainers | Layering and control-plane direction |
| [docs/container-standards.md](/home/timl/projects/tboss/dev-container-fortress/docs/container-standards.md) | Maintainers | Container runtime/build contract |
| [docs/ROADMAP.md](/home/timl/projects/tboss/dev-container-fortress/docs/ROADMAP.md) | Maintainers | Milestone ordering and strategic direction |
| [docs/milestones/README.md](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/README.md) | Maintainers | Active milestone workflow and draft format |

## :building_construction: Repository Layout

| Path | Purpose |
| --- | --- |
| `ft/` | Python package for the `ft` CLI, target model, and supporting logic |
| `ansible/` | Host playbooks, inventory contract, and future roles |
| `brew/` | Host-side Brew bundle definitions |
| `containers/` | Ubuntu and Alpine container targets plus shared runtime helpers |
| `.devcontainer/` | VS Code wrappers for container targets |
| `docs/` | Usage guides, contracts, roadmap, and milestone drafts |

## :dart: Design Direction

- Keep `ft` as the stable operator front door for both humans and agents
- Keep shell behavior in [`shell-config`](../shell-config/README.md)
- Prefer explicit, debuggable contracts over magic
- Prove transport and bootstrap paths before deepening workstation automation
- Keep the container and host stories aligned where practical without forcing them to be identical

## :zap: Current Working Surface

Working today:

- local workspace bootstrap with `uv`
- packaged `ft` CLI with grouped `container`, `host`, and `tool` surfaces
- Ubuntu and Alpine disposable container flows
- VS Code devcontainer wrappers
- host target inventory, managed SSH keys, public-key enrollment, probe, and thin bootstrap
- disposable Ubuntu end-to-end verification through Docker, SSH, and Ansible check mode

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

The next implementation focus is
[M3a One-Liner Installer and Onramp](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/M3a-one-liner-installer-and-onramp.md).

Use these planning docs together:

- [docs/ROADMAP.md](/home/timl/projects/tboss/dev-container-fortress/docs/ROADMAP.md) for strategy and milestone ordering
- [docs/milestones/README.md](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/README.md) for the execution workflow
- the active milestone draft under [docs/milestones](/home/timl/projects/tboss/dev-container-fortress/docs/milestones)

## Collaboration Model

> [!NOTE]
> This repository is developed through human-and-AI collaboration.
> Project direction, design intent, and acceptance decisions are human-led,
> while much of the implementation, iteration, and documentation work is
> carried out with agentic coding agents.

## License

Released under the MIT License.
See [LICENSE](/home/timl/projects/tboss/dev-container-fortress/LICENSE).
