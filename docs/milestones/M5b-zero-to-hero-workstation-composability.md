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

- [ ] One documented command takes a fresh Ubuntu 24.04 machine to a converged host workstation: `curl -fsSL …/install.sh | sh`
- [ ] The installer detects the platform, installs its own native prerequisites with one `sudo` step, and fails clearly on unsupported platforms such as macOS
- [ ] The installer registers `localhost` in `hosts.toml` when it is missing and runs the host bootstrap without a separate operator step
- [ ] `host` is the default mode; a `workspace` mode gives a thin host with Docker and `ft`, plus a ready daily-driver workspace
- [ ] The Linuxbrew role tracks the latest stable Homebrew tag, and a fresh host converges in one pass, with the idempotency pass reporting `changed=0`
- [ ] Re-running the command on an already converged or hand-built host is safe and reports what it changed
- [ ] A Git identity step works non-interactively from environment variables, prompts only on a TTY, and documents a manual fallback for corporate and GitLab identities
- [ ] Dev Fortress installs stock tmux with no config by default, and offers `minimal`, `full`, and `raidboss` profiles ported from the `dotfiles` repo, each selectable with one setting
- [ ] Claude Code is installed by default on host targets through its native installer, so it updates itself between bootstrap runs
- [ ] The flow is verified on fresh WSL2 Ubuntu, fresh Ubuntu EC2 running the one-liner on the box, and one brownfield host
- [ ] One "Zero to Hero" quickstart replaces the scattered onramp docs, and `README.md` points to it

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
| tmux profile | none (stock tmux, no config written) | `DEV_CONTAINER_FORTRESS_TMUX_PROFILE=full` |
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
   the terminal

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
and one re-run. `full` and `raidboss` need tmux 3.8+, which Homebrew provides
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
- the bootstrap sets the profile only when one is requested explicitly or no
  link exists yet, so a re-run never undoes a `csm` choice

## Issue Drafts

### M5b-1 Spike the single-prompt privilege model

- [x] Problem: native packages and Ansible `become` both need root, and two password prompts break the one-command promise
- [x] Scope: test whether a cached `sudo` timestamp reaches Ansible local `become`, compared with passing `-K`, on WSL2 and a password-protected Ubuntu host
- [x] Acceptance: one documented privilege model with at most one prompt (see Privilege above; the real WSL2 run is still in the verification list)

### M5b-2 Make the installer install its own prerequisites

- [ ] Problem: `install.sh` exits on a fresh Ubuntu because `zsh` is missing
- [ ] Scope: platform detection, apt prerequisites, and clear failures for macOS and other platforms
- [ ] Acceptance: `install.sh` succeeds on a stock Ubuntu 24.04 image with only `curl`

### M5b-3 Chain registration and host bootstrap

- [ ] Problem: `hosts.toml` and `ft host bootstrap` are separate manual steps
- [ ] Scope: register `localhost` when missing and run the host bootstrap from the installer
- [ ] Acceptance: one command reaches a converged host

### M5b-4 Add the workspace mode

- [ ] Problem: there is no thin-host path from the one-liner
- [ ] Scope: `DEV_CONTAINER_FORTRESS_MODE=workspace` installs the bootstrap floor and Docker, then builds the daily-driver workspace locally, with an opt-in to pull the published image
- [ ] Acceptance: `ft workspace enter ubuntu-full` works straight after the installer finishes

### M5b-5 Pin stable Homebrew and converge in one pass

- [ ] Problem: the role tracks Homebrew's development branch, the first `M5a` EC2 converge hit a duplicate-pour race, and the Linuxbrew and `neovim_kickstart` tasks still changed on a second pass
- [ ] Scope: check out the latest stable tag, and fix whatever keeps the second pass changing
- [ ] Acceptance: a fresh host converges in one pass, then reports `changed=0`

### M5b-6 Add the Git identity step

- [ ] Problem: fresh hosts and workspaces have no identity, and GitHub declines pushes that use a private email
- [ ] Scope: env-driven identity, TTY prompt, manual fallback, and an optional forge login start
- [ ] Acceptance: a non-interactive run never blocks, and a corporate or GitLab user can follow the documented manual path

### M5b-7 Port the tmux profiles

- [ ] Problem: tmux setup lives only in the separate `dotfiles` repo
- [ ] Scope: port the `minimal`, `full`, and `raidboss` profiles into a role with one profile variable, a no-config default, and brownfield-safe linking
- [ ] Scope (`shell-config`): add a `csm` tmux profile command with an `fzf` picker and a native fallback, reading the Dev Fortress profile directory
- [ ] Acceptance: the default leaves stock tmux untouched, each profile installs and starts cleanly on Ubuntu, `csm` switches profiles, including back to none, and a bootstrap re-run keeps the `csm` choice

### M5b-8 Consolidate the onramp docs

- [ ] Problem: the onramp is spread across four documents
- [ ] Scope: one "Zero to Hero" quickstart covering modes, overrides, identity, and tmux, linked from `README.md`
- [ ] Acceptance: a new user needs only that page to reach a working workstation

### M5b-9 Install Claude Code on host targets

- [ ] Problem: Claude Code is installed by hand on every new host
- [ ] Scope: a host role that runs the native installer as the operator user, skips hosts where it already exists, and leaves updates to Claude Code itself
- [ ] Acceptance: `claude --version` works after a fresh bootstrap, and a re-run reports no change

## Verification Notes

- [ ] Fresh WSL2 Ubuntu instance, default command
- [ ] Fresh Ubuntu EC2 instance, the one-liner run on the box itself (the `localhost` path, which `M5a` did not exercise)
- [ ] Ubuntu desktop or server, if one is available
- [ ] Brownfield: re-run on an already converged host, then on a hand-built host with existing dotfiles
- [ ] `workspace` mode on a fresh host
- [ ] A stock `ubuntu:24.04` container as a fast CI check of the installer prerequisites

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
- Claude Code is a default package on every target, installed through its
  native installer so it updates itself (the container side is in `M5c`)

Settled when starting the milestone:

- the tmux profiles live in Dev Fortress, with the reason recorded in
  `AGENTS.md` and `docs/architecture.md`
- the default is stock tmux with no config; `minimal`, `full`, and `raidboss`
  are all ported from `dotfiles` and selected with one setting
- `workspace` mode builds the image locally by default and pulls the published
  image only on request

## Progress Notes

Drafted on 2026-10-18 after the `M5a` EC2 loop, which supplied most of the gap
list.

Findings from the `M5a` rerun to fold into the issues above:

- `ft deploy init` does not run `bootstrap.zsh`, and nothing pins the Python
  version, so the host `.venv` picked up Homebrew's Python 3.15 instead of the
  uv-managed 3.14 (relevant to `M5b-3`)
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
  when interop is off (relevant to `M5b-8`)

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
