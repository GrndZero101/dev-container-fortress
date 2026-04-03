# Tool Manifest

This directory contains the reusable manifest consumed by the `ft` package.

## Layout

Each tool definition lives under `[tools.<name>]` and should declare:

- `description`
- `version`
- `enabled`
- `install_root`
- `healthcheck`
- optional `variables`
- `integrity`
- one or more `assets`

Each asset should declare:

- `os`
- `arch`
- optional `target` when a tool needs target-specific assets such as Ubuntu versus Alpine
- either `url` or `url_template`
- optional `filename`
- `archive`
- `binary_path`
- optional `variables`
- optional `checksum_asset`

## Reuse Strategy

Prefer config-driven manifests over installer-specific code.

A good default is to keep the installer generic and express tool differences through:

- tool-level `variables`
- asset-level `variables`
- optional `target` matching for distro-specific assets
- renderable fields like `url_template`, `filename`, and integrity URL templates

That lets future GitHub-style tools reuse the same installer behavior while only changing manifest data.

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
> If a tool declares integrity metadata, keep the manifest specific enough that the
> installer can fail closed on mismatches.

Some upstream projects only expose integrity data in human-readable release notes.
For those tools, it is acceptable to omit integrity metadata until a reliable
machine-consumable source exists.
