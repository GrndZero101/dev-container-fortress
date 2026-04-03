# Devcontainer Usage

This document describes how to use the VS Code devcontainer definitions in `dev-container-fortress`.

## Available Definitions

The repository currently provides two devcontainer definitions:

- [`.devcontainer/ubuntu/devcontainer.json`](/home/timl/projects/tboss/dev-container-fortress/.devcontainer/ubuntu/devcontainer.json)
- [`.devcontainer/alpine/devcontainer.json`](/home/timl/projects/tboss/dev-container-fortress/.devcontainer/alpine/devcontainer.json)

Each is a thin wrapper over the matching Dockerfile in `containers/`.

## Open in VS Code

1. Open `/home/timl/projects/tboss/dev-container-fortress` in VS Code.
2. Run `Dev Containers: Reopen in Container` or `Dev Containers: Rebuild and Reopen in Container`.
3. Choose the Ubuntu or Alpine definition when prompted.

## Expected Behavior

After the container opens:

- the runtime user should be `vscode`
- the integrated terminal should default to `zsh`
- the image should already contain `uv`, `ft`, `tenv`, `starship`, `zoxide`, `atuin`, and `fzf`
- `shell-config` should already be cloned and bootstrapped
- the default shell profile should be `zsh-tll-citadel-dev-fortress` unless you changed the build args
- `postCreate` should run a lightweight `ft plan` validation for the selected target

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
ft plan --manifest /home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml --target ubuntu
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

## Optional Corporate CA Support

Corporate CA support is opt-in for devcontainer builds.

Prepare a repo-local directory that contains one or more PEM-formatted `.crt` files, for example `.local/certs/`, then export:

```zsh
export DEV_CONTAINER_FORTRESS_CA_CERT_DIR=.local/certs
```

After that, rebuild and reopen the devcontainer.

If the variable is unset or empty, the CA step is skipped and the build behaves normally.
If it is set, the directory must exist inside the repo and contain valid `.crt` files.

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
