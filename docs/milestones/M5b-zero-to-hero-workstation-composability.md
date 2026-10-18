# M5b Zero to Hero: Workstation Composability

## Status

- [ ] Milestone complete
- [x] Active milestone

## Objective

Take a brand-new or existing Ubuntu machine to a working Dev Fortress
workstation from one `curl | sh` command with sane defaults, while keeping the
pieces composable: host or thin-workspace mode, optional tmux profiles, and an
identity step that works for personal, corporate, and GitLab setups.

The same default command should work on a fresh WSL2 Ubuntu instance, an
Ubuntu desktop or server, and an Ubuntu EC2 instance stood up independently.
Re-running it on a brownfield host should converge, not clobber.

This milestone covers the first two Dev Fortress use cases: a direct Ubuntu
host and WSL2 Ubuntu. The container use cases, a VS Code devcontainer and a
devcontainer CLI terminal mode, belong to
[`M5c`](M5c-composable-container-workspaces.md).

## Current Gap

As of 2026-10-18 a fresh Ubuntu machine needs about seven manual steps:

1. `sudo apt install git curl zsh ...`, because `install.sh` exits when `zsh`
   or `git` is missing
2. `curl … install.sh | sh`, which stops after installing `uv`, `ft`, and
   Ansible
3. copy `ft/targets/hosts.example.toml` into the XDG config tree
4. `ft host bootstrap localhost -K`
5. open a new shell, sometimes after a manual `chsh`
6. set a Git identity and log in to the forge, which nothing covers
7. optionally build and enter a workspace

The roles behind step 4 are proven on WSL2 Ubuntu as `localhost` and on Ubuntu
EC2 over SSH (`M5a`), but the onramp around them is manual and spread across
`README.md`, `docs/workstation-usage.md`, `docs/wsl-bootstrap.md`, and
`docs/ec2-development-loop.md`.

## Exit Criteria

- [x] One documented command takes a fresh Ubuntu 26.04 LTS machine to a converged host workstation: `curl -fsSL …/install.sh | sh` (fresh WSL2 and fresh arm64 EC2, 2026-10-18)
- [x] Ubuntu 26.04 LTS is the default release for container images and EC2 hosts, and the newest release (26.10 today) is one setting away on each, so a new release can be tried with the full toolchain (`M5b-10`: `UBUNTU_RELEASE`, the `ubuntu-full-rolling` profile, and `TF_VAR_ubuntu_release`)
- [x] The installer detects the platform, installs its own native prerequisites with one `sudo` step, and fails clearly on unsupported platforms such as macOS (`M5b-1`, `M5b-2`; one `sudo-rs` prompt on every fresh run)
- [x] The installer registers `localhost` in `hosts.toml` when it is missing and runs the host bootstrap without a separate operator step (`M5b-3`; `ft` falls back to the repo example manifest's `localhost`, so no `hosts.toml` is written or needed)
- [x] `host` is the default mode; a `workspace` mode gives a thin host with Docker and `ft`, plus a ready daily-driver workspace (fresh WSL2 Ubuntu 26.04, 2026-10-18)
- [x] The Linuxbrew role tracks the latest stable Homebrew tag, and a fresh host converges in one pass, with the idempotency pass reporting `changed=0` (arm64 EC2 on `7.0.9`, 2026-10-18)
- [x] Re-running the command on an already converged or hand-built host is safe and reports what it changed (the operator's WSL2 host, 2026-10-18; a seeded hand-built host with end-of-run notices, 2026-10-19)
- [x] A Git identity step works non-interactively from environment variables, prompts only on a TTY, and documents a manual fallback for corporate and GitLab identities (`ft identity`, 2026-10-18)
- [x] Dev Fortress installs stock tmux with no config by default, and offers `minimal`, `full`, and `raidboss` profiles ported from the `dotfiles` repo, each selectable with one setting (the `tmux-*` options, 2026-10-18)
- [x] Large extras are optional components, off by default and selectable by flag, environment variable, config file, or a checkbox picker; Claude Code (`claude-code`) is the first, installed through its native installer so it updates itself between bootstrap runs
- [x] The flow is verified on fresh WSL2 Ubuntu, fresh Ubuntu EC2 running the one-liner on the box, and one brownfield host (fresh WSL2 and arm64 EC2, 2026-10-18; brownfield, 2026-10-19)
- [x] One "Zero to Hero" quickstart replaces the scattered onramp docs, and `README.md` points to it (`docs/quickstart.md`, 2026-10-19)

## Non-Goals

- [ ] macOS hosts; they are the next platform after this milestone
- [ ] Arch, Alpine, or other distros as one-liner hosts
- [ ] Integrating the separate `dotfiles` repo; it stays opt-in and user-run
- [ ] Porting the `zsh-*` packages from `dotfiles`; `shell-config` owns zsh
- [ ] A curl-installed `ft` binary distribution
- [ ] Automating forge logins beyond starting the documented CLI flow

## Design Direction

### One Entrypoint, Thin Layers

`install.sh` stays the single public entrypoint and stays POSIX `sh`, because
it runs before `zsh` exists. It should only:

1. detect the platform and fail clearly when unsupported
2. install native prerequisites (`git`, `curl`, `zsh`, `python3`)
3. clone or refresh the checkout and run `bootstrap.zsh`
4. hand off to `ft` for everything after that

Host convergence stays in Ansible, and the mode, target registration, and
identity steps stay in `ft`. The installer should not grow its own provisioning
logic.

### Defaults and Overrides

Every choice has a default and an environment-variable override, following the
existing `DEV_CONTAINER_FORTRESS_*` pattern:

| Setting | Default | Example override |
| --- | --- | --- |
| install directory | XDG-aligned checkout path | `DEV_CONTAINER_FORTRESS_DIR` |
| mode | `host` | `DEV_CONTAINER_FORTRESS_MODE=workspace` |
| workspace image | local build | `DEV_CONTAINER_FORTRESS_WORKSPACE_IMAGE=published` |
| `shell-config` profile | `zsh-tll-citadel-dev-fortress` | existing profile variable |
| tmux profile | none (stock tmux, no config written) | `DEV_CONTAINER_FORTRESS_OPTIONS=tmux-full` |
| optional components | none | `DEV_CONTAINER_FORTRESS_OPTIONS=claude-code,tmux-full`, or `options.toml` |
| option picker | off | `DEV_CONTAINER_FORTRESS_INTERACTIVE=1` |
| Git identity | prompt on a TTY, else skip with a hint | `DEV_CONTAINER_FORTRESS_GIT_NAME`, `DEV_CONTAINER_FORTRESS_GIT_EMAIL` |

Arguments after `sh -s --` should map to the same settings for people who
prefer flags.

### Modes

- `host`: today's full host bootstrap. Native packages, Docker, `shell-config`,
  zinit, login shell, Homebrew tools, Neovim kickstart, and the chosen tmux
  profile.
- `workspace`: the bootstrap floor plus Docker and `ft`, then a ready
  daily-driver workspace. Build the image locally by default, because
  corporate environments may block or distrust public registries. Pulling the
  published `ghcr.io/grndzero101/dev-container-fortress:ubuntu-full` image is
  an opt-in for speed.

### Privilege

The installer needs `sudo` for native packages and Ansible needs `become` for
host roles. The `M5b-1` spike settled on one prompt, from a cached `sudo`
timestamp:

1. running as root skips `sudo` entirely; otherwise the installer runs
   `sudo -v` once and fails clearly when the user cannot use `sudo`
2. a background `sudo -n -v` loop refreshes the timestamp until the installer
   exits, because a fresh Homebrew converge can outlast the 15-minute default
3. the installer runs the `apt` prerequisites and then the `localhost` host
   bootstrap without `-K`. Ansible's `sudo` plugin passes `-n`, so it reuses
   the cached timestamp
4. nothing in the chain may start a new session (`setsid` or
   `start_new_session`), because Ubuntu's default `tty` timestamp is tied to
   the terminal. ansible-core 2.19+ does exactly that for every worker, so
   `ft` renders `ansible_worker_session_isolation: false` for local-connection
   targets only

`sudo` reads the password from `/dev/tty`, so the prompt still works under
`curl | sh`. Hosts with passwordless `sudo`, such as EC2, never prompt. Remote
SSH targets keep `ft host bootstrap -K`, because a local timestamp does not
reach them.

### Brownfield Safety

`shell-config` already moves conflicting dotfiles aside instead of deleting
them. The tmux role and identity step should follow the same rule: never
overwrite an existing `~/.tmux.conf` or Git identity silently.

### Git Identity

- read `DEV_CONTAINER_FORTRESS_GIT_NAME` and `..._GIT_EMAIL` first
- on a TTY, prompt with the current value as the default, and mention the
  GitHub noreply address for accounts that keep email private
- off a TTY, skip and print the manual commands
- start `gh auth login --web` or `glab auth login` only when asked; never block
  bootstrap on a forge login
- document the manual path for corporate forges, SSO, and personal access tokens

### tmux Profiles

Port `tmux-minimal`, `tmux-full`, and `tmux-raidboss` from the `dotfiles` repo
into a Dev Fortress role with one profile variable. The default is no profile:
tmux is installed and runs with its stock settings, and Dev Fortress writes no
config. Switching to `full`, the operator's daily profile, must be one setting
and one re-run.

The profiles are optional components (`M5b-11`) rather than a separate
setting: `tmux-minimal`, `tmux-full`, and `tmux-raidboss` form one pick-one
choice, because they share one Ansible variable. `ft` rejects two of them in
one selection, the picker reopens until the choice is valid, and the inventory
carries `dev_container_fortress_tmux_profile` as the chosen profile or `none`.
So `--options tmux-full`, `DEV_CONTAINER_FORTRESS_OPTIONS`, `options.toml`, and
`--interactive` all work for tmux as they do for Claude Code. `full` and `raidboss` need tmux 3.8+, which Homebrew provides
on Ubuntu, and they bootstrap tpm plugins on first start.

Dev Fortress owns these profiles even though `AGENTS.md` keeps shell UX in
`shell-config`: tmux is terminal-multiplexer setup for the provisioned
workstation rather than shell behavior, and a working tmux setup should come
out of the box without the separate `dotfiles` repo. Personal tmux tweaks stay
in `dotfiles`.

Switching profiles after install belongs to `csm`, the `shell-config` operator
surface: something like `csm tmux-profile [name]`, with `csm tmux-profile -i`
using the existing `csm` picker (`fzf` when installed, a native zsh menu
otherwise). The two repos share a small contract:

- Dev Fortress installs the profile files in one XDG-aligned directory and
  owns their content
- the active profile is one symlink at `${XDG_CONFIG_HOME}/tmux/tmux.conf`,
  and `none` means no Dev Fortress link, so stock tmux applies
- `csm` lists whatever profiles that directory contains, flips the link, and
  reloads running tmux servers with `tmux source-file`
- the bootstrap relinks only when the selected profile differs from the one
  it last applied, recorded in
  `${XDG_STATE_HOME}/dev-container-fortress/tmux-profile`, so a re-run never
  undoes a `csm` choice, including `none`; changing the option still switches
- neither side replaces a `tmux.conf` it did not link, or links a profile
  while `~/.tmux.conf` exists, because tmux loads both files

## Issue Drafts

### M5b-1 Spike the single-prompt privilege model

- [x] Problem: native packages and Ansible `become` both need root, and two password prompts break the one-command promise
- [x] Scope: test whether a cached `sudo` timestamp reaches Ansible local `become`, compared with passing `-K`, on WSL2 and a password-protected Ubuntu host
- [x] Acceptance: one documented privilege model with at most one prompt (see Privilege above; the real WSL2 run is still in the verification list)

### M5b-2 Make the installer install its own prerequisites

- [x] Problem: `install.sh` exits on a fresh Ubuntu because `zsh` is missing
- [x] Scope: platform detection, apt prerequisites, and clear failures for macOS and other platforms
- [x] Acceptance: `install.sh` succeeds on a stock Ubuntu 24.04 image with only `curl` (`--mode cli`, from an image with none of the prerequisites)

### M5b-3 Chain registration and host bootstrap

- [x] Problem: `hosts.toml` and `ft host bootstrap` are separate manual steps
- [x] Scope: register `localhost` when missing and run the host bootstrap from the installer. No registration is needed: `ft` falls back to `hosts.example.toml`, which defines `localhost`, and merges a user `hosts.toml` over it
- [x] Acceptance: one command reaches a converged host (fresh Ubuntu 26.04 WSL2, 2026-10-18)

### M5b-4 Add the workspace mode

- [x] Problem: there is no thin-host path from the one-liner
- [x] Scope: `DEV_CONTAINER_FORTRESS_MODE=workspace` installs the bootstrap floor and Docker, then builds the daily-driver workspace locally, with an opt-in to pull the published image. `ft host bootstrap --mode workspace` renders `dev_container_fortress_host_mode`, which skips the workstation roles and the optional components; the installer then runs `ft workspace build ubuntu-full`, or `ft workspace pull ubuntu-full` with `--workspace-image published`, through a root `su` login for the user while the new `docker` group is not yet active in the installer's process
- [x] Acceptance: `ft workspace enter ubuntu-full` works straight after the installer finishes (fresh WSL2 Ubuntu 26.04, 2026-10-18: the installer exited 0, and a new login entered the workspace as `vscode` with `ft`, `gh`, and the AWS CLI working; `ft workspace pull ubuntu-full` also tagged the published image)

### M5b-5 Pin stable Homebrew and converge in one pass

- [x] Problem: the role tracks Homebrew's development branch, the first `M5a` EC2 converge hit a duplicate-pour race, and the Linuxbrew and `neovim_kickstart` tasks still changed on a second pass
- [x] Scope: check out the latest stable tag, and fix whatever keeps the second pass changing. The role now resolves the newest `X.Y.Z` tag, the same one `brew update` picks, and `dev_container_fortress_homebrew_version` overrides it
- [x] Acceptance: a fresh host converges in one pass, then reports `changed=0` (fresh arm64 EC2 one-liner on `7.0.9`, 2026-10-18)

### M5b-6 Add the Git identity step

- [x] Problem: fresh hosts and workspaces have no identity, and GitHub declines pushes that use a private email
- [x] Scope: env-driven identity, TTY prompt, manual fallback, and an optional forge login start. `ft identity`, run by the installer in every mode, with `--local` for workspace checkouts and `--login github|gitlab`
- [x] Acceptance: a non-interactive run never blocks, and a corporate or GitLab user can follow the documented manual path

### M5b-7 Port the tmux profiles

- [x] Problem: tmux setup lives only in the separate `dotfiles` repo
- [x] Scope: port the `minimal`, `full`, and `raidboss` profiles into a role with one profile variable, a no-config default, and brownfield-safe linking. `dev_fortress_tmux`, selected by the pick-one `tmux-*` options; `gitmux` and `sesh` joined the Homebrew pool
- [x] Scope (`shell-config`): add a `csm` tmux profile command with an `fzf` picker and a native fallback, reading the Dev Fortress profile directory. `csm tmux-profile [-i] [name|none]`, merged to `shell-config` `main` (PR #1, 2026-10-18)
- [x] Acceptance: the default leaves stock tmux untouched, each profile installs and starts cleanly on Ubuntu, `csm` switches profiles, including back to none, and a bootstrap re-run keeps the `csm` choice (the role run on the WSL2 Ubuntu 26.04 workstation against an isolated `HOME`, each profile started on its own tmux server, 2026-10-18; a fresh-host one-liner with `--options tmux-full` is in the verification list)

### M5b-8 Consolidate the onramp docs

- [x] Problem: the onramp is spread across four documents
- [x] Scope: one "Zero to Hero" quickstart covering modes, overrides, identity, and tmux, linked from `README.md`. `docs/quickstart.md`, 2026-10-19; it also covers existing machines, re-runs, testing a branch, WSL2, and troubleshooting. `README.md` keeps only the one-liner, `docs/wsl-bootstrap.md` became WSL-specific notes, and `docs/workstation-usage.md` points to it
- [x] Acceptance: a new user needs only that page to reach a working workstation

### M5b-9 Install Claude Code on host targets

- [x] Problem: Claude Code is installed by hand on every new host
- [x] Scope: a host role that runs the native installer as the operator user, skips hosts where it already exists, and leaves updates to Claude Code itself. `dev_fortress_claude_code`, enabled by the `claude-code` option (`M5b-11`)
- [x] Acceptance: with `claude-code` selected, `claude --version` works after a fresh bootstrap, and a re-run reports no change (arm64 EC2, 2026-10-18)

### M5b-10 Default to Ubuntu 26.04 and make release trials easy

- [x] Problem: everything defaulted to 24.04, and trying a new Ubuntu release with the full toolchain meant hand-editing Dockerfiles and Terraform
- [x] Scope: 26.04 as the default for the Ubuntu image, EC2 AMI, and installer support list; a profile-level `os_release` with an `ubuntu-full-rolling` profile; `TF_VAR_ubuntu_release` for EC2
- [x] Acceptance: `ubuntu-full` builds and validates on 26.04, `ubuntu-full-rolling` builds and validates on 26.10, and the host roles converge on a 26.04 host

### M5b-11 Make large extras optional

- [x] Problem: agentic coding tools are large and not wanted on every machine, so they should not be in the default bootstrap
- [x] Scope: an option catalog in `ft`, a non-interactive selection (`--options` on `ft host bootstrap` and `install.sh`, `DEV_CONTAINER_FORTRESS_OPTIONS`, or `options.toml`), and a checkbox picker (`ft options pick`, `install.sh --interactive`); `claude-code` is the first option
- [x] Acceptance: the default one-liner installs no optional component, `--options claude-code` installs Claude Code, and `--interactive` under `curl | sh` shows the picker and saves the choice (arm64 EC2 for the default and `--interactive` runs; `--options` by unit tests and the container runs)

## Verification Notes

- [x] Fresh WSL2 Ubuntu instance, default command (Ubuntu 26.04.1 LTS store image, 2026-10-18)
- [x] Fresh Ubuntu EC2 instance, the one-liner run on the box itself (the `localhost` path, which `M5a` did not exercise; `m8g.large` arm64, 2026-10-18)
- [ ] Ubuntu desktop or server, if one is available
- [x] Brownfield: re-run on an already converged host (operator's `dev-fortress` WSL2 workstation, 2026-10-18: `changed=12`, then `changed=0`), then on a hand-built host with existing dotfiles (WSL2 Ubuntu 26.04 store image, 2026-10-19)
- [x] `workspace` mode on a fresh host (fresh WSL2 Ubuntu 26.04 store image, 2026-10-18; a fresh EC2 run is still open)
- [x] A fresh-host one-liner with `--options tmux-full`, then `csm tmux-profile raidboss` and a re-run that keeps it (fresh WSL2 Ubuntu 26.04 store image, 2026-10-19)
- [ ] A stock `ubuntu:26.04` container as a fast CI check of the installer prerequisites

## Branch and Merge Plan

- [x] Start after `M5a` is squash-merged
- [x] Branch from `main` as `feat/m0005b-zero-to-hero`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Decisions

Recorded on 2026-10-18:

- one `curl | sh` command is the public starting point
- `host` mode is the default; `workspace` is the thin variant
- Ubuntu and WSL2 Ubuntu come first; macOS is the next platform
- the `dotfiles` repo stays opt-in and outside Dev Fortress; its tmux profiles
  are ported into Dev Fortress
- the identity step needs a manual fallback for corporate and GitLab use
- Homebrew moves to its latest stable tag for one-pass convergence
- Claude Code installs through its native installer so it updates itself
  (the container side is in `M5c`). It was first planned as a default package,
  then made an optional component the same day, because agentic coding tools
  are large (`M5b-11`)

Settled when starting the milestone:

- the tmux profiles live in Dev Fortress, with the reason recorded in
  `AGENTS.md` and `docs/architecture.md`
- the default is stock tmux with no config; `minimal`, `full`, and `raidboss`
  are all ported from `dotfiles` and selected with one setting
- `workspace` mode builds the image locally by default and pulls the published
  image only on request

Recorded while building `M5b-4` (2026-10-18):

- `workspace` mode is the same playbook with one `dev_container_fortress_host_mode`
  variable rather than a second playbook, so a thin host becomes a full one by
  re-running in `host` mode
- the optional components are skipped in `workspace` mode; they are
  workstation extras, and Claude Code in containers belongs to `M5c`
- workspace mode prepares `ubuntu-full` only; other profiles stay one
  `ft workspace build` away
- `ft workspace pull` uses a per-profile `published_image` from
  `profiles.toml`, pulls with an explicit `--platform` so a missing
  architecture fails at pull time (CI publishes amd64 only), and tags the
  result as the local workspace image so `ft workspace enter` skips the build

Recorded while building `M5b-7` (2026-10-18):

- the tmux profiles are pick-one bootstrap options instead of a separate
  `DEV_CONTAINER_FORTRESS_TMUX_PROFILE` setting, so every selection path
  covers them
- selecting any `tmux-*` option installs all three profiles, so `csm` can
  switch without a bootstrap; plugins are cloned only for the active profile,
  and at startup for one chosen later
- the profiles keep their companion files inside the profile directory
  (`gitmux.conf`, scripts) instead of writing `~/.gitmux.conf`; `sesh.toml`
  stays in `dotfiles`, because its sessions are personal
- each profile loads `${XDG_CONFIG_HOME}/tmux/local.conf` last, so personal
  settings survive the bootstrap rewriting the profiles

## Resume Here

State at the end of 2026-10-19, on `feat/m0005b-zero-to-hero` (no PR yet;
the 2026-10-19 commits are not pushed):

- done: `M5b-1` (one `sudo` prompt), `M5b-2` (installer prerequisites),
  `M5b-3` (chained `localhost` bootstrap), `M5b-6` (`ft identity`), `M5b-10`
  (Ubuntu 26.04 default and `ubuntu-full-rolling`), and the host-mode login
  shell. A fresh WSL2 26.04 run converged in one pass and re-ran with
  `changed=0`
- also done: `M5b-5` (stable Homebrew tag), `M5b-9` (Claude Code role), and
  `M5b-11` (optional components, `claude-code` off by default), all accepted
  on a fresh arm64 EC2 one-liner run
- also done: `M5b-7` (tmux profiles as the pick-one `tmux-*` options, plus
  `csm tmux-profile`), verified with an isolated `HOME` on the WSL2
  workstation. The `shell-config` half is merged to its `main` (PR #1)
- also done: `M5b-4` (`workspace` mode, local build by default, opt-in
  `--workspace-image published`), accepted on a fresh WSL2 Ubuntu 26.04 distro
- decided: stock tmux by default with `csm` switching, local workspace builds
  by default, and Homebrew in containers in `M5c`
- also done (2026-10-19): Dev Fortress code runs only on the uv-managed
  Python. The repo-root `.python-version` is the one pin (bump it alone, after
  checking `ansible-core` supports the version; 3.15 waits), local targets run
  Ansible modules on that Python, and `python-preference = "only-managed"`
  keeps `uv run` off distro and Homebrew Pythons
- also done (2026-10-19): the fresh-host `--options tmux-full` run and the
  hand-built brownfield host, which added end-of-run notices and kept uv's
  installer out of user dotfiles in host mode

Next, in suggested order:

1. open the `M5b` PR: `M5b-8` (the quickstart) is done
2. optional: `workspace` mode on a fresh arm64 EC2 host (local build only; the
   published images are amd64), now a natural first `M7b` fleet check

Working notes for the next session:

- testing strategy from 2026-10-19: verify on the operator's `dev-fortress`
  WSL2 host as the brownfield case, and on disposable EC2 hosts for fresh
  runs, not throwaway WSL2 distros. The five-host EC2 fleet is planned in
  [`M7b`](M7b-cloud-test-fleet.md)
- the retired throwaway WSL2 recipe, for reference: `wsl.exe --install
  Ubuntu-26.04 --name m5b-test --no-launch`, a password-`sudo` user added as
  root, the branch shared as a git bundle in `/mnt/wsl`, and the one-liner run
  under `script` with a background `sleep infinity` keepalive. Unregister all
  test distros in one `cmd.exe /c "wsl --unregister a & wsl --unregister b"`
  call, because the first one wipes `WSLInterop`
- stopping any sibling WSL2 distro wipes `WSLInterop`; restore it with
  `wsl-restore-interop` in a normal terminal
- `wsl.exe -d <distro> -- <cmd>` expands `$` in `<cmd>` before the target
  shell sees it; put anything with variables in a script under `/mnt/wsl` and
  run that
- the brownfield seed script used on 2026-10-19 writes one marker line per
  dotfile and records checksums, so a `sha256sum -c` after the run shows
  exactly which files changed
- container recipe for installer checks: `ubuntu:26.04` with `/src` mounted and
  `[safe] directory = *` in `~/.gitconfig`, then
  `sh /src/install.sh --repo /src --ref <branch>`

## Progress Notes

Drafted on 2026-10-18 after the `M5a` EC2 loop, which supplied most of the gap
list.

Findings from the `M5a` rerun to fold into the issues above:

- `ft deploy init` does not run `bootstrap.zsh`, and nothing pins the Python
  version, so the host `.venv` picked up Homebrew's Python 3.15 instead of the
  uv-managed 3.14 (relevant to `M5b-3`). Fixed: `pyproject.toml` now sets
  `python-preference = "only-managed"`
- WSL interop can be disabled, which breaks `wslview` browser opening and the
  Windows profile lookup in `ft host ssh-config --windows`. The onramp must not
  assume interop on WSL2. On the operator's machine the cause was a sibling
  distro: all WSL2 distros share one kernel, so binfmt registrations are
  VM-wide, and an idle `Ubuntu-22.04` shutdown cleared `WSLInterop` for every
  distro even though WSL's generated drop-in disables
  `systemd-binfmt --unregister`. `sudo systemctl restart systemd-binfmt`
  restores it. A self-heal timer in the WSL host role is worth considering
- `ft host ssh-config` on WSL2 writes only the WSL config, but VS Code on
  Windows reads the Windows one. It should detect WSL and point to `--windows`,
  and fall back to the single `/mnt/c/Users/*` profile with a `.ssh` directory
  when interop is off (relevant to `M5b-8`). The quickstart and WSL notes
  document `--install --windows` and the `--windows-ssh-dir` workaround; the
  automatic WSL detection and `/mnt/c/Users/*` fallback are not built yet

### Brownfield hand-built host, 2026-10-19

Throwaway distros (Ubuntu 26.04.1 LTS store image) seeded as a hand-built
host: custom `~/.bashrc`, `~/.profile`, `~/.zshrc`, `~/.zshenv`, `~/.zprofile`,
and `~/.tmux.conf`, a `~/.gitconfig` with an identity and an alias, plus
`~/.config/nvim/init.lua`, `~/.config/starship.toml`, and `~/.ssh/config`. The
one-liner ran with `--options tmux-full` and no Git identity variables.

| Run | Result |
| --- | --- |
| `m5b-brown`, 1 | ✅ `changed=30 failed=0`; identity kept (`Brownfield User`); tmux link held back by `~/.tmux.conf`; Neovim, starship, SSH, and Git configs byte-identical |
| `m5b-brown2`, 1, after the fixes | ✅ `changed=30`; only `~/.profile` and `~/.zprofile` (marked blocks) and `~/.zshenv` (moved to a backup) changed; the run ended with all three notices |
| `m5b-brown2`, 2 | ✅ 31 s, `changed=0`; the two notices that still applied repeated, the one-off backup notice did not |
| `m5b-brown2`, 3, after moving `~/.tmux.conf` aside and removing `~/.zshrc` | ✅ `changed=3`: `tmux-full` linked, no notices |

A new zsh login found `uv`, `ft`, `brew`, `tmux`, and `nvim`, and an alias
moved into `shell-config.local/<profile>/aliases.zsh` loaded.

Found and fixed:

- uv's standalone installer appended `. "$HOME/.local/bin/env"` to
  `~/.profile`, `~/.bashrc`, and `~/.zshrc`. Host mode now sets
  `UV_NO_MODIFY_PATH=1`, since shell-config owns `PATH` there
- the `~/.zshenv` backup, the now-unread `~/.zshrc`, and the blocked tmux link
  were buried in, or missing from, the Ansible output. They are now end-of-run
  notices above the play recap; the profile's existing `shell-config.local`
  overrides (`env.zsh`, `aliases.zsh`) are where the notice sends old zsh
  settings, so `shell-config` needed no change

### Fresh WSL2 `--options tmux-full` run, 2026-10-19

A throwaway `m5b-test` distro (Ubuntu 26.04.1 LTS store image, `sudo-rs`
0.2.13, `zsh` absent) with a password-`sudo` user, the one-liner piped into
`sh` under `script`, and the branch shared as a bundle:

| Run | Result |
| --- | --- |
| 1, fresh, `--options tmux-full` | ✅ one `sudo` prompt, 4 min 43 s: `ok=93 changed=33 failed=0`, and no interpreter-discovery warning |
| new login | ✅ zsh login shell; `~/.config/tmux/tmux.conf` links the `full` profile; tmux 3.8 starts with prefix `C-Space`, the catppuccin status line, and the tpm plugins already installed |
| `csm tmux-profile raidboss` | ✅ `full -> raidboss`; tmux starts cleanly on it |
| 2, same one-liner again | ✅ 32 s, `ok=88 changed=0`; the link still points at `raidboss` |

The only tmux message is tpm's first-load `unknown variable:
TMUX_PLUGIN_MANAGER_PATH`, which is harmless. The root (`become`) tasks ran on
the uv-managed interpreter without trouble.

### `M5b-4` workspace mode on fresh WSL2, 2026-10-18

Run on a throwaway `m5b-test` distro (Ubuntu 26.04.1 LTS store image,
password-`sudo` user) with the branch shared as a bundle:

| Run | Result |
| --- | --- |
| first one-liner, `--mode workspace` | ❌ converge `changed=8`, then `sg: not found`: Ubuntu 26.04's util-linux `login` ships no `sg` or `newgrp` |
| re-run after switching to root `su` | ✅ converge `changed=0`, image built through `su`, exit 0 |
| new login: `ft workspace enter ubuntu-full` | ✅ `vscode@dev-fortress-workspace-ubuntu-full`, `ft`, `gh`, `aws` |
| re-run with the user removed from `docker` | ✅ converge `changed=1`, build through `su`, summary asks for a new terminal |
| `ft workspace pull ubuntu-full` | ✅ local tag points at the published image |

The installer cannot use the new `docker` group in its own process, so it runs
the build as `su <user>` from root, through the `sudo` session it already
holds; a fresh `su` login picks up the group.

### `M5b-1` privilege spike, 2026-10-18

Run in a throwaway `ubuntu:24.04` container (sudo 1.9.15p5, ansible-core
2.16.3) with a password-protected sudo user, and `script` providing a real
pseudo-terminal for each case:

| Case | Result |
| --- | --- |
| `sudo -v`, then `ansible -b` without `-K`, same terminal | ✅ `uid=0(root)` |
| no cached timestamp, `ansible -b` without `-K` (control) | ❌ fails |
| cached timestamp, Ansible started under `setsid` | ❌ "password is required" |
| cached timestamp, full playbook with fact gathering | ✅ `uid=0(root)` |
| `timestamp_timeout=1`, 75 s idle, no keepalive | ❌ "password is required" |
| `timestamp_timeout=1`, 75 s idle, `sudo -n -v` keepalive | ✅ `uid=0(root)` |

`ft` runs `ansible-playbook` through a plain `subprocess.run` that inherits the
terminal, so it keeps the timestamp. Its only `start_new_session=True` call is
the workspace browser bridge daemon, which is unrelated.

The spike missed one thing: Ubuntu's ansible-core 2.16 keeps workers on the
terminal, but the 2.21 that `bootstrap.zsh` installs calls `os.setsid()` in
every worker (`WORKER_SESSION_ISOLATION`, default on). The first full installer
run in a container prompted once, installed the prerequisites, and then failed
at the first `become` task with "sudo: a password is required". Rendering
`ansible_worker_session_isolation: false` for local targets fixed it.

### `M5b-2` and `M5b-3` installer work, 2026-10-18

`install.sh` gained `--mode host|cli|workspace` (default `host`), matching
environment variables, platform detection, an early systemd check for host
mode, the single `sudo` prompt with a keepalive, missing-only `apt`
prerequisites, and the chained `ft host bootstrap localhost`.

Tested in `ubuntu:24.04` containers, with the branch cloned from a mounted
checkout:

- `--mode cli` as root from an image with no `curl`, `git`, `zsh`, `sudo`, or
  `python3`: prerequisites installed, `ft` worked, and a second run reused the
  packages, checkout, and `uv`
- default `host` mode as a password-`sudo` user, piped into `sh` on a
  pseudo-terminal like `curl | sh`: one password prompt, prerequisites
  installed, and the host roles' `become` tasks ran until the Docker role
  stopped on the missing systemd, which the new early check now reports before
  any change
- found and fixed on the way: re-runs reinstalled `uv` when `~/.local/bin`
  was not on `PATH`, containers on a WSL2 host were labelled WSL2, and the
  ansible-core 2.19+ worker session isolation described above

Still needed: a full host-mode converge on a systemd host, which is the fresh
WSL2 and fresh EC2 rows in the verification notes.

### `M5b-10` Ubuntu release survey, 2026-10-18

| Source | 26.04 LTS (`resolute`) | 26.10 (`stonking`) |
| --- | --- | --- |
| Docker Hub `ubuntu:` tag | ✅ 26.04.1 | ✅, also `rolling` |
| Docker apt repository suite | ✅ | ✅ |
| AWS SSM AMI parameter | ✅ | ✅ |
| WSL store image | ✅ `Ubuntu-26.04` | ❌ interim releases are not published for WSL |

Every Ubuntu package the host roles install exists on both releases. A 26.10
WSL2 distro would need a release upgrade from 26.04, which is not covered yet.

Verified locally the same day:

- `ft workspace build` produced `ubuntu-full` on Ubuntu 26.04.1 LTS and
  `ubuntu-full-rolling` on Ubuntu 26.10
- `ft workspace validate` passed all 16 checks on both
- replacing the 24.04 `ubuntu-full` container with the 26.04 one kept the
  persisted zsh history
- the 171 tests passed inside the 26.10 workspace
- the installer's `--mode cli` passed on stock `ubuntu:26.04` and `ubuntu:26.10`

### Fresh WSL2 Ubuntu 26.04 run, 2026-10-18

A throwaway `m5b-test` distro from the store's `Ubuntu-26.04` image (26.04.1
LTS, systemd on, `zsh` absent) with a password-`sudo` user. The one-liner was
piped into `sh` on a pseudo-terminal, cloning the branch from a git bundle in
`/mnt/wsl`.

| Run | Result |
| --- | --- |
| 1, fresh | one `sudo-rs` prompt, installed `zsh`, converged in 5 min 19 s: `ok=74 changed=26 failed=0` |
| 2, re-run | `changed=0`, but it was still on the old commit: a `--ref` branch never fast-forwarded (fixed) |
| 3, re-run | fast-forwarded, `changed=1`: the login shell, after the host-mode login shell fix |
| 4, re-run | `changed=0` |

A new login session then opened zsh 5.9 with the
`zsh-tll-citadel-dev-fortress` profile. `brew`, `ft`, `uv`, `nvim`,
`starship`, `zoxide`, `atuin`, `fzf`, `rg`, `docker`, and `csm` were all on
`PATH`, `docker run hello-world` worked, and zinit installed its plugins on the
first interactive start.

Found and fixed:

- the login shell stayed `bash`, because the role manages only remote targets
  by default; host mode now sets `DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL=1`
- `--ref <branch>` re-runs fetched without fast-forwarding

Observed, not fixed yet:

- Ubuntu 26.04 ships `sudo-rs`; its timestamp and `-n -v` keepalive behave like
  `sudo` for this flow (but see the EC2 run below for `-v` and mixed
  sudoers rules)
- stopping `m5b-test`, a pristine store image, also wiped `WSLInterop` in
  `dev-fortress`. The wipe is a general sibling-distro problem, not one
  misconfigured distro, and it now reproduces on demand
- Ansible discovered `.venv/bin/python3.14` as the `localhost` interpreter and
  warned that this may change; pinning `/usr/bin/python3` for local targets is
  worth considering
- WSL warns "Failed to start the systemd user session" for a user created with
  `useradd` after first boot; nothing in the run depended on it

### `M5b-5` stable Homebrew, 2026-10-18

Homebrew's installer checks out the newest `X.Y.Z` tag as a local `stable`
branch, and every non-developer `brew update`, including the auto-update before
`brew install`, recreates `stable` at the newest tag. The role pinned `main`, so
the two fought: this workstation was on `stable` at `7.0.9` even though the role
asked for `main`, and a check-mode `git` task pinned to `main` reported
`changed` against it. A run after an auto-update would flip the checkout back to
the development branch, which explains the earlier second-pass change.

The role now lists the remote tags, resolves the newest `X.Y.Z` tag (`7.0.9`
today), and checks it out. Check mode against the same checkout reports no
change for the tag. `brew doctor` only flags a `master` branch, and `brew
update` turns the detached checkout back into `stable` at the same commit, so
Ansible and Homebrew now agree. `dev_container_fortress_homebrew_version`
accepts any tag, branch, or commit, such as `main`, to override it.

The `neovim_kickstart` change from `M5a` did not recur in the later EC2 rerun
or the fresh WSL2 run. It tracks the kickstart `master` branch, so it changes
only when upstream moves. The duplicate-pour race also has not recurred, and
pinning a tag removes one moving part, so no further fix is planned unless it
reproduces.

Then `ft host bootstrap localhost -K` ran twice on the operator's `dev-fortress`
WSL2 workstation, which had last been bootstrapped before this branch. The first
pass reported `changed=12`, including the managed `/etc/docker/daemon.json` and a
Docker restart. The second reported `changed=0`, with the Homebrew checkout
still at `7.0.9`.

### `M5b-6` Git identity, 2026-10-18

`ft identity` sets the global `user.name` and `user.email`, or the current
checkout's with `--local` for workspaces, where `~/.gitconfig` is not
persisted. Flags and the `DEV_CONTAINER_FORTRESS_GIT_NAME` and `..._GIT_EMAIL`
variables replace the current values and name the old ones. Without them, an
existing identity is kept, a terminal is prompted only for missing fields with
the noreply hint, and anything else skips with the manual commands.
`--login github|gitlab`, or `DEV_CONTAINER_FORTRESS_FORGE_LOGIN`, starts the
forge login only on a terminal and only when not already logged in. `gh` and
`glab` joined the host Homebrew set for it.

The installer runs the step in every mode and never fails on it. Under
`curl | sh` stdin is the script, so prompts read `/dev/tty`, and stdin is
`/dev/null` when there is no terminal.

Piped installer runs (`--mode cli`) in stock `ubuntu:26.04` containers:

| Run | Result |
| --- | --- |
| no terminal, no variables | skipped with the `git config` commands; install completed |
| variables set, no terminal | set the global identity without a prompt |
| pseudo-terminal, answers fed in | prompted for both fields and set them |

The forge login itself was not exercised beyond the unit tests; the `gh`
device flow was proven by hand in `M5a`.

### `M5b-9` Claude Code, 2026-10-18

The new `dev_fortress_claude_code` role pipes `https://claude.ai/install.sh`
into `bash` as the target user, guarded by `creates: ~/.local/bin/claude`, then
reports `claude --version`. The installer downloads the binary for the
platform (glibc or musl, x64 or arm64), verifies its SHA-256 against the
release manifest, and refuses to run under `sudo`, so the role uses no
`become`. Once the launcher exists, the role leaves updates to Claude Code.

It first ran by default on `workstation` and `cloud` targets; `M5b-11` below
made it an opt-in option instead.

Run alone against `localhost` with a throwaway `HOME`:

| Run | Result |
| --- | --- |
| 1, fresh | installed 2.1.302, `changed=1`; `claude --version` worked |
| 2, re-run | `changed=0` |

The installer wrote only `~/.local/bin/claude`, `~/.local/share/claude`
(273 MB), `~/.claude`, `~/.claude.json`, and cache and state directories. It
did not touch any shell rc file; `shell-config` already puts `~/.local/bin` on
`PATH`. `ansible-lint` passes on the production profile.

### `M5b-11` optional components, 2026-10-18

Agentic coding tools are large, so the default bootstrap should not install
them. `ft/src/ft/options.py` holds a small catalog (just `claude-code` for now),
each entry mapped to the inventory variable that turns its role on. `ft`
resolves the selection and renders every catalog variable as `true` or `false`
for the `dev_fortress` group, and the playbook defaults each one to `false`.
Precedence, highest first: `--options`, `DEV_CONTAINER_FORTRESS_OPTIONS`,
`${XDG_CONFIG_HOME}/dev-container-fortress/options.toml`, then nothing. `none`
selects nothing explicitly. The deploy and `ft host validate` paths use the
same resolution, so a saved choice applies everywhere.

- `ft options` lists the catalog and where the selection came from
- `ft options pick` is a checkbox picker that saves `options.toml`; it reuses
  the host target picker, now split into a generic `_interactive_multi_select`
- `install.sh --options LIST` and `--interactive` (or
  `DEV_CONTAINER_FORTRESS_INTERACTIVE=1`) map onto the same model. The picker
  reads `/dev/tty`, so it works under `curl | sh`; without a terminal, or when
  cancelled, the installer warns and continues with the non-interactive
  selection
- the Claude Code role now fails clearly on a target without `/bin/bash`
  rather than skipping Alpine silently

Checked: 13 new tests (200 in total), `ruff`, `ansible-lint` on the production
profile, and `shellcheck` on the installer. Driving `ft options pick` on a
pseudo-terminal with Space and Enter saved `enabled = ["claude-code"]`, and
`ft options` then reported it from `config`.

Piped installer runs (`--mode cli`) in stock `ubuntu:26.04` containers:

| Run | Result |
| --- | --- |
| `--interactive` on a pseudo-terminal, Space and Enter fed in | picker shown after `bootstrap.zsh`; saved `enabled = ["claude-code"]`; install completed |
| `--interactive --options claude-code`, no terminal | warned and continued; `ft options` reported `claude-code` from the environment |

Then `ft host bootstrap localhost -K --options claude-code` on the operator's
`dev-fortress` WSL2 workstation, which already had Claude Code, reported
`changed=0`: the role's `creates` guard left the existing self-updating install
alone.

### Fresh arm64 EC2 one-liner, 2026-10-18

A disposable `m8g.large` (Graviton, arm64) spot instance in `ap-southeast-1`
from `ft infra aws-disposable-ubuntu`, on Ubuntu 26.04.1 LTS with `sudo-rs`,
no `zsh`, and the stock `ubuntu` user. The one-liner ran on the box itself
from the branch on GitHub, with the Git identity variables set.

The first attempt stopped at once with "sudo needs a password, but there is no
terminal". The `ubuntu` user has cloud-init's `NOPASSWD: ALL` and also the
password-only `%sudo` group rule, and `sudo -v` checks every entry the user
has (the default `verifypw=all`), so `sudo -n -v` failed even though
`sudo -n true` worked. `M5a` never hit this because it bootstrapped EC2 over
SSH, and the `M5b-1` spike used password-only users. The installer now probes
with `sudo -n true`; the `-n -v` keepalive simply exits on such hosts, where it
is not needed.

| Run | Result |
| --- | --- |
| 1, default | installed `zsh`, `options: none (default)`, converged in 6 min 9 s: `ok=79 changed=26 failed=0`; Claude Code role skipped, no `options.toml`, Homebrew at `7.0.9`, login shell `zsh` |
| 2, `--interactive` over `ssh -tt` | picker shown; Space and Enter saved `claude-code`; `options: claude-code (config)`, `changed=1` in 51 s; `claude` 2.1.302 is an aarch64 ELF on the login `PATH` |
| 3, plain re-run | `options: claude-code (config)`, `changed=0` in 33 s |

Fetching the installer from a `raw.githubusercontent.com` branch URL served a
copy cached from before the fix for a few minutes; pinning the URL to the
commit SHA avoided it. Worth a note in the quickstart for anyone testing a
branch (`M5b-8`).
