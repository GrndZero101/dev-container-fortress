# M5e Zero to Hero: Developer Workstation

## Status

- [ ] Milestone complete
- [x] Active milestone

## Objective

Take a fresh Ubuntu or macOS install to a full DevOps development workstation
with the fewest commands: Dev Fortress and `shell-config` in development mode,
the host toolchain, and a workbench for agentic development, in under an hour
rather than the days or weeks a manual rebuild takes.

`M5b` delivered one command for an Ubuntu operator workstation, and `M5c`
adds workbenches. What is still manual for a developer:

- macOS supports only the installer's `cli` mode, so Docker, Homebrew, and the
  host roles are hand work there
- the login shell runs the installed `~/.config/shell-config`, which the host
  bootstrap resets to `main` on every run, so `shell-config` changes cannot be
  lived in on the host
- the developer path is about ten commands across the installer, a second
  clone, hook setup, a login, a font, and a workbench

## Exit Criteria

- [ ] The installer's `host` mode converges a fresh macOS install (Apple silicon first) as it does Ubuntu
- [ ] A developer mode clones `shell-config` beside the Dev Fortress checkout and runs the host shell from that clone, and the host bootstrap leaves a developer's checkout alone instead of resetting it
- [ ] The developer path in `DEVELOPMENT.md` shrinks to the installer, one login, and `ft workbench init` plus `clone`
- [ ] Timed cold runs from a fresh bare-metal Ubuntu install and a fresh macOS install finish in under an hour, with the time recorded here

## Non-Goals

- [ ] Installing desktop apps beyond what the workstation needs, such as VS Code; the docs list them as prerequisites
- [ ] Windows-native hosts; WSL2 stays the Windows path
- [ ] Integrating the separate `dotfiles` repo beyond restoring `~/.config/dev-container-fortress/` from it

## Issue Drafts

### M5e-1 Developer mode for `shell-config`

- [ ] Problem: the host bootstrap owns `~/.config/shell-config` and pulls `main` on every run, so a developer cannot run their own `shell-config` clone as the login shell
- [ ] Scope: an installer and `ft host bootstrap` setting that points the host at a `shell-config` checkout (the Ansible variable `dev_container_fortress_shell_config_dir` exists, but nothing in `ft` exposes it), clones it beside the Dev Fortress checkout when missing, and stops updating a checkout the developer owns
- [ ] Acceptance: with developer mode on, a new login shell runs the sibling clone, a branch checked out there survives `ft host bootstrap localhost`, and `ft workspace` keeps mounting the same clone

### M5e-2 macOS host mode

- [ ] Problem: on macOS only `--mode cli` works; Homebrew, the container runtime, and the host roles are manual
- [ ] Scope: the installer's prerequisite step for macOS (Xcode Command Line Tools), Homebrew as the substrate, a container runtime decision (Docker Desktop, Colima, or OrbStack) with its tradeoffs recorded, and the host roles that apply on macOS
- [ ] Acceptance: one installer command converges a fresh macOS install, `ft host validate localhost` passes, and a workbench starts

### M5e-3 Shorten the developer path

- [ ] Problem: the developer path is a sequence of separate commands
- [ ] Scope: fold the second clone, `pre-commit install`, and the forge login prompt into the installer's developer mode, and decide whether a terminal font belongs in an opt-in option (the Homebrew cask works on Linux and macOS; WSL2 needs the font on Windows)
- [ ] Acceptance: the developer path in `DEVELOPMENT.md` is at most four commands from a fresh install to a workbench

## Verification Notes

- [ ] Bare-metal Ubuntu desktop, cold, timed
- [ ] The baseline run also checks the `M6b` read-through: no step sends the reader back to an earlier document
- [ ] Fresh macOS on Apple silicon, cold, timed
- [ ] WSL2 Ubuntu, as a regression check
- [ ] A `shell-config` branch lived in as the login shell for a day

## Branch and Merge Plan

- [x] Start after `M5c` merges
- [x] Branch from `main` as `feat/m0005e-developer-workstation`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Progress Notes

Drafted on 2026-11-20 from the operator's stated aim: the fewest commands from
a new Ubuntu or macOS install to a full DevOps development workstation, in
hours or less instead of days or weeks. The gaps came from walking the
developer path for a bare-metal Ubuntu run of the `M5c-7` workbench docs.

Activated on 2026-11-20 after `M5c` merged (#7). The first step is the cold,
timed bare-metal Ubuntu run of the current developer path, which measures the
baseline the issue drafts aim to shrink and closes the `M5c` workbench
acceptance that moved here.
