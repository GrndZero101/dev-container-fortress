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

- [x] The container images install their userland tools through Homebrew, with the same bundle model as the host targets, and the decision is recorded in `docs/architecture.md` and `docs/container-standards.md` (Ubuntu and Arch; Alpine keeps the downloader, recorded as a no-go)
- [x] Tools added inside a running container with `brew install` persist across container replacement where that is intended, or the docs state clearly that they do not
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

### M5c-5 Spike Results

Measured on 2026-10-19 on amd64 (WSL2) with the warm `ubuntu-base` image.
Two candidates for one definition:

- **A, `ft workspace` drives the devcontainer CLI:** `ft` writes an override
  `devcontainer.json` from the mount plan and runs `devcontainer up` and
  `exec`
- **B, generate the devcontainer files:** `ft` renders the `.devcontainer/`
  definitions and the volume definition from its own data, and `ft workspace`
  keeps its `docker run`

| Measure | A | Today, and B |
| --- | --- | --- |
| Replace a running workspace | 7.4 s | 1.0 s |
| Run one command | 0.85 s per `devcontainer exec` | 0.32 s per `ft workspace exec` (0.08 s raw `docker exec`) |
| Host dependency | Node plus `@devcontainers/cli` on every host; neither is in the Brewfile or tool pool | none new |
| Prototype | works: 11 bind mounts, `--name` through `runArgs`, `init`, `updateRemoteUserUID: false` | about 70 lines reproduce all four committed files byte for byte |

Decision: **B**. Generate the devcontainer files from the same data that
`ft workspace` uses, and keep two runtimes for documented reasons:

- `ft workspace` is several times faster to replace and exec, and needs no
  Node toolchain on hosts or the EC2 fleet
- it computes host integrations at start: the browser bridge broker, WSL
  interop mounts, the SSH agent socket, and option-dependent mounts. VS Code
  supplies its own browser, agent, and credential forwarding, and static JSON
  cannot branch on the host
- its state is host-owned bind mounts that `ft workspace auth` and `doctor`
  inspect, while devcontainer state is named volumes keyed per definition

What B shares: the persisted-mount table (names and container paths), which
mounts apply to glibc targets only, the start steps (`ft-brew-floor`,
`ft-ensure-claude-code`), the option and Claude Code environment, and the
build-arg names. M5c-4 had to add the same `gh`, `glab`, and brew mounts in
four JSON files plus `cli.py`; under B that is one edit.

Found along the way:

- **The image cache busts on every commit.** There is no `.dockerignore`, and
  two `RUN --mount=type=bind,source=.` steps (the corporate CA and
  `shell-config` installers) see the whole context, `.git` included. After
  only doc edits and a commit, `ft workspace build ubuntu-base` re-ran
  everything from layer 11, the Homebrew floor included: 215 s
- **The devcontainer build args blank the Dockerfile defaults.** An unset
  `${localEnv:...}` passes an empty string, so the devcontainer image has
  `SHELL_CONFIG_PROFILE=""` where the `ft` image has
  `zsh-tll-citadel-dev-fortress`. The active-profile file still resolves,
  because the installer falls back. It also gives the two builds different
  cache keys, so each keeps its own 3.2 GB image
- **`${localEnv:VAR:default}` cannot hold a `:`.** The default is cut at the
  first colon, so a URL default arrives as `https`. The renderer must leave
  such arguments to the Dockerfile default
- the devcontainer CLI does not expand `${devcontainerId}` in
  `workspaceMount` (already worked around in M5c-4)

## Issue Drafts

### M5c-1 Spike Homebrew in the container images

- [ ] Problem: the images and hosts use different userland toolchains
- [x] Scope: install Homebrew as the `vscode` user into a per-workspace volume for `ubuntu`, measure build time, first-start time, and size on amd64 and arm64, and try Alpine with glibc compatibility (arm64 covered by bottle coverage only; times pending a Graviton host)
- [x] Acceptance: a recorded go or no-go with numbers, plus the Alpine result

### M5c-2 Move container userland tools to Homebrew

- [ ] Problem: the `ft` tool-pool downloads duplicate what the host Brewfile already declares
- [x] Scope: on Ubuntu and Arch, replace the tool pool with the shared Homebrew bundle and keep `uv` on Astral's installer; bake the floor into the image and mount the prefix as a per-workspace named volume (`ft workspace` and the devcontainers); run the floor check on start and add a clean-rebuild option; drop `uv` from the tool-pool Homebrew set, `host.yml`, and the Brewfiles; Alpine keeps its current installers; update the container standards and architecture docs
- [x] Acceptance: `ft workspace validate` passes on the Homebrew-based images, an ad hoc `brew install` survives container replacement, and the clean rebuild restores the floor

### M5c-3 Offer Claude Code in every container target

- [ ] Problem: Claude Code is installed by hand today
- [x] Scope: honour the existing `M5b` `claude-code` option for workspaces, installing through the native installer, a persisted config mount, and a validation check when selected
- [ ] Acceptance: with the option selected, `claude --version` passes in every workspace and the CLI updates itself without a rebuild; without it, nothing is installed

### M5c-4 Choose how code gets into a devcontainer

- [ ] Problem: bind mounts need a host checkout and can be slow, while volume clones hide the code from the host
- [x] Scope: support and document both, with a recommended default per use case; `gh` and `glab` come from the Homebrew bundle
- [ ] Acceptance: both flows work from VS Code and the devcontainer CLI (CLI verified; VS Code pending)

### M5c-5 Unify the workspace and devcontainer definitions

- [ ] Problem: `ft workspace` profiles and `.devcontainer/` describe overlapping container setups
- [x] Scope: spike `ft workspace` driving the devcontainer CLI, compared with generating the devcontainer files from profiles (decision: generate; see the spike results)
- [ ] Scope: add `ft devcontainer render`, which writes the four definitions from the shared mount table and target data, plus `--check` in pre-commit and CI; render build-arg defaults where they hold no `:`
- [ ] Acceptance: one source of truth for mounts, start steps, and environment, with the reasons for two runtimes recorded in `docs/architecture.md`

### M5c-6 Keep the image cache across commits

- [ ] Problem: every commit or doc edit rebuilds the Homebrew floor, about 3.5 minutes, and the `ft` and devcontainer builds never share layers
- [ ] Scope: add a `.dockerignore`, narrow the bind-mounted build steps to the paths they read, and order the layers so that changes under `ft/` do not invalidate the floor where practical
- [ ] Acceptance: a rebuild after a doc-only commit reuses the floor layer, and a devcontainer build after `ft workspace build` with default settings reuses it too

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

M5c-2 built on 2026-10-19. The Ubuntu and Arch images write the tool-pool
Linux set to `brew-floor.txt` with the new `ft tool formulae`, and
`ft-brew-floor` installs Homebrew and any missing formulae. The
`HOMEBREW_FLOOR` build arg picks `warm` (the default) or `cold`, and CI
publishes cold images and smoke-tests their first start. `ft workspace up`
mounts the per-profile `dev-fortress-brew-<profile>` named volume and runs the
floor before the Claude Code check; `ft workspace reset --brew` removes it.
The Ubuntu and Arch devcontainers mount `dev-fortress-brew-<id>` and run the
floor from `postStartCommand`. Several custom installers went with it: the
`ft install` step in both images, the apt and pacman `gh`/`glab` installs
(both now in the floor), and `install-aws-cli.sh` and pacman's `aws-cli-v2`
(the `aws` layer now appends `awscli` to the floor). `uv` left the tool-pool
Homebrew set, `host.yml`, and the Brewfile; hosts that already have the
Homebrew `uv` keep it, behind the Astral one on `PATH`. A new `bash-syntax`
pre-commit hook covers the two bash container helpers.

Verified on amd64:

| Check | Result |
| --- | --- |
| Warm Ubuntu build, `ubuntu-base` | 254 s, 3.2 GB |
| Cold Ubuntu build, with the `aws` layer | 1.1 GB |
| `ft workspace up` on a fresh volume, warm image | 11 s, all 44 formulae present, `validate` all OK |
| Replace the container after `brew install hello` | 0.9 s, `hello` still runs |
| `ft workspace reset --brew` | removes the volume; the next start re-seeds |
| Cold image first start | 169 s for Homebrew 7.0.9 and 45 formulae, including `awscli` |
| Warm Arch test target, `ft container validate arch` | 27 of 27 checks OK, every tool from Homebrew |
| `nvim`, `rg`, `gh` on `PATH` | from the Homebrew prefix; `uv` and `ft` from `~/.local/bin` |

Still to verify: arm64 on a Graviton host, a devcontainer opened in VS Code,
and the first CI run with cold images.

Decided on 2026-10-19: Alpine stays a supported container target, on the
`ft install` downloader with its pinned, checksummed tools. The downloader
stays for Alpine alone; Alpine's own repositories lack `tenv`, `glow`, and
`oh-my-posh`, so `apk` alone could not replace it.

M5c-4 built on 2026-10-19. The recommended default is a bind mount for VS Code
on an existing checkout, and a volume for VS Code without one (or on a slow
host filesystem) and for devcontainer CLI terminal mode. VS Code's volume flow
is its own "Clone Repository in Container Volume"; the CLI one is the new
`devcontainer/volume/devcontainer.json`, which runs the published image with
`dev-fortress-src-<folder>` at `/workspaces`. It is keyed on the host folder's
name because the CLI does not expand `${devcontainerId}` in `workspaceMount`.
It lives outside `.devcontainer/` so VS Code does not offer it on reopen.

Forge login and push:

- the Ubuntu and Arch devcontainers gained `gh` and `glab` config volumes,
  and the images pre-create those paths and `/workspaces` with `vscode`
  ownership
- the `glab` mount moved to `~/.config/glab-cli`, the directory `glab`
  actually uses; the old `~/.config/glab` target never held the login
- `ft identity --login gitlab` now runs `glab auth login --device` against
  `gitlab.com`, so both forges log in with a device code; older self-managed
  GitLab still runs `glab auth login` directly
- `/etc/gitconfig` routes HTTPS credentials for `github.com` and `gitlab.com`
  through `gh` and `glab`, because `~/.gitconfig` does not persist.
  `GIT_CONFIG_SYSTEM` points at it, since the floor's Homebrew `git` reads its
  system config from the prefix on the brew volume

Verified on amd64 with a warm `ubuntu-base` image:

| Check | Result |
| --- | --- |
| CLI volume flow, first `up` | 24 s; `/workspaces` and the forge dirs owned by `vscode`; HTTPS clone works |
| `up --remove-existing-container` after an unpushed change, a commit, and `brew install hello` | 8 s; all three still there |
| `gh auth login --web`, no browser | prints the code and URL, says to open it by hand, keeps polling |
| `glab auth login --device` | prints the code and URL after a skippable registry prompt; writes to `~/.config/glab-cli` |
| Credential helpers with no login | Homebrew and distro `git` both run `gh auth git-credential`, which stays silent, and Git falls back |
| CLI bind flow, `.devcontainer/ubuntu` | 231 s build; the live checkout at `/workspaces/dev-container-fortress` |
| `ft workspace validate ubuntu-base` | all OK; `glab-cli` mounted from `config-glab` |

Still to verify: both flows opened in VS Code, a real login and push from
terminal mode, and Arch. The CLI volume flow needs the published image to
carry `ft-brew-floor`, so it works from GHCR only after this branch merges;
use `DEV_FORTRESS_IMAGE` with a local build until then.

M5c-5 spike done on 2026-10-19: generate the devcontainer files from `ft`'s
data (B) rather than have `ft workspace` drive the devcontainer CLI (A).
A was 7x slower to replace a workspace, 2.6x slower per exec, and needs Node on
every host; B's prototype reproduced all four committed definitions byte for
byte. The spike also found that the image cache busts on every commit and that
the devcontainer build args blank the Dockerfile defaults, now M5c-6.
