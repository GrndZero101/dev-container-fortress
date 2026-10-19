# Devcontainer Usage

This document describes how to use the VS Code devcontainer definitions in `dev-container-fortress`.

For day-to-day multi-repo development, prefer the separate `tboss-workspace`
orchestrator scaffold. It consumes the published
`ghcr.io/grndzero101/dev-container-fortress:ubuntu-full` image by default and
keeps child repositories under `repos/`.

## Available Definitions

The repository currently provides three devcontainer definitions:

- [`.devcontainer/ubuntu/devcontainer.json`](../.devcontainer/ubuntu/devcontainer.json)
- [`.devcontainer/alpine/devcontainer.json`](../.devcontainer/alpine/devcontainer.json)
- [`.devcontainer/arch/devcontainer.json`](../.devcontainer/arch/devcontainer.json) (amd64 hosts only)

Each is a thin wrapper over the matching Dockerfile in `containers/`.

These repo-local definitions are best for changing the Dev Fortress image
itself. The orchestrator scaffold is best for using Dev Fortress as the
workspace toolchain while editing multiple child repositories.

## Getting Code In

Code reaches the container in one of two ways. Both work from VS Code and the
devcontainer CLI.

| Use case | Recommended | Why |
| --- | --- | --- |
| VS Code on a checkout you already have on Linux or WSL2 ext4 | Bind mount | Edits are shared with the host, and nothing is cloned twice |
| VS Code with no checkout, or one on `/mnt/c` or another slow host filesystem | Volume | Fast everywhere, and it needs only the repository URL |
| Devcontainer CLI terminal mode, with no editor attached | Volume | The container is the whole environment, so the host needs no checkout |

> [!WARNING]
> Code in a volume lives only in that volume. Push to back it up. Removing the
> volume deletes anything you have not pushed.

### Bind Mount From VS Code

1. Open your `dev-container-fortress` checkout in VS Code.
2. Run `Dev Containers: Reopen in Container` or `Dev Containers: Rebuild and Reopen in Container`.
3. Choose the Ubuntu, Alpine, or Arch definition when prompted.

### Volume From VS Code

1. Run `Dev Containers: Clone Repository in Container Volume`.
2. Enter the repository URL, for example
   `https://github.com/GrndZero101/dev-container-fortress`.
3. Choose the Ubuntu, Alpine, or Arch definition when prompted.

VS Code clones into a new volume and builds from the definitions inside the
clone, so the repository must carry them, as this one does.

### Bind Mount From the Devcontainer CLI

From the checkout:

```bash
devcontainer up --workspace-folder . --config .devcontainer/ubuntu/devcontainer.json
devcontainer exec --workspace-folder . --config .devcontainer/ubuntu/devcontainer.json zsh -l
```

### Volume From the Devcontainer CLI

`devcontainer/volume/devcontainer.json` runs the published Ubuntu image with a
named volume at `/workspaces`. The CLI needs a host folder to key the
container and its volumes on, but nothing is mounted from it, so an empty
folder per environment is enough. The code volume is named after that folder,
so give each environment a distinct folder name:

```bash
dcf=/path/to/dev-container-fortress/devcontainer/volume/devcontainer.json
mkdir -p ~/boxes/demo && cd ~/boxes/demo
devcontainer up --workspace-folder . --config "$dcf"
devcontainer exec --workspace-folder . --config "$dcf" zsh -l
```

Inside the container, log in and clone into `/workspaces`:

```zsh
ft identity --login github
gh repo clone owner/repo
cd repo && ft identity --local
```

Run the same `up` and `exec` later to come back to the same state, including
after `devcontainer up --remove-existing-container`. Set `DEV_FORTRESS_IMAGE`
to use another image, such as a local build:

```bash
DEV_FORTRESS_IMAGE=dev-container-fortress:workspace-ubuntu-base devcontainer up --workspace-folder . --config "$dcf"
```

> [!NOTE]
> The published image is cold, so the first start installs the Homebrew floor
> into the new volume, which takes a few minutes. Later starts take seconds.

## Expected Behavior

After the container opens:

- the runtime user should be `vscode`
- the integrated terminal should default to `zsh`
- the image should already contain `uv`, `ft`, `tenv`, `starship`, `zoxide`, `atuin`, and `fzf`
- `shell-config` should already be cloned and bootstrapped
- the default shell profile should be `zsh-tll-citadel-dev-fortress` unless you changed the build args
- on Ubuntu and Arch, `postStartCommand` runs `ft-brew-floor`, which installs any missing Homebrew floor formulae into the brew volume; the first start seeds the volume from the image, so it is quick
- on Alpine, `postCreate` runs a lightweight `ft plan` validation

## Persisted State

Each definition mounts named Docker volumes so shell history, navigation
state, and Claude Code survive `Rebuild Container`:

| Volume | Container path | Holds |
| --- | --- | --- |
| `dev-fortress-state-<id>` | `~/.local/state` | zsh history, Neovim undo and shada |
| `dev-fortress-zoxide-<id>` | `~/.local/share/zoxide` | zoxide directory database |
| `dev-fortress-atuin-<id>` | `~/.local/share/atuin` | atuin history database |
| `dev-fortress-claude-<id>` | `~/.claude` | Claude Code config and login |
| `dev-fortress-claude-versions-<id>` | `~/.local/share/claude` | Claude Code versions, including self-updates |
| `dev-fortress-gh-<id>` | `~/.config/gh` | GitHub CLI login (Ubuntu and Arch only) |
| `dev-fortress-glab-<id>` | `~/.config/glab-cli` | GitLab CLI login (Ubuntu and Arch only) |
| `dev-fortress-brew-<id>` | `/home/linuxbrew/.linuxbrew` | Homebrew prefix (Ubuntu and Arch only) |

`<id>` is the `${devcontainerId}` that VS Code computes per dev container, so the
Ubuntu, Alpine, and Arch definitions keep separate state. The volume definition
adds `dev-fortress-src-<folder>` at `/workspaces` for the code itself, named
after the host folder because the devcontainer CLI does not expand
`${devcontainerId}` there.

> [!IMPORTANT]
> The image owns the rest of `~/.local/share`, including `uv`, the managed
> Python, and `ft`. Do not add a mount over `~/.local/share` or `~/.local`; it
> hides those installs and breaks `ft`. See the persisted state contract in
> [container standards](container-standards.md#persisted-state-contract).

To start from clean state, remove the volumes after closing the container:

```bash
docker volume ls --filter name=dev-fortress-
docker volume rm <volume-name>
```

## Forge Login and Pushing

`gh` and `glab` come from the Homebrew floor on Ubuntu and Arch; the Alpine
image does not include them. Their logins persist in the `gh` and `glab`
volumes. Both use a device code, so they work in VS Code and in terminal mode:

```zsh
ft identity --login github   # gh auth login --web, then gh auth setup-git
ft identity --login gitlab   # glab auth login --device
```

Each prints a one-time code and a URL. In VS Code the browser opens on the
host; in terminal mode, open the URL on the host yourself. `glab`'s device flow
needs GitLab 17.9 or later; for an older self-managed instance, run
`glab auth login` and choose a token.

The image's `/etc/gitconfig` routes HTTPS credentials for `github.com` and
`gitlab.com` through `gh` and `glab`, so pushes keep working after a rebuild
even though `~/.gitconfig` does not persist. Keep the commit identity in the
checkout with `ft identity --local`.

> [!TIP]
> VS Code also copies the host's `~/.gitconfig` and forwards the host's Git
> credentials into the container, so pushing from VS Code can work without a
> container login. The `gh` and `glab` logins are still needed for their own
> commands.

## Optional Claude Code

The devcontainers install Claude Code on start when the `claude-code` option
is selected. They read the selection only from `DEV_CONTAINER_FORTRESS_OPTIONS`
in the environment VS Code starts from, not from the host's `options.toml`:

```bash
export DEV_CONTAINER_FORTRESS_OPTIONS=claude-code
code .
```

`postStartCommand` runs `ft-ensure-claude-code --if-selected`. The first start
runs the native installer; later starts reuse the persisted version, including
any self-update, without downloading again.

## Validate the Devcontainer

Open a terminal in the container and run:

Ubuntu:

```zsh
whoami
uv --version
readlink ~/.zshenv
cat ${XDG_CONFIG_HOME:-$HOME/.config}/shell-config/active-profile
command -v csm
starship --version
zoxide --version
atuin --version
fzf --version
ft-brew-floor
gh --version
glab --version
tenv --version
```

Alpine:

```zsh
whoami
uv --version
readlink ~/.zshenv
cat ${XDG_CONFIG_HOME:-$HOME/.config}/shell-config/active-profile
command -v csm
starship --version
zoxide --version
atuin --version
fzf --version
ft plan --manifest /home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml --target alpine
tenv --version
```

Arch: run the Ubuntu checks.

## Optional Corporate CA Support

Corporate CA support is opt-in for devcontainer builds.

Prepare a repo-local directory that contains one or more PEM-formatted `.crt` files, for example `.local/certs/`, then export:

```zsh
export DEV_CONTAINER_FORTRESS_CA_CERT_DIR=.local/certs
```

After that, rebuild and reopen the devcontainer.

If the variable is unset or empty, the CA step is skipped and the build behaves normally.
If it is set, the directory must exist under the repo's `.local/` and contain valid `.crt` files; `.dockerignore` keeps every other operator path out of the build context.

> [!TIP]
> If you change `DEV_CONTAINER_FORTRESS_CA_CERT_DIR`, use `Dev Containers: Rebuild and Reopen in Container` so the build arg is applied again.

## Shell-Config Source Configuration

Devcontainers can use either a GitHub-based `shell-config` source or a repo-local source passed through build args.

GitHub mode example:

```zsh
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_SOURCE=github
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_REPO_URL=https://github.com/GrndZero101/shell-config.git
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_BRANCH=main
```

Local mode example:

```zsh
zsh ./scripts/stage-shell-config.zsh /absolute/path/to/shell-config
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_SOURCE=local
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_LOCAL_DIR=.local/sources/shell-config
```

You can also change the default built-in profile and whether fortress `zinit` is installed during image build:

```zsh
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_PROFILE_DEFAULT=zsh-tll-citadel-dev-fortress
export DEV_CONTAINER_FORTRESS_SHELL_CONFIG_INSTALL_ZINIT=1
```

> [!TIP]
> Runtime shells can still override the active profile with `SHELL_CONFIG_PROFILE` after the container starts.
