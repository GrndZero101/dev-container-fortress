# Container Usage

This document describes how to build and use the Ubuntu and Alpine images directly with Docker.

See [Container Standards](/home/timl/projects/tboss/dev-container-fortress/docs/container-standards.md) for the container contract and [containers/README.md](/home/timl/projects/tboss/dev-container-fortress/containers/README.md) for implementation details.

## Current Status

Works today:

- Ubuntu image build
- Alpine image build
- non-root `vscode` runtime user
- XDG-style home layout
- runtime `uv`
- installed `ft` CLI
- installed interaction baseline: `starship`, `zoxide`, `atuin`, and `fzf`
- installed `tenv`
- cloned and bootstrapped `shell-config`
- default fortress shell profile
- optional opt-in corporate CA support for builds

## Build the Images

Ubuntu:

```zsh
docker buildx build --load   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-test   .
```

Alpine:

```zsh
docker buildx build --load   -f containers/alpine/Dockerfile   -t dev-container-fortress:alpine-test   .
```

## Run the Images

Ubuntu:

```zsh
docker run --rm -it dev-container-fortress:ubuntu-test zsh
```

Alpine:

```zsh
docker run --rm -it dev-container-fortress:alpine-test zsh
```

## Validate the Runtime

Inside either container:

```zsh
whoami
echo $HOME
echo $XDG_DATA_HOME
echo $PATH
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

For the Alpine image, change `--target ubuntu` to `--target alpine`.

Expected behavior:

- `whoami` prints `vscode`
- `HOME` is `/home/vscode`
- `uv` is available
- `~/.zshenv` points at the installed `shell-config` selector
- `csm` is on `PATH`
- the saved active profile is `zsh-tll-citadel-dev-fortress` unless you changed the build-time default
- `starship`, `zoxide`, `atuin`, and `fzf` are all available for interactive shell use
- `ft` can resolve plans for the full enabled tool set
- `tenv` is already installed and runnable

## Optional Corporate CA Support

Corporate CA support is opt-in.

Prepare a directory under the repo root that contains one or more PEM-formatted `.crt` files, for example:

```zsh
mkdir -p .local/certs
cp /path/to/your-root-ca.crt .local/certs/
cp /path/to/your-intermediate-ca.crt .local/certs/
```

Then build with the directory path:

```zsh
docker buildx build --load   --build-arg CORPORATE_CA_CERT_DIR=.local/certs   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-ca-test   .
```

The same pattern works for Alpine.

If `CORPORATE_CA_CERT_DIR` is unset or empty, the CA step is skipped.
If it is set, the build requires:

- the directory to exist
- at least one `.crt` file
- each `.crt` file to parse as a valid PEM certificate

> [!IMPORTANT]
> Keep private certificate material under an ignored path such as `.local/certs/` and do not commit it.

## Shell-Config Source Modes

By default, the images clone `shell-config` from GitHub:

```zsh
docker buildx build --load   --build-arg SHELL_CONFIG_SOURCE=github   --build-arg SHELL_CONFIG_REPO_URL=https://github.com/GrndZero101/shell-config.git   --build-arg SHELL_CONFIG_BRANCH=main   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-test   .
```

To use a repo-local source instead, first stage an existing absolute-path checkout into the repo build context:

```zsh
zsh ./scripts/stage-shell-config.zsh /absolute/path/to/shell-config
```

Then build with local mode:

```zsh
docker buildx build --load   --build-arg SHELL_CONFIG_SOURCE=local   --build-arg SHELL_CONFIG_LOCAL_DIR=.local/sources/shell-config   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-local-shell-config   .
```

> [!TIP]
> Docker cannot see a sibling checkout outside the build context directly. The staging helper copies your chosen host checkout into `.local/sources/shell-config` so the build can consume it.
