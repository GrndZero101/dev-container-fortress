# M5c Composable Container Workspaces

## Status

- [ ] Milestone complete
- [x] Active milestone

## Objective

Make the container targets long-lived, composable development environments
that work like a traditional workstation, rather than tightly pinned build
artifacts. Standardize their userland on Homebrew, the same toolchain the host
targets use, and make the VS Code devcontainer and the devcontainer CLI
genuinely useful for daily development.

These environments may be disposable, but they are expected to last days,
months, or years. They need to be quick to compose and safe to grow at will.
They do not need to be byte-for-byte deterministic.

## Target Use Cases

Dev Fortress serves four use cases. `M5b` owns the first two and this
milestone owns the last two:

1. a new or existing Ubuntu install on a direct host, whether physical, virtual,
   or cloud (`M5b`)
2. a new or existing WSL2 Ubuntu install on a Windows host (`M5b`)
3. a VS Code devcontainer, or the devcontainer CLI driven by an editor, with a
   clear answer for how the code gets in (`M5c`)
4. a devcontainer CLI "terminal mode" in which the container itself is the dev
   environment, with no editor attached (`M5c`)

## Exit Criteria

- [ ] The container images install their userland tools through Homebrew, with the same bundle model as the host targets, and the decision is recorded in `docs/architecture.md` and `docs/container-standards.md`
- [ ] Tools added inside a running container with `brew install` persist across container replacement where that is intended, or the docs state clearly that they do not
- [ ] Claude Code can be selected for every container target through the `M5b` option model, installs through its native installer, and updates itself in place
- [ ] The devcontainer documents and supports one recommended way to get code in, either a bind mount of the host checkout or a clone into a volume, and the other way works as a documented variant
- [ ] A devcontainer CLI terminal mode works end to end: `up`, enter a shell, develop, commit, push, and come back later to the same state
- [ ] `ft workspace` and the devcontainer CLI either share one definition or have a documented reason to differ, so there are no two overlapping container paths

## Non-Goals

- [ ] Byte-for-byte reproducible image builds
- [ ] Dropping the distro package manager for low-level system prerequisites
- [ ] New container distros

## Design Direction

### Homebrew in Containers

Recorded on 2026-10-18: standardize on Homebrew in the container targets too.
This reverses the earlier guidance that kept Homebrew out of the images in
favour of pinned `uv` and binary installs. The reason is that the goal is a
rapid, composable development environment, and running one toolchain on hosts
and containers is simpler than maintaining two. A similar setup is already
proven in a work environment.

Keep from the current design:

- distro packages for the system substrate (`git`, `curl`, build tools, GPG)
- the non-root `vscode` user, who owns the Homebrew prefix so `brew install`
  works without `sudo`
- `shell-config` as the owner of shell behavior

Decided on 2026-10-19:

- `uv` stays on Astral's native installer everywhere, never Homebrew or a
  distro package. Bootstrap depends on it, and only the native install can
  `uv self update`. Homebrew replaces the `ft` tool-pool downloads (`tenv`,
  `starship`, `zoxide`, `atuin`, and the rest), not `uv`
- Alpine tries glibc compatibility first, so it can stay on the Homebrew
  path. If that fails, record why and fall back to its current installers.
  The M5c-1 spike found it fails; see the results below
- the Homebrew prefix and its cache live on a persisted volume per
  workspace, never shared between containers, so ad hoc `brew install`s
  survive container replacement. Bootstrap brings the volume up to the
  baseline bundle on every start, and a clean rebuild option wipes the
  volume and reinstalls Homebrew from scratch
- containers use the same bundle as the hosts (`brew/Brewfile` plus
  `brew/Brewfile.linux`). When no host bundle is available, such as a
  devcontainer opened without a Dev Fortress host or a profile that opts out,
  they fall back to the repo's own copy of that bundle in the image. It
  already covers the DevOps tools and everything Dev Fortress needs to run

To work out:

- the prefix must stay at `/home/linuxbrew/.linuxbrew` for bottles to pour,
  so the volume mounts there rather than under XDG paths
- `brew/Brewfile` lists `uv`, which puts a second `uv` beside the Astral
  install on hosts. Drop it so there is one `uv`

### M5c-1 Spike Results

Measured on 2026-10-19 on amd64 (WSL2, 32 cores) against the tool-pool
Homebrew set: `[homebrew.common]` plus `[homebrew.linux]` from
`ft/tools/tool-pool.toml`, minus `uv`. That is 44 formulae, which resolve to
112 installed formulae once their dependencies are included. The spike
extended the `workspace-ubuntu-base` image with Homebrew's prerequisites
(`build-essential`, `procps`, `file`) and the `vscode`-owned prefix.

| Measure | Result |
| --- | --- |
| Bottle coverage, `x86_64_linux` and `arm64_linux` | complete for the whole dependency closure (96 formulae); three are architecture-independent `all` bottles; nothing builds from source |
| Prerequisite layer | 27 s build, +0.40 GB image |
| Homebrew baked into the image | 209 s build, +2.05 GB image |
| Prefix size on a volume | 1.5 GB |
| Model A first start: baked image seeds a fresh named volume | 13.5 s |
| Model B first start: prerequisites only, install into an empty volume | 151 s |
| Later starts, and the floor check with nothing missing | 0.4 s |
| `brew install hello`, then replace the container | `hello` still runs |
| Toolchain | Homebrew used the host glibc (2.43) and pulled no brewed gcc or glibc |

Decision: **go** for the glibc targets, with model A.

- Bake the floor into the image, and mount the prefix as a per-workspace
  **named Docker volume**, `dev-fortress-brew-<profile>`. Docker copies the
  image's prefix into a fresh named volume, so a new workspace has the full
  floor in about 13 s. A bind mount from host state, which `ft workspace`
  uses for every other path, does not seed, so it would always pay model B's
  151 s.
- Run the floor check on every start. It costs 0.4 s and installs only what is
  missing, so a newer image's additions reach existing volumes. It does not
  upgrade what is already there; that stays with `brew upgrade`.
- Clean rebuild: remove the volume, and it re-seeds from the image. For a
  completely fresh Homebrew, rebuild the image without cache first.
- `~/.local/bin` comes before the Homebrew prefix on `PATH`, so the old
  downloaded tools shadow the Homebrew ones until M5c-2 removes them. In the
  spike, `nvim` still resolved to `~/.local/bin`.
- `python@3.15` arrives as a dependency. It is only a library for other
  formulae; Dev Fortress code keeps running on the uv-managed Python.
- The image grows by about 2.4 GB in total. The published GHCR images grow by
  the same amount, which buys a first start under a minute without network
  installs.

Not measured: arm64 build and start times, because this machine has no arm64
builder. Bottle coverage is complete, so arm64 should behave like amd64;
confirm it on a Graviton host from the EC2 test fleet. Arch is untested.
It is glibc-based and rolling, so expect it to behave like Ubuntu.

Alpine: **no-go**, so it keeps its current installers.

- `gcompat` fails. It shims musl, so Homebrew cannot detect a glibc version
  and refuses to install its portable Ruby.
- The community `sgerrand/alpine-pkg-glibc` package (glibc 2.35, unmaintained
  since 2023) gets bottles pouring only after replacing Alpine's
  `/usr/bin/ldd`, which Homebrew hardcodes. Even then, 2.35 is below
  Homebrew's minimum, so it installs its own glibc 2.39, gcc 16, and binutils
  (about 600 MB) before the first formula.
- That package has no arm64 build, so this path cannot cover arm64 Alpine at
  all.

### Claude Code

Install Claude Code with its native installer rather than a package manager,
so it can keep itself up to date between rebuilds. It is an optional component,
not baseline, because it is large (about 270 MB).

Already done in `M5b`: the `claude-code` option and the
`dev_fortress_claude_code` role install it on hosts. Still missing for
containers: the images do not install it, and `ft host bootstrap --mode
workspace` deliberately skips options. This milestone wires the same option
into the images and adds a persisted mount for its config and login state,
like the other CLI auth paths.

### Getting Code Into a Devcontainer

- **Bind mount** the host checkout: edits are shared with the host and nothing
  is cloned twice, but the checkout must already exist, and performance
  depends on the host filesystem (fine on WSL2's ext4, slow from `/mnt/c`)
- **Clone into a volume**: this works from a bare host or the VS Code "Clone
  Repository in Container Volume" flow and is fast everywhere, but the code
  lives only in the volume, so pushing becomes the backup

Today's devcontainers bind-mount the workspace folder. Decided on 2026-10-19:
support both for flexibility, and document a recommended default per use case.
Both flows depend on `gh` and `glab`, which come from the Homebrew bundle, and
those two are the only forge tools in scope for now. Login should be browser
OAuth from inside the container. The `M5a` host browser bridge already opens
the login page in the host browser (through Windows interop on WSL2) for
`ft workspace`; the devcontainers do not have it yet. `gh auth login --web`
uses a device code, so it works through the bridge. `glab auth login --web`
redirects to a localhost callback that a plain Docker workspace cannot
receive, so containers should use `glab auth login --device` (GitLab 17.9 or
later) or publish the callback port.

Later, outside this milestone: a purpose-built Python CLI for managing many
GitLab and GitHub repos, and a `devops-sessions` tool for AWS SSO logins at
scale, GitLab tokens, SSH keys, and secrets retrieval.

### Terminal Mode

`ft workspace` already starts a long-lived container with bind mounts and
persisted state, and the devcontainer CLI can do the same from
`devcontainer.json`. Prefer one definition: either `ft workspace` drives the
devcontainer CLI, or the devcontainer files are generated from the workspace
profiles. Spike this before building more. Confirmed as in scope on
2026-10-19, after the Homebrew work.

## Issue Drafts

### M5c-1 Spike Homebrew in the container images

- [ ] Problem: the images and hosts use different userland toolchains
- [x] Scope: install Homebrew as the `vscode` user into a per-workspace volume for `ubuntu`, measure build time, first-start time, and size on amd64 and arm64, and try Alpine with glibc compatibility (arm64 covered by bottle coverage only; times pending a Graviton host)
- [x] Acceptance: a recorded go or no-go with numbers, plus the Alpine result

### M5c-2 Move container userland tools to Homebrew

- [ ] Problem: the `ft` tool-pool downloads duplicate what the host Brewfile already declares
- [ ] Scope: on Ubuntu and Arch, replace the tool pool with the shared Homebrew bundle and keep `uv` on Astral's installer; bake the floor into the image and mount the prefix as a per-workspace named volume (`ft workspace` and the devcontainers); run the floor check on start and add a clean-rebuild option; drop `uv` from the tool-pool Homebrew set, `host.yml`, and the Brewfiles; Alpine keeps its current installers; update the container standards and architecture docs
- [ ] Acceptance: `ft workspace validate` passes on the Homebrew-based images, an ad hoc `brew install` survives container replacement, and the clean rebuild restores the floor

### M5c-3 Offer Claude Code in every container target

- [ ] Problem: Claude Code is installed by hand today
- [x] Scope: honour the existing `M5b` `claude-code` option for workspaces, installing through the native installer, a persisted config mount, and a validation check when selected
- [ ] Acceptance: with the option selected, `claude --version` passes in every workspace and the CLI updates itself without a rebuild; without it, nothing is installed

### M5c-4 Choose how code gets into a devcontainer

- [ ] Problem: bind mounts need a host checkout and can be slow, while volume clones hide the code from the host
- [ ] Scope: support and document both, with a recommended default per use case; `gh` and `glab` come from the Homebrew bundle
- [ ] Acceptance: both flows work from VS Code and the devcontainer CLI

### M5c-5 Unify the workspace and devcontainer definitions

- [ ] Problem: `ft workspace` profiles and `.devcontainer/` describe overlapping container setups
- [ ] Scope: spike `ft workspace` driving the devcontainer CLI, compared with generating the devcontainer files from profiles
- [ ] Acceptance: one source of truth, or a documented reason for two

## Verification Notes

- [ ] VS Code devcontainer, bind-mount flow, on WSL2
- [ ] VS Code devcontainer, volume-clone flow
- [ ] Devcontainer CLI terminal mode, used for a real change and pushed
- [ ] A container replaced after `brew install` of an ad hoc tool behaves as documented
- [ ] amd64 and arm64 builds

## Branch and Merge Plan

- [ ] Start after `M5b`, or alongside it if the Homebrew spike is independent
- [x] Branch from `main` as `feat/m0005c-composable-container-workspaces`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Progress Notes

Drafted on 2026-10-18 when closing `M5a`, from the target use cases and the
Homebrew decision above.

Activated on 2026-10-19 with the scope decisions recorded under Design
Direction: `uv` stays on Astral's installer, Homebrew lives on a per-workspace
volume with a clean-rebuild option, Alpine tries glibc compatibility, the
containers share the host bundle, and both ways of getting code in are
supported. M5c-1 is the first slice.

M5c-3 built on 2026-10-19. Optional components install at container start, so
one published image serves every selection. Each image ships
`ft-ensure-claude-code`. `ft workspace up` and `enter` take `--options`, record
the selection in the container, mount `~/.claude` (with `CLAUDE_CONFIG_DIR`) and
`~/.local/share/claude` from per-profile state, and run the helper. The
devcontainers mount the same paths as volumes and run the helper with
`--if-selected` from `postStartCommand`, reading `DEV_CONTAINER_FORTRESS_OPTIONS`.
`ft workspace validate` checks `claude --version` when the option was selected.
Verified on `ubuntu-base`: the first start ran the native installer (2.1.303,
12 s), a replaced container relinked the persisted version in under a second
with no download, and `--options none` left Claude out. The Alpine image
installs the musl build through the same helper. Still to verify: Arch, a
devcontainer opened in VS Code, and a self-update that survives replacement.

M5c-1 done on 2026-10-19: go for Homebrew on the glibc targets, with the floor
baked into the image and seeding a per-workspace named volume (13.5 s first
start, 0.4 s floor check). No-go on Alpine, which keeps its current
installers. Numbers and reasoning are in the spike results above; arm64 times
are still to measure on a Graviton host.
