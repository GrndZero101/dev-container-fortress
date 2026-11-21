# Dev Container Fortress

Dev Fortress provisions developer environments: it takes a fresh Ubuntu or
WSL2 Ubuntu machine to a working workstation in one command, and builds the
containers, devcontainers, and multi-repo workbenches that sit on top of it.

It is split into thin layers:

- `ft` is the operator CLI, for humans and agents
- Ansible converges hosts
- Homebrew supplies the steady-state toolchain
- Dockerfiles build the container images
- [`shell-config`](https://github.com/GrndZero101/shell-config) owns the shell
  experience, which this repo consumes rather than reimplements

> [!IMPORTANT]
> This project is in active buildout. The [support matrix](#support-matrix)
> below is the one place that records what works today.

## Install

On Ubuntu or WSL2 Ubuntu, with a user that can `sudo`:

```sh
cd ~
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | sh
```

After one `sudo` prompt this installs Docker, `shell-config` with zsh as the
login shell, the Homebrew toolchain, and `ft`. Re-running it is safe, including
on a machine you set up by hand.

The [quickstart](docs/quickstart.md) is the whole install guide: prerequisites,
extras such as Claude Code and the tmux profiles, the `cli` and `workspace`
install modes, every override, WSL2 notes, and troubleshooting.

To work on Dev Fortress itself, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Support Matrix

| Target | State | Notes |
| --- | --- | --- |
| Ubuntu workstation, bare metal or WSL2 | Supported | One command; Ubuntu 26.04 LTS on amd64 and arm64 is the tested baseline |
| macOS workstation | Partial | The installer's `cli` mode only; host mode is planned in `M5e` |
| Remote Ubuntu host over SSH, including EC2 | Supported | `ft host ...` enrolls, probes, and converges it |
| Arch host | New | x86_64 only; pacman supplies the toolchain instead of Homebrew |
| Alpine host | Partial | Base packages, `shell-config`, and zsh as the login shell; no Homebrew toolchain |
| Ubuntu container | Supported | amd64 and arm64 |
| Alpine container | Supported | Tools come from the `ft install` downloader, because Homebrew does not support musl |
| Arch container | Supported | amd64 only |
| Workspace daily-driver container | Supported | `ft workspace ...`, amd64 and arm64 |
| VS Code devcontainers | Supported | Thin wrappers over the container targets |
| Workbenches | New | Multi-repo devcontainers rendered from one TOML file |

## Documentation

### Start Here

| Document | Purpose |
| --- | --- |
| [Quickstart](docs/quickstart.md) | Install a workstation, from prerequisites to a validated machine |
| [WSL2 notes](docs/wsl-bootstrap.md) | Windows-side setup, systemd, Docker, interop, and Windows SSH |

### Guides

| Document | Purpose |
| --- | --- |
| [Workbenches](docs/guides/workbench-usage.md) | Multi-repo devcontainers for your own repos |
| [Workspaces](docs/guides/workspace-usage.md) | The mounted daily-driver container, `ft workspace ...` |
| [Devcontainers](docs/guides/devcontainer-usage.md) | The repo's VS Code devcontainer definitions |
| [Containers](docs/guides/container-usage.md) | Building, running, and validating the images |
| [Workstations and remote hosts](docs/guides/workstation-usage.md) | Host targets and bootstrap over SSH |
| [EC2 development host](docs/guides/ec2-development-loop.md) | A disposable cloud development host |
| [Secrets](docs/guides/secrets-management.md) | GPG and `pass` in workspace profiles |

### Reference

| Document | Purpose |
| --- | --- |
| [`ft` CLI reference](docs/reference/cli.md) | Every command and flag, generated from the CLI itself |

### Design

| Document | Purpose |
| --- | --- |
| [Architecture](docs/design/architecture.md) | Layering, tool selection, and control-plane direction |
| [Container standards](docs/design/container-standards.md) | The container build and runtime contract |
| [Daily-driver design](docs/design/daily-driver-design.md) | Design notes behind `ft workspace` |
| [Backup and restore](docs/design/backup-restore.md) | Direction for `rustic`-based backups |

### Project

| Document | Purpose |
| --- | --- |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Contributor setup, checks, CI, and development loops |
| [Roadmap](docs/project/ROADMAP.md) | Milestone ordering and current direction |
| [Milestones](docs/project/milestones/README.md) | Milestone workflow and working drafts |
| [Target validation](docs/project/target-validation.md) | Runbook for validating the container and EC2 targets |
| [TODO.md](TODO.md) | The short "up next" queue |
| [AGENTS.md](AGENTS.md) | Conventions for coding agents and contributors |

Component READMEs sit beside the code they describe: [`ansible/`](ansible/README.md),
[`containers/`](containers/README.md), [`infra/`](infra/README.md), and
[`ft/tools/`](ft/tools/README.md).

## Repository Layout

| Path | Purpose |
| --- | --- |
| `ft/` | Python package for the `ft` CLI, target model, and supporting logic |
| `ansible/` | Host playbooks, inventory contract, and roles |
| `brew/` | Host-side Brew bundle definitions |
| `containers/` | Ubuntu, Alpine, and Arch container targets plus shared runtime helpers |
| `infra/` | Terraform stacks for disposable hosts and the test fleet |
| `.devcontainer/` | VS Code wrappers for the container targets |
| `devcontainer/` | Devcontainer CLI definitions that VS Code should not offer on reopen |
| `examples/workbench/` | A rendered reference workbench, kept current by pre-commit |
| `docs/` | Guides, reference, design notes, roadmap, and milestone drafts |

## Collaboration Model

> [!NOTE]
> This repository is developed through human-and-AI collaboration.
> Project direction, design intent, and acceptance decisions are human-led,
> while much of the implementation, iteration, and documentation work is
> carried out with agentic coding agents.

## License

Released under the MIT License.
See [LICENSE](LICENSE).
