# Containers

This directory contains the container-oriented implementation of the developer
environment.

## Strategy

- Use the distro package manager for base system dependencies
- Use Python + `uv` for pinned tool installation
- Avoid Homebrew inside containers
- Keep Ubuntu and Alpine variants aligned where practical

The downloader now lives as an installable Python package under
`ft/` with a reusable TOML tool manifest. The first implemented tool
is `tenv`.

## Current State

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
