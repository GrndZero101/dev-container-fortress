# Containers

This directory contains the container-oriented implementation of the developer
environment.

See [Container Standards](../docs/container-standards.md) for the shared
runtime contract that container targets should follow.

For user-facing build and run instructions, see [Container Usage](/home/timl/projects/tboss/dev-container-fortress/docs/container-usage.md).

## Strategy

- Use the distro package manager for base system dependencies
- Use Python + `uv` for pinned tool installation
- Avoid Homebrew inside containers
- Keep Ubuntu and Alpine variants aligned where practical
- Use a non-root runtime user for day-to-day development inside the container

The downloader now lives as an installable Python package under
`ft/` with a reusable TOML tool manifest. The first implemented tool
is `tenv`.

## Current State

The Ubuntu and Alpine Dockerfiles now use a shared split bootstrap strategy:

- copy `uv` from Astral's distroless image for build-time package work
- install `uv` again with Astral's shell installer for the final runtime user
- install managed Python 3.14 with `uv` so the `ft` package runs without depending on distro Python versions
- install the `ft` CLI with `uv tool install` into the runtime user's XDG-managed tool directories
- keep runtime state under the user's home directory rather than a custom `/opt` tree
- run the final container as a non-root `vscode` user with `sudo`
- clone or copy `shell-config` into the runtime user's XDG config tree and run `csm bootstrap`
- set the default shell profile to `zsh-tll-citadel-dev-fortress` unless a different build-time default is requested
- install fortress `zinit` support by default so the richer shell profile is ready on first launch
- pre-create minimal Zsh startup files so the container shell is non-interactive on first launch

The Dockerfiles now resolve and install `tenv`, `starship`, `zoxide`, and `atuin` through the packaged downloader entrypoint, while `fzf` comes from the distro package manager.

The Python tool installer currently provides:

- manifest loading
- host platform detection
- installation planning
- archive download and extraction
- checksum verification from upstream checksum manifests
- `tenv`, `starship`, `zoxide`, and `atuin` installation for Linux `amd64` and `arm64`
- target-specific asset selection for Ubuntu versus Alpine where needed

Planned follow-up work:

- optional signature verification where upstream supports it
- host-side corporate CA support through Ansible
- broader tool coverage beyond the current interaction baseline

## Devcontainer Targets

VS Code should see two devcontainer definitions under `.devcontainer/`:

- `.devcontainer/ubuntu/devcontainer.json`
- `.devcontainer/alpine/devcontainer.json`

Each stays a thin wrapper over the matching Dockerfile and only runs a lightweight `ft plan` validation in `postCreate`.

## Local Build

Use Docker Buildx for local validation:

```zsh
docker buildx build --load -f containers/ubuntu/Dockerfile -t dev-container-fortress:ubuntu-test .
docker buildx build --load -f containers/alpine/Dockerfile -t dev-container-fortress:alpine-test .
```

## Optional Corporate CA Support

Corporate CA trust is now available as an explicit opt-in for container and devcontainer builds.

To use it with direct Docker builds, place one or more PEM-formatted `.crt` files in a directory under the repo root, for example `.local/certs/`, and pass that repo-relative directory path:

```zsh
docker buildx build --load \
  --build-arg CORPORATE_CA_CERT_DIR=.local/certs \
  -f containers/ubuntu/Dockerfile \
  -t dev-container-fortress:ubuntu-test .
```

The same pattern works for Alpine by swapping the Dockerfile path.

For VS Code devcontainers, export the same repo-relative directory path before you reopen in container:

```zsh
export DEV_CONTAINER_FORTRESS_CA_CERT_DIR=.local/certs
```

If the variable is unset or empty, the CA installation step is skipped and the build behaves exactly as before. If the variable is set, the build requires the directory to exist and to contain at least one valid PEM `.crt` file.

> [!IMPORTANT]
> This feature is active only when you opt in. Certificates are loaded as individual `.crt` files and copied into the distro trust setup. On Ubuntu this matches Canonical's documented `/usr/local/share/ca-certificates` plus `update-ca-certificates` flow. On Alpine we use the same `update-ca-certificates` integration as an implementation choice based on Alpine examples. Keep the directory inside the Docker build context, and do not commit private cert material. Add it under an ignored path such as `.local/certs/`.

## Shell-Config Source Options

Container builds now support two `shell-config` source modes:

- `github` (default): clone from `SHELL_CONFIG_REPO_URL` and `SHELL_CONFIG_BRANCH`
- `local`: copy from a repo-relative directory inside the Docker build context via `SHELL_CONFIG_LOCAL_DIR`

Build args:

- `SHELL_CONFIG_SOURCE`
- `SHELL_CONFIG_REPO_URL`
- `SHELL_CONFIG_BRANCH`
- `SHELL_CONFIG_LOCAL_DIR`
- `SHELL_CONFIG_PROFILE_DEFAULT`
- `SHELL_CONFIG_INSTALL_ZINIT`

> [!NOTE]
> Runtime shells can still override the selected profile with `SHELL_CONFIG_PROFILE`. The build-time default only determines the saved initial profile and the default exported environment inside the image.

For local-source testing from an existing absolute host path, stage it into the build context with [`scripts/stage-shell-config.zsh`](/home/timl/projects/tboss/dev-container-fortress/scripts/stage-shell-config.zsh).
