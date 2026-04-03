# Tool Manifest

This directory contains the reusable manifest consumed by the `ft` package.

## Layout

Each tool definition lives under `[tools.<name>]` and should declare:

- `description`
- `version`
- `enabled`
- `install_root`
- `healthcheck`
- `integrity`
- one or more `assets`

Each asset should declare:

- `os`
- `arch`
- `url`
- `archive`
- `binary_path`
- `checksum_asset` when checksum verification is enabled

## Environment Variables

Runtime defaults can be supplied through environment variables:

- `FT_MANIFEST`
- `FT_TARGET`
- `FT_SYSTEM`
- `FT_ARCHITECTURE`
- `FT_INSTALL_ROOT`
- `FT_HEALTHCHECK`

## Integrity

Prefer upstream checksum manifests whenever they exist.

> [!IMPORTANT]
> If a tool declares `integrity.checksum_url`, each asset should also declare
> `checksum_asset` so the installer can fail closed on mismatches.

Signature metadata is modeled in the manifest now and can be enforced in a
follow-up step as more tools are added.
