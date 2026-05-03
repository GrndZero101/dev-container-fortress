# Development Guide

This guide is for a developer who wants to get productive in `dev-container-fortress` quickly.

It focuses on the current high-value loop:

- bootstrap the repo locally
- use `ft` as the primary operator CLI
- build and validate Ubuntu and Alpine test containers
- iterate on `shell-config` and container behavior without getting lost in Docker cache surprises

> [!IMPORTANT]
> `ft` is the primary interface now. `just` still exists, but treat it as a compatibility shim rather than the main developer workflow.
> [!NOTE]
> Dev Fortress should increasingly be used to develop and validate itself.
> When a documented `ft` or bootstrap workflow exists, prefer it over ad hoc
> manual commands. If a necessary workflow is still too manual or taxing,
> treat that as a roadmap opportunity rather than a permanent workaround.

## Supported Developer Platforms

The current recommended developer platforms are:

- macOS with Homebrew and Docker Desktop
- Ubuntu on bare metal or Ubuntu under WSL2, with Docker CE from Docker's official apt repository

General tool-management rule of thumb:

- Docker images: repo-owned custom installers and `ft`-managed image logic
- Host userland tools on macOS, Ubuntu, WSL2, and EC2 Ubuntu: Homebrew after
  the minimal native bootstrap substrate is in place
- Native package managers remain acceptable for base host prerequisites such as
  Docker Engine, `git`, `curl`, and similar bootstrap-floor dependencies

## What You Need

Recommended baseline on your workstation:

- `zsh`
- `git`
- Docker with `buildx`
- `curl`
- `rsync`

You do not need `uv` or Python 3.14 preinstalled. The repo bootstrap will
install `uv` if needed and then provision a uv-managed Python 3.14 runtime for
the project environment.

### macOS with Homebrew

If you use Homebrew, these commands are a good baseline:

```zsh
brew install git rsync pre-commit
brew install --cask docker
```

Then:

1. start Docker Desktop
2. wait for Docker to become available
3. confirm `docker buildx version` works

Useful checks:

```zsh
docker version
docker buildx version
git --version
rsync --version
```

> [!TIP]
> `pre-commit` is optional at the package-manager level because the repo can run it through `uv`, but installing it globally is still convenient for local development.

### Ubuntu or Ubuntu on WSL2

On Ubuntu, prefer Docker CE from Docker's official apt repository instead of a Homebrew-based Docker install.

Useful baseline packages:

```zsh
sudo apt update
sudo apt install -y git rsync curl ca-certificates pre-commit
```

Then install Docker CE using Docker's standard Ubuntu method:

```zsh
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"${UBUNTU_CODENAME:-$VERSION_CODENAME}\") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Optional post-install so you can run Docker without `sudo` after a fresh login:

```zsh
sudo usermod -aG docker "$USER"
```

Useful checks:

```zsh
docker version
docker buildx version
git --version
rsync --version
```

> [!IMPORTANT]
> Under WSL2, make sure the Docker daemon path you choose is actually reachable from your Ubuntu environment before starting the Dev Fortress loop. The simplest route is usually a normal Docker CE install inside Ubuntu, or a known-good Docker Desktop plus WSL integration setup you already trust.

## First-Time Setup

Recommended one-liner:

```zsh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | sh
```

This will:

1. clone or refresh the repository checkout
2. install `uv` if missing
3. hand off to `bootstrap.zsh`
4. provision a uv-managed Python 3.14 runtime for the project environment
5. create or refresh the local project environment
6. install the live `ft` CLI into the user tool path with `uv tool install`
7. install the `ft` completion artifact into the XDG data tree

Optional environment overrides:

- `DEV_CONTAINER_FORTRESS_DIR` to change the checkout destination
- `DEV_CONTAINER_FORTRESS_REF` to pin a branch, tag, or commit
- `DEV_CONTAINER_FORTRESS_REPO` to use an alternate repository URL

Manual clone fallback:

```zsh
git clone https://github.com/GrndZero101/dev-container-fortress.git
cd dev-container-fortress
zsh ./bootstrap.zsh
```

This will:

1. install `uv` if missing
2. provision a uv-managed Python 3.14 runtime for the local project
3. create or refresh the local `.venv`
4. install Python dependencies for local development
5. install the live `ft` CLI into the user tool path from the local checkout
6. install the `ft` zsh completion artifact into the XDG data tree

After bootstrap, open a fresh shell if you want the new completion loaded cleanly.

## Core Developer Commands

Use `ft` directly:

```zsh
uv run ft --help
uv run ft doctor
uv run ft container --help
uv run ft completion path zsh
```

Once the repo is bootstrapped and your shell is picking up the installed tooling, the shorter form should also work:

```zsh
ft doctor
ft container status
```

## Baseline Local Checks

Run these after a fresh checkout or after significant CLI changes:

```zsh
uv run ruff check ft
uv run pytest ft/tests
uv run pre-commit run --all-files
pre-commit run markdownlint-cli2 --all-files
```

To install the hooks locally:

```zsh
uv run pre-commit install
```

The current baseline keeps the hooks intentionally light:

- file hygiene checks for YAML, JSON, merge markers, trailing whitespace, and EOF handling
- `markdownlint-cli2` for repo Markdown, aligned with the VS Code markdownlint ecosystem
- `ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" ansible-playbook --syntax-check`
  for the repo-owned host playbook
- `ansible-lint` for the Ansible tree under `ansible/`
- `ruff` lint and format for Python
- `zsh -n` syntax checks for repo-owned Zsh entrypoints under `scripts/` plus `bootstrap.zsh`

## Workspace Daily-Driver Loop

The repo now also includes an Ubuntu-first daily-driver container path for
mounted development work.

Start with:

```zsh
ft workspace doctor ubuntu-base
ft workspace build ubuntu-base
ft workspace up ubuntu-base
ft workspace enter ubuntu-base
```

This path is intentionally different from the disposable target loop:

- `ft container ...` is for validation targets and parity testing
- `ft workspace ...` is for live mounted day-to-day development

Current first-pass behavior:

- the workspace bind-mounts the live `dev-container-fortress` checkout
- it bind-mounts a sibling `../shell-config` checkout automatically when present
- it persists a small state set for cache, share, GitHub CLI, GitLab CLI, AWS, and Azure paths under the Dev Fortress XDG state tree
- on WSL-backed hosts, it mounts `C:\Windows\System32` read-only into the container and defaults browser-based auth flows to the built-in host browser helper unless `BROWSER` or `GH_BROWSER` is already set

Current auth limitation to keep in mind:

- browser launch from the workspace container is supported
- localhost callback OAuth is not guaranteed in plain Docker workspaces
- for tools such as AWS CLI SSO, prefer device-code flows in workspace
  containers, for example `aws sso login --use-device-code`
- native hosts can keep their normal localhost callback flows

Use `ft workspace exec ubuntu-base -- zsh -lc 'pwd'` for one-off commands and
`ft workspace reset ubuntu-base` when you want to remove both the container and
its tagged image cleanly.

For auth-oriented runtime checks, use:

```zsh
ft workspace auth doctor ubuntu-gitforge
ft workspace auth validate ubuntu-gitforge
```

If you want the most feature-complete current workspace for day-to-day use and
cross-layer validation, prefer:

```zsh
ft workspace doctor ubuntu-full
ft workspace build ubuntu-full
ft workspace up ubuntu-full
ft workspace auth validate ubuntu-full
ft workspace enter ubuntu-full
```

## Preferred Container Development Loop

### Quick Orientation

Start with:

```zsh
ft doctor
ft container status
```

### Build, Start, Validate

Ubuntu:

```zsh
ft container build ubuntu
ft container up ubuntu
ft container validate ubuntu
ft container shell ubuntu
```

Alpine:

```zsh
ft container build alpine
ft container up alpine
ft container validate alpine
ft container shell alpine
```

### Faster Convenience Commands

For the most common human loops:

```zsh
ft container refresh ubuntu
ft container enter ubuntu
```

Meaning:

- `refresh` rebuilds the image and replaces the container
- `enter` ensures the target is ready, then opens an interactive shell

### Useful Inspection Commands

```zsh
ft container logs ubuntu
ft container exec ubuntu -- printenv TERM
ft container exec ubuntu -- zsh -lc 'echo $TERM'
ft container down ubuntu
ft container reset ubuntu
```

> [!TIP]
> Use `--` with `ft container exec` whenever the inner command has its own flags.

## Shell-Config Development Loop

If you are actively changing `shell-config`, prefer a repo-local build source instead of a moving GitHub branch.

Recommended:

```zsh
ft container build ubuntu \
  --shell-config-source local \
  --shell-config-stage-from /home/timl/projects/tboss/shell-config
```

This stages a sanitized local `shell-config` checkout into the Docker build context automatically.

Use the same pattern for Alpine:

```zsh
ft container build alpine \
  --shell-config-source local \
  --shell-config-stage-from /home/timl/projects/tboss/shell-config
```

### GitHub-Backed Builds

If you want to test the remote-consumer path instead:

```zsh
ft container build ubuntu \
  --shell-config-source github \
  --shell-config-branch feature-ohmyposh_disble_transient_prompt
```

> [!WARNING]
> Moving Git branches are a weak cache key for `docker buildx`. A branch-based build can appear to be one commit behind even after `docker system prune -a`.

If that happens, use one of:

```zsh
ft container build ubuntu --no-cache
docker buildx prune --all
```

For active `shell-config` work, local mode is the more truthful and less frustrating loop.

## Regression and Parity Loop

When changing shell startup, prompt behavior, tool installation, or Dockerfiles, use this repeatable pass:

```zsh
ft container refresh ubuntu
ft container validate ubuntu

ft container refresh alpine
ft container validate alpine

ft doctor
ft container status
```

For deeper shell checks inside each container:

```zsh
fortress-hud
fortress-hud --env
printf '%s\n' ${PATH//:/ }
```

Key things to confirm:

- active profile is `zsh-tll-citadel-dev-fortress`
- `prompt_engine_resolved` matches expectations
- `starship`, `atuin`, `zoxide`, and `fzf` are available
- `${HOME}/.local/bin` is present on `PATH`
- Ubuntu and Alpine remain at functional parity unless a difference is intentional

## JSON and Agentic-Friendly Loops

For machine-readable checks:

```zsh
ft doctor --json
ft doctor --json 'u*'
ft container validate --json ubuntu
ft container validate --json 'alp*'
```

These are the preferred surfaces for future agentic operators and automation layers.

## Completion

The installed `ft` completion artifact lives under:

```zsh
${XDG_DATA_HOME:-$HOME/.local/share}/dev-container-fortress/completions/zsh/_ft
```

To refresh it manually after CLI changes:

```zsh
uv run ft completion install zsh
```

If completion feels broken:

1. reinstall the artifact
2. open a fresh shell
3. confirm the external completion artifact exists
4. confirm your active shell is loading the fortress profile you expect

## Where To Look Next

For related details:

- [README.md](/home/timl/projects/tboss/dev-container-fortress/README.md)
- [docs/container-usage.md](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md)
- [docs/workstation-usage.md](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md)
- [docs/architecture.md](/home/timl/projects/tboss/dev-container-fortress/docs/architecture.md)
- [docs/ROADMAP.md](/home/timl/projects/tboss/dev-container-fortress/docs/ROADMAP.md)
- [docs/milestones/README.md](/home/timl/projects/tboss/dev-container-fortress/docs/milestones/README.md)
