# Containers

This directory contains the container-oriented implementation of the developer
environment.

See [Container Standards](../docs/design/container-standards.md) for the shared
runtime contract that container targets should follow.

For user-facing build and run instructions, see [Container Usage](../docs/guides/container-usage.md).

## Strategy

- Use the distro package manager only for base system dependencies
- Use Homebrew for the userland tools on the glibc targets (Ubuntu, Arch), from the same tool-pool set as the hosts, on a per-workspace volume
- Keep the packaged `ft install` downloader for Alpine, which Homebrew does not support
- Keep Ubuntu, Alpine, and Arch variants aligned where practical
- Use a non-root runtime user for day-to-day development inside the container

The downloader is the `ft` Python package under `ft/`, driven by the TOML
manifest that [`ft/tools/README.md`](../ft/tools/README.md) describes.

## Current State

The Ubuntu, Alpine, and Arch Dockerfiles now use a shared split bootstrap strategy:

- copy `uv` from Astral's distroless image for build-time package work
- install `uv` again with Astral's shell installer for the final runtime user
- install the managed Python that the repo-root `.python-version` pins with `uv` so the `ft` package runs without depending on distro Python versions
- install the `ft` CLI with `uv tool install` into the runtime user's XDG-managed tool directories
- install the `ft` zsh completion artifact into the user's XDG-managed data tree so shell-config can load it without vendoring cross-repo files
- keep runtime state under the user's home directory rather than a custom `/opt` tree
- pre-create the user-owned XDG state directory so first-login shell startup can write state safely
- run the final container as a non-root `vscode` user with `sudo`
- clone or copy `shell-config` into the runtime user's XDG config tree and run `csm bootstrap`
- set the default shell profile to `zsh-tll-citadel-dev-fortress` unless a different build-time default is requested
- install fortress `zinit` support by default so the richer shell profile is ready on first launch
- pre-create minimal Zsh startup files so the container shell is non-interactive on first launch
- install Alpine's split `zsh-vcs` package so native zsh prompt fallback can still use `vcs_info`
- on Ubuntu and Arch, write the tool-pool Homebrew floor to `brew-floor.txt` and, for warm builds (`HOMEBREW_FLOOR=warm`, the default), install it into the `vscode`-owned prefix at `/home/linuxbrew/.linuxbrew`; `ft-brew-floor` tops it up at every start
- ship `ft-ensure-claude-code`, which installs Claude Code at container start when the `claude-code` option is selected; Alpine also carries `libgcc` and `libstdc++` and sets `USE_BUILTIN_RIPGREP=0`, which the musl build needs
- on Alpine, restore user-local bin discovery through `/etc/profile.d` because login shells source `/etc/profile`, which otherwise resets `PATH` to system directories only
- on Arch, point pacman at one [Arch Linux Archive](https://archive.archlinux.org/) snapshot through the `ARCH_ARCHIVE_DATE` build arg so the rolling release still yields a reproducible package set

The Ubuntu and Arch images take their userland tools from the Homebrew floor.
The Alpine Dockerfile uses the packaged `ft install` downloader instead,
because Homebrew does not support musl. On Alpine:

- the downloader installs `atuin`, `bat`, `bats`, `fd`, `glow`, `gum`, `jq`,
  `lazygit`, `oh-my-posh`, `starship`, `tenv`, and `zoxide`, resolving the
  latest upstream release at install time by default rather than the
  manifest's fallback version
- `rg` and `nvim` come from `apk`, because upstream publishes no musl build of
  either that covers `arm64`
- `fzf` comes from `apk`, because it is not in the downloader manifest

> [!IMPORTANT]
> The Arch target is amd64 only because the official `archlinux` base image
> has no arm64 build. `ft container build arch` refuses arm64 hosts early, and
> `ft container build all` skips Arch there.

The Python tool installer currently provides:

- manifest loading
- host platform detection
- installation planning
- archive download and extraction
- checksum verification from upstream checksum manifests
- XDG cache reuse for downloaded assets, keyed by tool, target, OS, arch, and resolved version
- installation of every enabled manifest tool for Linux `amd64` and `arm64`
- target-specific asset selection for Ubuntu, Alpine, and Arch where needed

Planned follow-up work:

- optional signature verification where upstream supports it
- host-side corporate CA support through Ansible
- expand the downloader-managed subset toward the declared shared parity target
  in [tool-pool manifest](../ft/tools/tool-pool.toml)

## Devcontainer Targets

VS Code should see three devcontainer definitions under `.devcontainer/`:

- `.devcontainer/ubuntu/devcontainer.json`
- `.devcontainer/alpine/devcontainer.json`
- `.devcontainer/arch/devcontainer.json`

They are generated: run `ft devcontainer render` after changing the shared runtime data or a forwarded Dockerfile build arg. Each stays a thin wrapper over the matching Dockerfile. Ubuntu and Arch run `ft-brew-floor` and the opt-in Claude Code check on every start; Alpine runs a lightweight `ft plan` validation in `postCreate`.

## Building and Testing

[Container Usage](../docs/guides/container-usage.md) covers the `ft container`
loop, the disposable SSH targets, runtime validation, and raw `docker buildx`
builds. [`scripts/test-container.zsh`](../scripts/test-container.zsh) and the
[`justfile`](../justfile) remain as thin shims over `ft`.

## Optional Corporate CA Support

Corporate CA trust is an explicit opt-in for container and devcontainer
builds, through the `CORPORATE_CA_CERT_DIR` build arg. The steps are in
[Container Usage](../docs/guides/container-usage.md#optional-corporate-ca-support)
and, for VS Code, in
[Devcontainer Usage](../docs/guides/devcontainer-usage.md). If the build arg is
unset or empty, the CA step is skipped. If it is set, the directory must exist
and contain at least one valid PEM `.crt` file.

> [!IMPORTANT]
> This feature is active only when you opt in. Certificates are loaded as individual `.crt` files and copied into the distro trust setup. On Ubuntu this matches Canonical's documented `/usr/local/share/ca-certificates` plus `update-ca-certificates` flow. On Alpine we use the same `update-ca-certificates` integration as an implementation choice based on Alpine examples. On Arch the installer uses the p11-kit anchors directory `/etc/ca-certificates/trust-source/anchors` plus `update-ca-trust`. Keep the directory under `.local/`, such as `.local/certs/`: the repo's `.dockerignore` admits no other operator path into the build context, and `.local/` is not committed.

## Shell-Config Source Options

Container builds now support two `shell-config` source modes:

- `github` (default): clone from `SHELL_CONFIG_REPO_URL` and `SHELL_CONFIG_BRANCH`
- `local`: copy from a repo-relative directory under `.local/` via `SHELL_CONFIG_LOCAL_DIR`

Build args:

- `SHELL_CONFIG_SOURCE`
- `SHELL_CONFIG_REPO_URL`
- `SHELL_CONFIG_BRANCH`
- `SHELL_CONFIG_LOCAL_DIR`
- `SHELL_CONFIG_PROFILE_DEFAULT`
- `SHELL_CONFIG_INSTALL_ZINIT`

> [!NOTE]
> Runtime shells can still override the selected profile with `SHELL_CONFIG_PROFILE`. The build-time default only determines the saved initial profile and the default exported environment inside the image.

How to choose a source mode, including staging a local checkout, is in
[Container Usage](../docs/guides/container-usage.md#shell-config-source-modes).
