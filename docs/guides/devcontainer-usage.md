# Devcontainer Usage

This document describes how to use the VS Code devcontainer definitions in `dev-container-fortress`.

For day-to-day multi-repo development on your own repos, use a
[workbench](workbench-usage.md): `ft workbench init` renders a devcontainer
around the published image and keeps the repos under `repos/`.

## Available Definitions

The repository currently provides three devcontainer definitions:

- [`.devcontainer/ubuntu/devcontainer.json`](../../.devcontainer/ubuntu/devcontainer.json)
- [`.devcontainer/alpine/devcontainer.json`](../../.devcontainer/alpine/devcontainer.json)
- [`.devcontainer/arch/devcontainer.json`](../../.devcontainer/arch/devcontainer.json) (amd64 hosts only)

Each is a thin wrapper over the matching Dockerfile in `containers/`.

> [!IMPORTANT]
> These files, and `devcontainer/volume/devcontainer.json`, are generated.
> Change the shared data in `ft/src/ft/container_runtime.py` or the renderer in
> `ft/src/ft/devcontainer.py`, then run `ft devcontainer render`. Pre-commit
> and CI run `ft devcontainer render --check` and fail on a hand edit.

These repo-local definitions are best for changing the Dev Fortress image
itself. A workbench is best for using Dev Fortress as the toolchain while
editing several of your own repositories.

## Getting Code In

Code reaches the container in one of two ways. Both work from VS Code and the
devcontainer CLI.

| Use case | Recommended | Why |
| --- | --- | --- |
| VS Code on a checkout you already have on Linux or WSL2 ext4 | Bind mount | Edits are shared with the host, and nothing is cloned twice |
| VS Code with no checkout, or one on `/mnt/c` or another slow host filesystem | Volume, started from the CLI, then attached | Fast everywhere, and it needs only the repository URL |
| Devcontainer CLI terminal mode, with no editor attached | Volume | The container is the whole environment, so the host needs no checkout |
| One long-lived container for several repos, with VS Code windows coming and going | Volume, started from the CLI, then attached | The container keeps running when the windows close |

> [!WARNING]
> Code in a volume lives only in that volume. Push to back it up. Removing the
> volume deletes anything you have not pushed.

### Bind Mount From VS Code

1. Open your `dev-container-fortress` checkout in VS Code.
2. Run `Dev Containers: Reopen in Container` or `Dev Containers: Rebuild and Reopen in Container`.
3. Choose the Ubuntu, Alpine, or Arch definition when prompted.

> [!IMPORTANT]
> Open the checkout folder itself, or a `.code-workspace` file inside it. When
> VS Code opens a `.code-workspace` file, it looks for `.devcontainer/` next to
> that file, so a workspace file in a parent folder gets VS Code's stock
> templates instead of these definitions.

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
after `devcontainer up --remove-existing-container`. Set
`DEV_FORTRESS_IMAGE_REPO` and `DEV_FORTRESS_IMAGE_TAG` to use another image,
such as a local build. They are separate because the devcontainer CLI cuts a
default at its first `:`, so one variable could not default to a tagged image:

```bash
DEV_FORTRESS_IMAGE_REPO=dev-container-fortress DEV_FORTRESS_IMAGE_TAG=workspace-ubuntu-base \
  devcontainer up --workspace-folder . --config "$dcf"
```

> [!NOTE]
> The published image is cold, so the first start installs the Homebrew floor
> into the new volume, which takes a few minutes. Later starts take seconds.

The container keeps running until you stop it or the host restarts. After a
restart, the same `devcontainer up` starts the stopped container again in a few
seconds.

### Volume From VS Code

Start the volume container from the CLI as above, then attach VS Code to it:

1. Run `Dev Containers: Attach to Running Container` and pick the container.
2. Run `File: Open Folder` and pick a repo under `/workspaces`.

Attach as many windows as you like, one per repo. Closing them leaves the
container running, so a terminal session or a later window picks up where you
left off.

> [!NOTE]
> An attached window does not apply `devcontainer.json`'s `customizations`, so
> the recommended extensions are not installed for you. Extensions you install
> live in the container's `~/.vscode-server` and do not survive
> `--remove-existing-container`.

VS Code's own `Dev Containers: Clone Repository in Container Volume` is not
supported. It only looks for `.devcontainer/devcontainer.json` or
`.devcontainer.json` at the repository root, so it never finds the
`.devcontainer/<distro>/` definitions and offers VS Code's stock templates.

> [!WARNING]
> **WSL2 with Docker CE:** a VS Code window that is not connected to WSL runs
> the Windows `docker` CLI, which starts Docker Desktop and works with its
> containers rather than Docker CE's in your distro. Set these in your Windows
> VS Code user settings so every Dev Containers command runs inside the distro:
>
> ```jsonc
> "dev.containers.executeInWSL": true,
> "dev.containers.executeInWSLDistro": "<your-distro>"
> ```
>
> Also keep Docker Desktop's WSL integration off for that distro (Docker
> Desktop: Settings > Resources > WSL integration), or Docker Desktop can take
> over the distro's `docker` CLI and socket when it starts.

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
> [container standards](../design/container-standards.md#persisted-state-contract).

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

Each prints a one-time code and a URL, and the browser opens on the host
through the [host browser bridge](#host-browser-bridge), in VS Code and in
terminal mode. If it does not open, open the URL on the host yourself.
`glab`'s device flow needs GitLab 17.9 or later; for an older self-managed
instance, run `glab auth login` and choose a token.

The image's `/etc/gitconfig` routes HTTPS credentials for `github.com` and
`gitlab.com` through `gh` and `glab`, so pushes keep working after a rebuild
even though `~/.gitconfig` does not persist. Keep the commit identity in the
checkout with `ft identity --local`.

> [!NOTE]
> VS Code copies the host's `~/.gitconfig` into the container and adds a helper
> that forwards the host's Git credentials. A host `~/.gitconfig` that sets a
> per-host helper, such as the one `gh auth setup-git` writes for
> `github.com`, clears VS Code's helper for that host, so pushes go through the
> container's `gh` login. Log in inside the container either way.

## Host Browser Bridge

VS Code opens links on the host only while a window is attached, so the
devcontainers carry their own way out to the host browser, which terminal mode
relies on:

- `initializeCommand` runs on the host before the container starts. It creates
  `~/.local/state/dev-container-fortress/browser-bridge/` and runs
  `ft devcontainer browser-bridge`, which starts one broker on a Unix socket
  there, or reuses the one already running. The broker hands each link to the
  host opener: `DEV_FORTRESS_HOST_BROWSER_OPENER` if set, then `wslview` on
  WSL2, then `$BROWSER`, then `xdg-open`.
- The container bind-mounts that folder at `/tmp/dev-fortress-host-services`,
  and `BROWSER` and `GH_BROWSER` point at `/usr/local/bin/ft-host-browser-open`,
  which writes the link to the socket.

The broker opens only `http` and `https` URLs with a host. It rejects anything
else, such as a `file:` path or a custom-scheme link, without running the
opener, so code in the container cannot use it to launch host programs.

When the host has no `ft`, or no browser opener, the container still starts;
the helper then falls back to the openers inside the container, and you open
the URL on the host yourself. Logins that redirect to a `localhost` callback
reach the host, not the container, so use their device-code option instead.
On macOS, Docker Desktop does not pass Unix sockets through bind mounts, so
the bridge does not connect there yet.

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

Prepare a repo-local directory that contains one or more PEM-formatted `.crt` files, for example `.local/certs/`, as [Container Usage](container-usage.md#optional-corporate-ca-support) describes, then export:

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
