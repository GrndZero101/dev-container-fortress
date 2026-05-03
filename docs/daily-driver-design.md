# Daily-Driver Container Design

## Status

This document now reflects the implemented first operator slice plus the
remaining design direction for follow-on work.

Use it to define the first concrete operator contract for a day-to-day Fortress
workstation container.

Implemented today:

- repo-owned workspace profile manifest
- `ft workspace build`
- `ft workspace up`
- `ft workspace enter`
- `ft workspace exec`
- `ft workspace down`
- `ft workspace reset`
- `ft workspace status`
- `ft workspace doctor`
- `ft workspace mount-plan`
- `ft workspace auth doctor`
- repo-owned workspace tool-layer metadata with explicit `state_only` versus future `image_build` modes

Still follow-on work:

- richer profile layering beyond the initial Ubuntu-first base profile
- stronger auth diagnostics
- secrets baseline integration with `M7a`
- disposable EC2 workflow proof as a documented end-to-end operator loop

## Goal

The daily-driver container should let an operator use Dev Fortress to develop
Dev Fortress, `shell-config`, and adjacent repos inside a reproducible
container on top of a thin host.

The first target host types are:

- local Docker hosts
- Ubuntu under WSL2
- disposable Ubuntu EC2 hosts bootstrapped by Dev Fortress

The important design rule is:

- keep the host thin and convergent
- keep the real workstation inside the container

## Why a New Command Group

The current `ft container ...` surface is intentionally shaped around
disposable validation targets:

- deterministic target names such as `ubuntu` and `alpine`
- repo-owned Dockerfiles
- replaceable test containers
- validation, SSH, and parity checks

That surface should remain focused on reproducible target validation.

The daily-driver workflow has different requirements:

- live bind-mounted working copies
- explicit persisted state mounts
- auth and secret handoff
- optional heavier tool layers
- one named workstation instance rather than a distro parity matrix

For that reason, the recommended operator surface is a new `ft workspace ...`
group rather than overloading `ft container ...` with two competing meanings.

## Recommended Command Shape

### Top-Level Group

Recommended new command group:

- `ft workspace ...`

Recommended first-pass commands:

- `ft workspace build <profile>`
- `ft workspace up <profile>`
- `ft workspace enter <profile>`
- `ft workspace exec <profile> -- <command...>`
- `ft workspace down <profile>`
- `ft workspace reset <profile>`
- `ft workspace status [profile]`
- `ft workspace doctor [profile]`

WSL-specific runtime note:

- when the host is WSL-backed, `ft workspace up` should route browser auth flows through a host-side browser bridge and the container helper at `/usr/local/bin/ft-host-browser-open`
- explicit `BROWSER` or `GH_BROWSER` values should still win when the operator wants a custom browser command

Recommended future commands once the core path is stable:

- `ft workspace validate <profile>`
- `ft workspace mount-plan <profile> --json`
- `ft workspace auth doctor <profile>`
- `ft workspace auth validate <profile>`

### Why `workspace` Instead of `container`

Recommended meanings:

- `container` means repo-owned disposable validation targets
- `workspace` means a mounted day-to-day development environment

That keeps operational intent obvious:

- use `ft container ...` to validate Fortress targets
- use `ft workspace ...` to do actual development work inside Fortress

## Profile Model

The first pass should avoid arbitrary free-form container definitions.

Recommended model:

- a small set of named workspace profiles
- one base image family per profile
- explicit optional tool layers per profile

Implemented first-pass layer contract:

- `state_only`: the layer changes runtime state and auth expectations, but does not currently change the image build
- `image_build`: the layer changes the built workspace image through repo-owned Dev Fortress image logic

Current real image-changing layers:

- `gitforge`: installs `gh` and `glab`
- `aws`: installs AWS CLI v2 through a repo-owned container helper that wraps the official AWS installer

Recommended first-pass profiles:

- `ubuntu-base`
- `ubuntu-gitforge`
- `ubuntu-secrets`
- `ubuntu-cloud-aws`
- `ubuntu-cloud-azure`
- `ubuntu-full`

Recommended default human path:

- `ubuntu-base`

Recommended current "most of the time" power-user path:

- `ubuntu-full`

Today that gives you the broadest combined workspace surface for daily use and
for validating that multiple optional layers still compose cleanly in one
image.

The first pass should stay Ubuntu-first even if Alpine remains important for
validation elsewhere.

## First-Pass Runtime Contract

### Container Identity

Recommended deterministic name:

- `dev-fortress-workspace-<profile>`

Recommended image tag shape:

- `dev-container-fortress:workspace-<profile>`

### Required Mounts

Required bind mounts:

- host checkout of `dev-container-fortress`
- host checkout of `shell-config` when actively developing `shell-config`

Recommended in-container layout:

- `/workspace/dev-container-fortress`
- `/workspace/shell-config`

The first pass should make these explicit rather than trying to infer arbitrary
project locations.

### Optional Persisted Mounts

Recommended host-owned persisted roots:

- `/state/workspace/<profile>/cache`
- `/state/workspace/<profile>/share`
- `/state/workspace/<profile>/config-gh`
- `/state/workspace/<profile>/config-glab`
- `${HOME}/.aws`
- `/state/workspace/<profile>/azure`
- `/state/workspace/<profile>/gnupg`
- `/state/workspace/<profile>/gopass`

Recommended in-container mount targets:

- `${XDG_CACHE_HOME}`
- `${XDG_DATA_HOME}`
- `${XDG_CONFIG_HOME}/gh`
- `${XDG_CONFIG_HOME}/glab`
- `${HOME}/.aws`
- `${HOME}/.azure`
- `${HOME}/.gnupg`
- `${XDG_CONFIG_HOME}/gopass`

The precise GPG and password-store paths should remain provisional until `M7a`
chooses the supported secrets baseline.

### Working Directory

Recommended default working directory:

- `/workspace/dev-container-fortress`

That makes self-hosting the default operator path.

## Auth Contract

### SSH

Recommended first supported path:

- prefer SSH agent forwarding when available
- allow an explicit mounted SSH directory as a fallback

Do not:

- bake private SSH keys into the image
- silently copy host keys into image layers

### GitHub and GitLab

Recommended first supported path:

- persist `${XDG_CONFIG_HOME}/gh` and `${XDG_CONFIG_HOME}/glab`
- allow normal `gh auth login` and `glab auth login` flows inside the container

That keeps forge login state outside the image and survives container
replacement without pretending the host itself is long-lived.

### AWS and Azure

Recommended first supported path:

- mount `${HOME}/.aws`
- mount `${HOME}/.azure`

Do not assume the first pass must solve every cloud auth mode.

The first pass should truthfully support the common file-backed CLI state path
before expanding into browser handoff, SSO helpers, or cloud-native workload
identity options.

Current workspace-container auth guidance:

- browser launch from the workspace container is supported through the host
  browser bridge
- localhost callback OAuth is not guaranteed in plain Docker workspaces because
  callback listeners inside the container are not automatically reachable from
  the host browser
- for AWS CLI SSO in plain workspaces, prefer `aws sso login --use-device-code`
- native hosts should keep their normal localhost callback behavior
- richer integration surfaces such as editor-assisted devcontainers may behave
  better, but should be treated as a separate target contract

### GPG, `pass`, and `gopass`

Recommended first supported path:

- mount a host-owned GPG state directory
- mount a host-owned password-store or `gopass` config path
- document one explicit supported agent model

Do not claim support until:

- key location
- store location
- restore flow
- trustdb or agent expectations

are explicit and documented.

## Tool Layering Contract

The base image should remain lean.

Recommended first-pass layer split:

- `base`: current shell and operator baseline
- `gitforge`: add `gh` and `glab`
- `secrets`: add `gpg`, `pass`, and or `gopass` once selected
- `aws`: add AWS CLI
- `azure`: add Azure CLI

Recommended rule:

- heavy CLIs are opt-in
- optional layers may be combined into a profile
- the default workspace should not pull every large CLI automatically

Implemented first pass:

- the repo-owned workspace manifest now declares layer metadata explicitly
- `gitforge` is the first real `image_build` layer and enables a build-arg-driven Ubuntu workspace variant
- `aws`, `azure`, and `secrets` remain honest `state_only` markers for now
- `ft workspace build` reports whether selected layers change the image or only affect runtime expectations
- `ft workspace mount-plan --json` exposes the resolved layer metadata for automation and review

## Recommended First-Pass UX

### Local or WSL2

Expected human loop:

1. bootstrap the repo locally
2. ensure Docker is healthy
3. run `ft workspace build ubuntu-base`
4. run `ft workspace up ubuntu-base`
5. run `ft workspace enter ubuntu-base`
6. work inside `/workspace/dev-container-fortress`

### Disposable EC2

Expected human loop:

1. provision the disposable Ubuntu EC2 host
2. run `ft host bootstrap <target>`
3. clone `dev-container-fortress` and `shell-config` onto the host
4. run `ft workspace up ubuntu-base`
5. develop inside the mounted container
6. destroy the host when done

This is the most important proof loop because it exercises the real
reproducibility claim.

## Implementation Guidance

Recommended implementation order:

1. define the workspace profile schema
2. implement mount-plan resolution in Python
3. add `ft workspace up`, `enter`, `exec`, `down`, `status`
4. add one supported Ubuntu-first profile
5. prove the local and WSL2 path
6. prove the disposable EC2 path
7. add optional tool layers
8. add auth and secrets validation helpers

Recommended internal design rules:

- keep Docker command assembly in reusable helpers
- keep rendering separate from runtime planning
- support JSON output for mount or auth plans early
- keep `container` and `workspace` business logic separate

## Open Questions

- Should workspace profiles live in a repo-owned manifest, user config, or both?
- Should persisted state defaults live under the operator's home directory or under an explicit workspace root such as `/state/workspace`?
- Should `ft workspace build` materialize separate Dockerfiles, use build args, or compose profiles from one base Dockerfile?
- When `shell-config` is not being actively developed, should the workspace mount it read-only, copy it into the image, or omit the mount entirely?
- Should the first pass support only one workspace instance at a time or allow multiple named instances?

## Recommendation

The strongest next move is:

- add `ft workspace ...` as a separate operator surface
- make Ubuntu-first bind-mounted self-hosting the default path
- keep auth and secrets explicit and incremental
- prove the disposable EC2 loop before broadening the feature set
