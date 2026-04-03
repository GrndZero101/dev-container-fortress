# Containers

This directory contains the container-oriented implementation of the developer
environment.

## Strategy

- Use the distro package manager for base system dependencies
- Use Python + `uv` for pinned tool installation
- Avoid Homebrew inside containers
- Keep Ubuntu and Alpine variants aligned where practical

## Current State

The Dockerfiles are initial scaffolds.

The Python tool installer currently provides:

- manifest loading
- host platform detection
- planning output

It does not yet perform real downloads or checksum verification.

