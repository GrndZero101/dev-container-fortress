# M5c Composable Container Workspaces

## Status

- [x] Milestone complete
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

Added on 2026-11-20: this milestone also folds the separate `tboss-workspace`
repo into Dev Fortress as a generic **workbench**, a multi-repo devcontainer
that anyone can set up, not tied to one operator's repos or paths. A
workbench is a DevOps workbench that feels close to local workstation
development, with the operator's credentials available. Its container limits
the **filesystem blast radius**, so coding agents such as Claude Code can run
with permission prompts bypassed without being able to damage the host.

Rescoped on 2026-11-20 so the workbench could merge before the first
bare-metal developer run: the agent guardrails (`M5c-8`, `M5c-9`) moved to
[`M5f`](M5f-agent-workbench-guardrails.md), and the cold run of the docs moved
to [`M5e`](M5e-developer-workstation.md)'s verification. The agent design
below stays here as the record that `M5f` builds on.

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

Workbenches serve both container use cases at the `full` trust level
described under [Agents in a Full Workbench](#agents-in-a-full-workbench). A
locked-down `sealed` level, for agents working on untrusted input, is planned
separately in [`M5d`](M5d-sealed-agent-workbench.md).

## Exit Criteria

- [x] The container images install their userland tools through Homebrew, with the same bundle model as the host targets, and the decision is recorded in `docs/design/architecture.md` and `docs/design/container-standards.md` (Ubuntu and Arch; Alpine keeps the downloader, recorded as a no-go)
- [x] Tools added inside a running container with `brew install` persist across container replacement where that is intended, or the docs state clearly that they do not
- [x] Claude Code can be selected for every container target through the `M5b` option model, installs through its native installer, and updates itself in place
- [x] The devcontainer documents and supports one recommended way to get code in, either a bind mount of the host checkout or a clone into a volume, and the other way works as a documented variant
- [x] A devcontainer CLI terminal mode works end to end: `up`, enter a shell, develop, commit, push, and come back later to the same state
- [x] `ft workspace` and the devcontainer CLI either share one definition or have a documented reason to differ, so there are no two overlapping container paths
- [x] A generic workbench ships in Dev Fortress, rendered from the same data as the other devcontainer definitions, with no `tboss` names, repos, or absolute paths (verified in terminal mode; the cold run from the docs is `M5e` verification; `tboss-workspace` was deleted after the merge)
- Moved to [`M5f`](M5f-agent-workbench-guardrails.md): what a `full` workbench protects, the filesystem guardrails and `--check`, SSH through forwarded agents, and Claude Code bypass mode with a deny-list hook

## Non-Goals

- [ ] Byte-for-byte reproducible image builds
- [ ] Dropping the distro package manager for low-level system prerequisites
- [ ] New container distros
- [ ] Protecting the accounts that a workbench's credentials can reach; that is the `sealed` level in [`M5d`](M5d-sealed-agent-workbench.md)
- [ ] Defending against a container or kernel escape exploit; the boundary is standard Docker isolation
- [ ] Workbenches on native Windows without WSL2

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
- **Clone into a volume**: this works from a bare host and is fast
  everywhere, but the code lives only in the volume, so pushing becomes the
  backup. The devcontainer CLI starts the container, and VS Code attaches to
  it (decided on 2026-11-20, below)

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

Decided on 2026-11-20, from the `M5c-4` VS Code run: VS Code's own "Clone
Repository in Container Volume" is not a supported flow. It only reads
`.devcontainer/devcontainer.json` or `.devcontainer.json` at the repository
root, so it never sees the `.devcontainer/<distro>/` definitions and falls back
to stock templates. The volume flow is one path instead: `devcontainer up` on
`devcontainer/volume/devcontainer.json`, then VS Code's "Attach to Running
Container" from as many windows as needed. That is also the long-lived,
many-window container the workbench needs, so it is not a second path to
maintain.

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

### Workbench

Drafted on 2026-11-20. `GrndZero101/tboss-workspace` is a thin VS Code
devcontainer around the published `ubuntu-full` image. It has a `repos/`
folder of ignored child clones, a `.code-workspace` listing them, persisted
state bind-mounted from host state directories, and a `local-build` variant
for changing the image itself. It works, but everything in it is specific to
one operator:

- the name, the state directory (`tboss-vscode`), and the hard-coded repo list
  (`dev-container-fortress`, `shell-config`, `minecraft-docker`)
- the absolute `/home/timl/...` paths in `README.md` and `TESTING.md`
- a mount set that predates this branch: no `state`, `zoxide`, `atuin`, brew
  volume, or Claude Code mounts, and `glab` at the old `~/.config/glab` target
- a `TODO.md` that a parked item in the root `TODO.md` pointed at, which the
  repo no longer has

Fold it into Dev Fortress as a generic **workbench**, built on the `M5c-5`
renderer rather than beside it:

- A workbench is one directory, usually the user's own small Git repo. It
  holds a `workbench.toml` with a name, a workspace profile or image, a trust
  level (`full` for now; `sealed` is reserved for `M5d`), the options and
  credential mounts to enable, and a list of repo URLs.
- `ft devcontainer render` gains a workbench target that writes the
  workbench's `.devcontainer/devcontainer.json`, its `<name>.code-workspace`,
  and a `.gitignore` for `repos/`, from `workbench.toml` plus the shared mount
  table. Mounts, start steps (`ft-brew-floor`, `ft-ensure-claude-code`), and
  environment then come from one source, as decision B intends, and the repo
  list and `.code-workspace` folders cannot drift apart. `--check` covers
  workbenches too.
- A small `ft workbench clone` clones any repos in `workbench.toml` that are
  missing from `repos/`.
- Dev Fortress checks in a rendered reference workbench under
  `examples/workbench/`, kept current by `--check`, so people who do not run
  `ft` on the host can copy it.
- Persisted state follows the devcontainer side of the persisted state
  contract: named volumes for `state`, `zoxide`, `atuin`, the brew prefix,
  `gh`, `glab-cli`, and the Claude Code paths, plus whichever credential mounts
  the workbench enables.
- Code comes in by the `M5c-4` defaults: `repos/` is a bind mount in VS Code,
  which keeps the feel of local workstation development, and the volume flow
  serves CLI terminal mode or hosts without a checkout.
- A workbench can be one always-on container: started once with the
  devcontainer CLI, entered from terminals, and attached from several VS Code
  windows, one per repo, that come and go without stopping it. Attached
  windows skip `devcontainer.json`'s `customizations`, and their extensions
  live in `~/.vscode-server`, which does not survive container replacement.
  Decide how a workbench restores its extensions and settings (a volume for
  `~/.vscode-server`, VS Code's attached-container configuration, or both),
  and whether rendered definitions set `"shutdownAction": "none"` so a
  container VS Code started also outlives its windows.
- Terminal mode is the devcontainer CLI run against the rendered definition,
  the same as the existing volume flow. There is no `ft workbench up`:
  decision B keeps `ft workspace` as the faster runtime for Dev Fortress
  self-hosting, and adding a third runtime would undo it.
- The `local-build` variant becomes a `workbench.toml` setting that points at
  a Dev Fortress checkout, rather than a second hand-written file.

> [!NOTE]
> "Workbench" is the multi-repo devcontainer users create; "workspace" stays
> the `ft workspace` profile and runtime vocabulary.

### Agents in a Full Workbench

Drafted on 2026-11-20. Most agentic development runs inside a workbench. The
workbench is a DevOps environment, so it carries the operator's credentials:
SSH through a forwarded agent, 1Password, forge logins, and cloud CLIs. Its
container gives two things: **filesystem blast radius protection** and a
development environment that can be composed quickly. Inside it, Claude Code
runs with permission prompts bypassed.

The trade is deliberate. An agent that has no access to anything is far less
useful. A locked-down level for untrusted input is planned in
[`M5d`](M5d-sealed-agent-workbench.md) and gets built when there is a
concrete job for it.

#### What a `full` Workbench Protects

| Protected by the container | Not protected |
| --- | --- |
| The host OS, packages, and services | Anything the mounted or forwarded credentials reach: forges, cloud accounts, SSH hosts including the `M7b` fleet, and the 1Password items in scope |
| The host home directory, dotfiles, and host-side tools | The bind-mounted `repos/`: the agent can delete uncommitted work, and hooks it plants in `repos/*/.git` run on the host the next time host-side Git touches that repo |
| Other host checkouts outside `repos/` | The network: the LAN, host services, and cloud metadata are reachable like they are from the host |
| The Windows side of a WSL2 host | Prompt injection: content the agent reads (issues, web pages, dependency docs) can steer it toward anything in the right-hand column |

The container protects the disk. It does not protect the accounts: running
Claude Code in bypass mode in a `full` workbench has the same account
exposure as running it on the host. The guardrails below protect the
filesystem, and add cheap friction in front of the worst account-level
mistakes.

#### Filesystem Guardrails

These are required, because without them the container does not limit the
filesystem blast radius at all. The renderer enforces them, and `--check`
fails on a definition that breaks one:

- **No host container-runtime socket** (Docker or Podman). A runtime socket
  gives root on the host, and with it the whole host filesystem. If a
  workbench needs Docker, spike the options: Docker-in-Docker, a rootless
  daemon inside the container, or Sysbox. Docker-in-Docker normally needs
  `--privileged`, which also weakens the disk boundary, so it is not a free
  answer.
- **Mount only `repos/` and the persisted state paths.** Never mount the host
  home directory, `/`, `/mnt/c`, or other Windows drives.
- **No `--privileged`, no added capabilities, and no host network.** Host
  networking exposes host-only `localhost` services to the container.
- **Validate the browser bridge.** `ft.browser_bridge` passes any payload to
  the host opener (`xdg-open`, `wslview`, or the WSL `explorer.exe` interop).
  Accept only `http` and `https` URLs before the devcontainers gain the
  bridge.
- **Give the devcontainers the browser bridge.** VS Code opens host browser
  links only while a window is attached, so CLI terminal mode needs the `M5a`
  bridge: the renderer adds the socket mount and the `BROWSER`, `GH_BROWSER`,
  and `DEV_FORTRESS_HOST_BROWSER_SOCKET` environment, and `initializeCommand`
  starts the broker on the host. The images already ship
  `ft-host-browser-open`. Device-code logins (`gh`, `glab --device`,
  `aws sso login --use-device-code`) work through it; logins that redirect to
  a `localhost` callback reach the host, not the container, so they need the
  device-code option or a published port.

Passwordless `sudo` stays in a `full` workbench. Without `--privileged`, a
runtime socket, or host mounts, root inside the container does not reach the
host.

#### Credential Model

Credentials are present but come in through the narrowest channel that keeps
workstation behavior. Most of it already exists on this branch:

- **Forge HTTPS** goes through `gh` and `glab` (`/etc/gitconfig`, `M5c-4`),
  with device-code logins persisted in their config volumes.
- **SSH** works through a forwarded agent. Private key files are never
  mounted. VS Code forwards the host agent itself. The devcontainer CLI does
  not, and static JSON cannot branch on whether `SSH_AUTH_SOCK` is set, so CLI
  terminal mode needs a stable socket path to mount (for example the
  1Password agent socket, or a WSL2 bridge to the Windows agent). With the
  1Password SSH agent, key use can require approval on the host, which is a
  cheap human check on pushes and SSH sessions. Confirm how that approval
  behaves through forwarding.
- **Commit signing** uses SSH signing through the same forwarded agent, so
  signing keys stay in 1Password.
- **The `op` CLI** most likely needs a 1Password service-account token scoped
  to a vault, because the desktop-app integration is not expected to cross a
  container boundary. Confirm this before documenting it.
- **Cloud CLIs** keep today's mounts. Note that `ft workspace` mounts the
  host's real `~/.aws` (`_workspace_persisted_host_path`), not per-profile
  state. A workbench sets a non-production default profile (`AWS_PROFILE`
  from `workbench.toml`), so reaching production takes a deliberate switch.
- **GPG and `pass`** stay optional mounts. The `pass` store holds every
  secret, so a workbench enables it only when it needs it.
- The later `devops-sessions` tool (see Getting Code Into a Devcontainer)
  is where AWS SSO at scale, GitLab tokens, and SSH key handling grow; this
  milestone only wires what exists.

#### Claude Code Policy

`M5c-3` already installs Claude Code in containers and persists its login
through `CLAUDE_CONFIG_DIR`. What a workbench adds:

- Claude Code defaults to bypassing permission prompts inside a workbench
  where it is selected. The policy ships in the image as managed settings, so
  project settings in a cloned repo cannot quietly change it, and it does not
  apply to `ft workspace` unless that profile asks for it.
- A deny-list hook (a small repo-owned script, `PreToolUse`) blocks a short,
  data-driven list of catastrophic commands. Examples: force-pushing to a
  default branch, deleting remote branches or tags, `terraform destroy`
  outside the `M7b` fleet directories, and bulk cloud deletes or terminations.
  It is a speed bump against mistakes and injected instructions, not a
  security boundary.
- Confirm in `M5c-9` the managed settings path and keys, and that hooks and
  `deny` rules still apply in bypass mode. Do not rely on either until
  confirmed.

#### Residual Risks

These are accepted risks, documented rather than solved:

- account-level damage through the credentials in the workbench, reduced by
  host-side 1Password approval, non-production defaults, the deny list, and
  branch protection on the forges
- hooks planted in bind-mounted repos that run on the host; the docs say so,
  and the volume flow avoids it for anyone who prefers that
- loss of uncommitted work in `repos/`; commit and push often
- container and kernel escapes (see Non-Goals)

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

- [x] Problem: Claude Code is installed by hand today
- [x] Scope: honour the existing `M5b` `claude-code` option for workspaces, installing through the native installer, a persisted config mount, and a validation check when selected
- [x] Acceptance: with the option selected, `claude --version` passes in every workspace and the CLI updates itself without a rebuild; without it, nothing is installed

### M5c-4 Choose how code gets into a devcontainer

- [x] Problem: bind mounts need a host checkout and can be slow, while volume clones hide the code from the host
- [x] Scope: support and document both, with a recommended default per use case; `gh` and `glab` come from the Homebrew bundle
- [x] Acceptance: both flows work from VS Code and the devcontainer CLI (VS Code reaches the volume flow by attaching to the CLI container)

### M5c-5 Unify the workspace and devcontainer definitions

- [x] Problem: `ft workspace` profiles and `.devcontainer/` describe overlapping container setups
- [x] Scope: spike `ft workspace` driving the devcontainer CLI, compared with generating the devcontainer files from profiles (decision: generate; see the spike results)
- [x] Scope: add `ft devcontainer render`, which writes the four definitions from the shared mount table and target data, plus `--check` in pre-commit and CI; render build-arg defaults where they hold no `:`
- [x] Acceptance: one source of truth for mounts, start steps, and environment, with the reasons for two runtimes recorded in `docs/design/architecture.md`

### M5c-6 Keep the image cache across commits

- [x] Problem: every commit or doc edit rebuilds the Homebrew floor, about 3.5 minutes, and the `ft` and devcontainer builds never share layers
- [x] Scope: add a `.dockerignore`, narrow the bind-mounted build steps to the paths they read, and order the layers so that changes under `ft/` do not invalidate the floor where practical
- [x] Acceptance: a rebuild after a doc-only commit reuses the floor layer, and a devcontainer build after `ft workspace build` with default settings reuses it too

### M5c-7 Fold `tboss-workspace` into a generic workbench

- [x] Problem: the multi-repo devcontainer lives in a separate repo, tied to one operator's repos, paths, and state names, and its mounts predate this branch
- [x] Scope: a user-owned workbench TOML file under `${XDG_CONFIG_HOME}/dev-container-fortress/workbenches/`; `ft workbench init`, `render` (with `--check`), `clone`, and `list`, which write `devcontainer.json` and the `.code-workspace` into the workbench folder; `examples/workbench/` kept current by pre-commit; the `local_build` setting; and `docs/guides/workbench-usage.md` replacing `tboss-workspace`'s `README.md` and `TESTING.md` (no `repos/` `.gitignore`: the folder is generated output, not a repo)
- [ ] Acceptance: a fresh user builds a workbench for two of their own repos from the docs alone, opens it in VS Code and in CLI terminal mode, and logs in and pushes; `tboss-workspace` is archived with a pointer; the `M5a` open note about its persisted state is closed
- [x] Depends on: `M5c-5` (the renderer)

### M5c-8 and M5c-9

Moved to [`M5f`](M5f-agent-workbench-guardrails.md) as `M5f-1` (filesystem
guardrails and credential model) and `M5f-2` (Claude Code bypass mode and
deny list).

## Verification Notes

- [x] VS Code devcontainer, bind-mount flow, on WSL2
- [x] VS Code devcontainer, volume flow: CLI `up`, then two windows attached to different repos
- [ ] Devcontainer CLI terminal mode, used for a real change and pushed
- [ ] A container replaced after `brew install` of an ad hoc tool behaves as documented
- [ ] amd64 and arm64 builds
- [ ] A generic workbench created from the docs by someone following them cold (moved to `M5e`)
- The agent checks moved to [`M5f`](M5f-agent-workbench-guardrails.md)

## Open Questions

- [x] Where does each user's own workbench live: a small private repo, or only a local `workbench.toml`? A local file under `${XDG_CONFIG_HOME}/dev-container-fortress/workbenches/<name>.toml`, which dotfiles can carry; the rendered folder is regenerable
- The questions about Docker inside a workbench and the SSH agent socket path moved to `M5f`

## Branch and Merge Plan

- [ ] Start after `M5b`, or alongside it if the Homebrew spike is independent
- [x] Branch from `main` as `feat/m0005c-composable-container-workspaces`
- [x] Remaining order: `M5c-7` (workbench); `M5c-8` and `M5c-9` moved to `M5f`
- [ ] Commit freely at verified checkpoints
- [x] Squash merge into `main` (#7, `77d964d`, 2026-11-20)

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

M5c-6 done on 2026-10-19. `.dockerignore` is now an allowlist:
`.python-version`, `containers/`, `ft/` (without tests, caches, and
Markdown), and `.local/` for operator inputs, so `ft` rejects a local
`shell-config` staging path outside `.local/`. The context fell from 8.1 MB to
330 kB, and local Terraform state and `.claude/` no longer reach the builder.
On Ubuntu and Arch, two new stages feed the runtime through `COPY --from`,
which BuildKit keys on content: `corporate-ca-source` copies only the requested
CA directory, and `brew-floor-list` writes the floor list with
`uv tool run --from ./ft`. The CA install moved into a shared `<distro>-trusted`
stage that both use. The floor now comes before the `shell-config` build args
and `COPY ft`. `SHELL_CONFIG_PROFILE` falls back to the default when a
devcontainer passes an empty build arg. Alpine keeps its layout; it has no
floor, and it builds unchanged under the new `.dockerignore`.

Verified on amd64:

| Change before rebuilding | Before | After |
| --- | --- | --- |
| Commit plus doc edits, Ubuntu | 215 s, floor rebuilt | 12 s, floor cached |
| Doc edit inside the context (`containers/README.md`), Ubuntu | floor rebuilt | 1 s, every step cached |
| Same doc edit, Arch | floor rebuilt | 1 s, every step cached |
| Source change under `ft/`, Ubuntu | 215 s, floor rebuilt | 26 s, floor cached |
| `.devcontainer/ubuntu` build right after `ft workspace build` | 231 s, its own floor | 12 s, floor shared |
| Staged local `shell-config` | floor rebuilt | 12 s, floor cached, copied from `.local/sources` |

Also checked: a probe CA under `.local/certs` installs into the trust store,
and a missing directory still fails with `requested certificate directory not
found`; the devcontainer image now has
`SHELL_CONFIG_PROFILE=zsh-tll-citadel-dev-fortress`; `ft container validate`
passes 27 of 27 checks on Arch and on Alpine; `ft workspace validate
ubuntu-base` passes.

Extended on 2026-11-20 with the generic workbench, folding in
`GrndZero101/tboss-workspace`, and agents in a `full` workbench: `M5c-7` to
`M5c-9`. The workbench builds on the `M5c-5` renderer and the `M5c-4` code-in
defaults rather than adding a runtime. A first draft made the container a
credential boundary with an egress allowlist. The operator chose a credentialed
DevOps workbench that protects the filesystem instead, and that draft moved to
[`M5d`](M5d-sealed-agent-workbench.md). These are planning changes only.

M5c-4 verified on 2026-11-20 on amd64 WSL2 with Docker CE, closing the code-in
and terminal-mode exit criteria:

| Check | Result |
| --- | --- |
| VS Code bind mount, `.devcontainer/ubuntu` | live checkout at `/workspaces/dev-container-fortress`; 44 of 44 floor formulae; all 8 state volumes owned by `vscode` |
| Login and push from VS Code | `ft identity --login github` opened the host browser; a scratch branch pushed through `gh auth git-credential` alone, under the noreply identity |
| VS Code "Rebuild Without Cache" | `gh` login, `atuin` history, a state-volume marker, and the floor all kept |
| `ft workspace build ubuntu-base` right after that devcontainer build | 12 s, floor shared, so `M5c-6`'s cache sharing works both ways |
| CLI volume flow, `up` on the local image | 27 s; floor present; HTTPS clone into `dev-fortress-src-m5c4` |
| Terminal-mode login and push | device code opened by hand on the host; push through `gh` alone, no VS Code involved |
| Host restart, then the same `devcontainer up` | 3 s; the stopped container restarted with the checkout, identity, and floor intact |
| `up --remove-existing-container` with an unpushed branch | 8 s; branch, commit, untracked file, `gh` login, and `atuin` history kept |
| Two VS Code windows attached to the CLI container | one per repo (`dev-container-fortress`, `shell-config`); after both closed, the container kept running and `devcontainer exec` re-entered it |

Found on the way:

- VS Code's own "Clone Repository in Container Volume" only reads definitions
  at the repository root, so it offered stock templates. The volume flow from
  VS Code is now the CLI container plus "Attach to Running Container"; see the
  decision under Getting Code Into a Devcontainer.
- A `.code-workspace` file in a parent folder makes VS Code look for
  `.devcontainer/` beside it, so it offered stock templates too. The
  workbench's rendered `.code-workspace` must sit beside its `.devcontainer/`.
- On WSL2 with Docker CE, a VS Code window not connected to WSL runs the
  Windows `docker` CLI and starts Docker Desktop. `dev.containers.executeInWSL`
  and `dev.containers.executeInWSLDistro` fixed it.
- The host `~/.gitconfig` that VS Code copies in clears VS Code's forwarded
  credential helper for `github.com` (an empty per-host `credential.helper`
  from `gh auth setup-git`), so pushes from VS Code use the container's `gh`
  login. The usage doc's earlier tip said otherwise.
- Attached windows skip `devcontainer.json`'s extensions and settings; recorded
  as a workbench decision.
- `gh repo clone` needs a login even for a public repo; `gh` cannot copy the
  device code to a clipboard in the container, which is cosmetic.

Still open: Arch, arm64, and the CLI volume flow from the published GHCR image,
which needs this branch merged first.

M5c-5 done on 2026-11-20. `ft devcontainer render` writes all four
definitions from `ft/src/ft/container_runtime.py`, which `ft workspace` now
reads too: the persisted-mount paths, the Homebrew-only mounts, each option's
mounts and environment, and the start steps, which `ft workspace up` now runs
from the same list. Build-arg defaults come from the target Dockerfiles. A
`devcontainer-render` pre-commit hook runs `--check`, so CI enforces it too.
The reasons for keeping two runtimes are in `docs/design/architecture.md`.

Found on the way: the volume flow's image,
`${localEnv:DEV_FORTRESS_IMAGE:ghcr.io/...:ubuntu}`, resolved to the
unpublished `:latest` when the variable was unset, because the CLI cut the
default at its first colon. The renderer now refuses a colon in any default,
and the override is split into `DEV_FORTRESS_IMAGE_REPO` and
`DEV_FORTRESS_IMAGE_TAG`.

| Check | Result |
| --- | --- |
| Fresh render against the committed files | only the intended changes: four build-arg defaults per build definition, and the split image reference |
| `devcontainer read-configuration`, volume flow, no variables set | `ghcr.io/grndzero101/dev-container-fortress:ubuntu` |
| Same, with the two variables set | `dev-container-fortress:workspace-ubuntu-base` |
| `.devcontainer/ubuntu` build with the rendered args | 22 s, floor cached; `SHELL_CONFIG_PROFILE=zsh-tll-citadel-dev-fortress` |
| `ft` tests and pre-commit | 260 passed; all hooks pass |

M5c-3 verified on 2026-11-20 on amd64 WSL2. Ubuntu was checked through
`ft workspace`, and Arch and Alpine through their devcontainers with
`DEV_CONTAINER_FORTRESS_OPTIONS=claude-code`:

| Check | Ubuntu (`ubuntu-base`) | Arch | Alpine (musl) |
| --- | --- | --- | --- |
| `claude --version` after start | 2.1.303, relinked from October's state | 2.1.329, fresh install | 2.1.329, fresh install |
| `claude update` in place, no rebuild | 2.1.303 to 2.1.329 in 4 s | 2.1.303 to 2.1.329 | 2.1.303 to 2.1.329 |
| Replace the container | 1 s, relinked 2.1.329; `validate` OK | 15 s, relinked 2.1.329 | relinked 2.1.329 after the fix below |
| `--options none` | `claude` not on `PATH`, options empty | | |

Found on the way:

- **The relink chose by modification time and could pick an older version.**
  `claude update` to a version that is already on disk relinks without
  rewriting it, so after reinstalling 2.1.303 and updating back to 2.1.329, a
  replaced Alpine container came back on 2.1.303. `ft-ensure-claude-code` now
  takes the highest plain version name with `sort -V` (BusyBox supports it),
  which also skips partial downloads. A new test runs the helper against a
  fake versions directory, and fails on the old ordering.
- **All definitions in one checkout share one devcontainer image tag.** The
  devcontainer CLI names the image after the workspace folder,
  `vsc-<folder>-<hash>`, not after the definition. Building Arch and Alpine
  from the same checkout at once overwrote each other's tag, which most likely
  only bites when builds run in parallel. Building any definition also retags
  the image that another definition's existing container was built from;
  containers keep their own image, and the CLI rebuilds from cache when it
  creates a container. Correction, made during `M5c-7`: the 174 s Arch
  replace seen here was not this race. The helper fix above landed mid-run,
  and every `containers/common/` helper was copied in before the Homebrew
  floor, so the edit rebuilt the floor. `M5c-7` moved the helpers after it.

M5c-7 built on 2026-11-20. The operator chose a local workbench file over a
private repo per workbench, with `ft` writing it, so dotfiles can carry it
later. A workbench is
`${XDG_CONFIG_HOME}/dev-container-fortress/workbenches/<name>.toml` (name,
directory, `ft workspace` profile, optional `local_build`, trust, options,
extra mounts, extensions, repos). `ft workbench init` writes it and renders
`~/workbenches/<name>/` (`.devcontainer/devcontainer.json` and
`<name>.code-workspace`); `render`, `clone`, and `list` complete the set. The
profile supplies the published image, or for a local build the tool-layer
and release build args, plus its persisted mounts. Volumes are named
`dev-fortress-wb-<name>-<mount>` rather than keyed by `${devcontainerId}`, so
they survive moving or re-rendering the folder. Because the selection is in
the file, the definition mounts only the selected options' volumes, sets
`DEV_CONTAINER_FORTRESS_OPTIONS` literally, and runs `ft-ensure-claude-code`
without `--if-selected`. A relative `local_build` resolves against the
workbench folder, so `repos/dev-container-fortress` builds from a clone; build
paths inside the folder stay relative, others are absolute.
`examples/workbench/` is the rendered reference, checked by a pre-commit hook.

Verified on amd64 WSL2 in terminal mode, with a sandbox
`XDG_CONFIG_HOME` and a `local_build` of this branch:

| Check | Result |
| --- | --- |
| `ft workbench init` with two repos, `claude-code`, `--profile ubuntu-base` | TOML written; folder rendered; `render --check` clean |
| `ft workbench clone` | both repos cloned on the host into `repos/` |
| `devcontainer up --workspace-folder <folder>` | 192 s including a floor rebuild; floor present, Claude Code 2.1.329 installed |
| Inside | `/workspaces/<name>` with both repos; `gh` works; `DEV_CONTAINER_FORTRESS_OPTIONS=claude-code`; no Docker socket and no `/mnt/c` |
| Volumes | eleven `dev-fortress-wb-<name>-*` volumes: the profile's mounts, `brew`, and the two Claude Code paths |
| `up --remove-existing-container` after a state marker and `brew install hello` | marker, `hello`, and Claude Code 2.1.329 all kept |

Found on the way: every `containers/common/` helper was copied in before the
Homebrew floor on Ubuntu and Arch, so any helper edit rebuilt the floor (about
3 minutes). Only `ft-brew-floor` and `/etc/gitconfig` now precede it, and the
rest use `COPY --chmod=0755` after it. A rebuild after a helper edit now takes
11 s with the floor cached.

Still open for the acceptance: a fresh user following
`docs/guides/workbench-usage.md` cold, the VS Code path, a real login and push from
inside a workbench, and archiving `tboss-workspace` with a pointer (an
operator action). Deferred to the always-on workbench work: persisting
`~/.vscode-server` and `"shutdownAction": "none"`.

Workbench prerequisites settled on 2026-11-20: a workbench sits on a full
Dev Fortress workstation, the quickstart in `host` mode, which already brings
`ft`, Docker, `shell-config`, and the Homebrew toolchain. The `devcontainer`
CLI joined the hosts through a new host-only tool-pool group,
`[homebrew.host]` (`brew/Brewfile.host`, appended to the host playbook's
list), so the container floor stays free of it and of Node; a test keeps the
two apart. VS Code and its Dev Containers extension stay a documented
prerequisite. `--mode workspace` hosts lack Homebrew, so they do not support
workbenches yet. The quickstart gained an optional workbench step, and the
workbench guide now frames the two layers, workstation and workbench, as
rebuildable from `~/.config/dev-container-fortress/` alone. The cold run of
the guide is planned on bare-metal Ubuntu.

Merged on 2026-11-20 as #7 (`77d964d`) after CI passed every image job,
including the `ubuntu-full` layer smoke tests that a shared Homebrew volume
fixed. `GrndZero101/tboss-workspace` was then deleted rather than archived:
the operator was its only user and never used it day to day. It had no
issues, pull requests, or forks, and its local-only leftovers (a `TODO.md` for
the `state`, `zoxide`, and `atuin` mounts, and a docs commit removing
hard-coded paths) are both superseded by workbenches.
