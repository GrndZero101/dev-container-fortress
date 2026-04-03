# Containers

This directory contains the container-oriented implementation of the developer
environment.

See [Container Standards](../docs/container-standards.md) for the shared
runtime contract that container targets should follow.

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
- pre-create minimal Zsh startup files so the container shell is non-interactive on first launch

The Dockerfiles now resolve and install `tenv` through the packaged downloader
entrypoint.

The Python tool installer currently provides:

- manifest loading
- host platform detection
- installation planning
- archive download and extraction
- checksum verification from upstream checksum manifests
- `tenv` installation for Linux `amd64` and `arm64`

Planned follow-up work:

- optional signature verification where upstream supports it
- optional private CA trust injection for corporate environments
- more tool definitions beyond `tenv`

## Local Build

Use Docker Buildx for local validation:

```zsh
docker buildx build --load -f containers/ubuntu/Dockerfile -t dev-container-fortress:ubuntu-test .
docker buildx build --load -f containers/alpine/Dockerfile -t dev-container-fortress:alpine-test .
```
