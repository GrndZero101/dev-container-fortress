# M9a Arch Linux Target

## Status

- [ ] Milestone complete
- [x] Active milestone

## Objective

Add Arch Linux as a supported Dev Fortress target, first as a disposable
container target and then as an Ansible-managed host target, without weakening
the repo's reproducibility and verification contract.

The goal is honest parity with the existing Alpine target, not a parallel
bootstrap path. Arch should slot into the same `ft container ...`,
`ft host ...`, and tool-manifest flows that Ubuntu and Alpine already use.

## Exit Criteria

- [x] `containers/arch/Dockerfile` builds a runtime image that follows the same user, XDG, `shell-config`, and `ft install` contract as Ubuntu and Alpine
- [x] Arch system packages come from a pinned Arch Linux Archive snapshot date rather than the moving rolling-release mirrors
- [x] `ft container build|up|validate|down arch` works end to end, including the SSH-capable disposable host target
- [x] `ft/tools/tools.toml` declares Arch assets for every enabled tool and installs them with the existing checksum and signature verification
- [ ] `ft host bootstrap` converges a minimally prepared Arch host through Ansible, including base packages, Docker, `shell-config`, and the login shell
- [x] The Arch Homebrew position is explicit: pacman provides the steady-state host toolchain and the linuxbrew role is skipped on Arch
- [x] Unsupported combinations, starting with Arch on arm64, fail clearly with an actionable message
- [x] A matching `.devcontainer/arch/devcontainer.json` exists as a thin wrapper over the container target
- [x] The Arch image is part of the CI build, smoke-test, and publish matrix
- [x] User-facing docs, `docs/container-standards.md`, and `docs/architecture.md` describe Arch truthfully

## Non-Goals

- [ ] Arch on arm64 or Arch Linux ARM images in the first pass
- [ ] Building or installing AUR packages
- [ ] Replacing the `ft install` container tool contract with pacman-provided userland tools inside images
- [ ] Supporting Arch derivatives such as Manjaro or EndeavourOS beyond best-effort detection
- [ ] Disposable Arch cloud hosts through Terraform
- [ ] Neovim kickstart management on Arch unless it falls out for free

## Design Direction

### Reproducibility on a Rolling Release

Arch has no point releases, so two builds of the same Dockerfile can diverge
within days. The container target should pin system packages to an
[Arch Linux Archive](https://archive.archlinux.org/) snapshot:

- expose the snapshot date as a single build arg such as `ARCH_ARCHIVE_DATE`
- point the pacman mirrorlist at `https://archive.archlinux.org/repos/<date>/$repo/os/$arch`
- bump the date deliberately, the same way tool versions are bumped in the manifest

Host targets cannot be pinned the same way without fighting the distro. Arch
hosts should therefore be documented as converging to current upstream
packages, with Ansible idempotency rather than version pinning as the
guarantee.

### Container Versus Host Tooling

Inside containers, Arch should follow the same rule as every other target:
distro packages for low-level prerequisites, `ft install` for pinned userland
tools. Arch should reuse the existing glibc or musl release assets that Ubuntu
already uses.

On hosts, most Homebrew-managed tools already exist in the official `extra`
repository. Running linuxbrew on top of pacman adds a second package manager
for little gain, so Arch hosts should use pacman for the steady-state
toolchain. This is a documented exception to the "hosts converge on Homebrew"
rule and should be recorded in `docs/architecture.md`.

### Centralize Target Metadata First

Target-specific values in `ft/src/ft/cli.py` are spread across `if target ==`
chains, for example SSH host-target names and forwarded ports. Before adding a
third distro, collapse these into one data-driven target table so adding Arch
is a new row rather than edits in several functions. This also starts the
`M6a` refactor without expanding its scope.

### Architecture Support

The official `archlinux` Docker image is amd64 only. Arch should be declared
amd64-only in the first pass, and `ft` should refuse arm64 Arch requests with a
clear message rather than failing deep inside a build.

## Issue Drafts

### M9a-1 Centralize container target metadata in `ft`

- [x] Problem: target names, SSH host-target names, forwarded ports, and Dockerfile paths are scattered across several `if target ==` branches and a hardcoded `Literal["ubuntu", "alpine"]`
- [x] Scope: introduce one typed target table in `ft` and route `KNOWN_CONTAINER_TARGETS`, SSH naming, ports, Dockerfile lookup, and model validation through it
- [x] Acceptance: existing Ubuntu and Alpine behavior is unchanged, all tests pass, and adding a target touches one table entry plus its assets

### M9a-2 Add the Arch container image

- [x] Problem: there is no Arch image that follows the Dev Fortress container contract
- [x] Scope: add `containers/arch/Dockerfile` with an archive-pinned mirrorlist, the shared user and XDG setup, corporate CA support, `shell-config` install, `ft install`, and the optional gitforge, secrets, and AWS layers from official repositories
- [x] Acceptance: the image builds reproducibly for a fixed `ARCH_ARCHIVE_DATE` and passes the same in-image health checks as Ubuntu

### M9a-3 Add Arch assets to the tool manifest

- [x] Problem: `tools.toml` assets are keyed per target, so Arch has no installable tool entries
- [x] Scope: add `target = "arch"` asset entries for each enabled tool, reusing the verified Linux release artifacts
- [x] Acceptance: `ft plan --target arch --use-manifest-version` resolves every enabled tool, and `ft install --target arch` verifies checksums and signatures where available

### M9a-4 Wire Arch into the disposable container loop

- [x] Problem: `ft container ...`, `scripts/test-container.zsh`, and the devcontainer layer only know Ubuntu and Alpine
- [x] Scope: add the Arch SSH test target with a dedicated forwarded port, extend the validation script, and add `.devcontainer/arch/devcontainer.json`
- [x] Acceptance: `ft container build|up|validate|down arch` and the devcontainer open cleanly against the Arch image

### M9a-5 Add Arch host roles to Ansible

- [x] Problem: the host playbook gates roles on Ubuntu and Alpine facts only
- [x] Scope: add a `dev_fortress_arch_base_packages` role using `community.general.pacman`, add Arch entries to the native bootstrap command-package map, gate roles on `os_family == 'Archlinux'`, install Docker from the official `docker` package, and skip linuxbrew on Arch
- [ ] Acceptance: `ft host bootstrap <arch-target> --check` reports cleanly, a real run converges, and a second run reports no changes
  - Verified against the disposable SSH target; the Docker role still needs a systemd Arch `workstation` or `cloud` host

### M9a-6 Fail clearly on unsupported Arch combinations

- [x] Problem: arm64 Arch requests would otherwise fail late and confusingly inside image builds or package installs
- [x] Scope: reject Arch on arm64 early in `ft` and in the Ansible target contract with an actionable message
- [x] Acceptance: unsupported combinations stop before any build or package work, and tests cover the refusal

### M9a-7 Add Arch to CI and publishing

- [x] Problem: an Arch image that CI never builds will rot quickly on a rolling release
- [x] Scope: add Arch to the build, smoke-test, and GHCR publish matrix as amd64 only
- [ ] Acceptance: CI builds and smoke-tests the Arch image on every relevant change and publishes `arch`, `arch-v*`, and `arch-sha-*` tags

### M9a-8 Update documentation

- [x] Problem: roughly fifteen docs enumerate supported targets and would become inaccurate
- [x] Scope: update `README.md`, `containers/README.md`, `ansible/README.md`, `docs/container-standards.md`, `docs/architecture.md`, usage docs, and the roadmap
- [x] Acceptance: every doc that lists supported targets includes Arch with its amd64-only and no-Homebrew caveats

## Verification Notes

- [x] `uv run pytest ft/tests` passes before and after the target-table refactor
- [x] Two builds with the same `ARCH_ARCHIVE_DATE` produce the same pacman package set
- [x] `ft container validate arch` passes against a fresh container
- [x] `ft host bootstrap` against the disposable Arch SSH target converges and is idempotent on a second run
- [x] `ansible-lint` and the playbook syntax check pass with the new role
- [x] Requesting Arch on arm64 fails early with a clear message
- [ ] CI builds, smoke-tests, and publishes the Arch image

## Branch and Merge Plan

- [x] Branch from `main` as `feat/m0009a-arch-linux-target`
- [x] Land `M9a-1` as the first verified checkpoint before adding Arch-specific files
- [x] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once container and host targets both pass verification
- [ ] Squash merge into `main`

## Decisions

- Arch host bootstrap runs a full `pacman -Syu` before installing packages,
  because Arch does not support partial upgrades. Operators can opt out with
  `dev_container_fortress_arch_full_upgrade: false`.
- Docker is managed by default on Arch `workstation` and `cloud` targets, the
  same as Ubuntu.

## Progress Notes

- Implementation landed on `feat/m0009a-arch-linux-target`: target registry,
  Arch Dockerfile, manifest assets, devcontainer, CI matrix entry, Ansible
  roles, and docs.
- Verified locally: 164 `ft` tests, `ruff`, `ansible-lint` (production
  profile), playbook syntax check, `markdownlint`, `docker buildx build
  --check`, real download and checksum verification of every Arch-specific
  manifest asset, and the CA installer plus user-creation block on the
  `archlinux:base` image.
- Verified on an operator machine (WSL2, amd64) on 2026-10-17:
  - `ft container build arch` builds the full runtime image and passes every
    in-image health check
  - an uncached rebuild of the `arch-base` stage for `ARCH_ARCHIVE_DATE`
    `2026/10/01` yields the identical 158-package `pacman -Q` set
  - `ft container validate arch` passes every check against a fresh container
  - `ft host validate dev-fortress-arch` passes doctor, check mode, a real
    bootstrap, and a second pass with `changed=0`
  - the devcontainer opens through `@devcontainers/cli` 0.89.0 and its
    `postCreateCommand` succeeds
- Still open:
  - the Docker role on Arch is unexercised, because it requires systemd and
    only runs on `workstation` and `cloud` targets, which the disposable
    container is not
  - CI build and publish of the Arch image, which first runs when the branch
    lands on `main`; `publish-images.yml` does not run on pull requests
- Known caveat: `become` tasks on Arch log `Module invocation had junk after
  the JSON data` warnings. systemd 262 emits OSC 3008 context escape sequences
  around privileged sessions. Ansible still parses the module result, so the
  warnings are cosmetic.
