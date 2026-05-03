# M5 Host Bootstrap Expansion

## Status

- [x] Milestone complete
- [ ] Next candidate milestone

## Objective

Expand host provisioning from "reachable and inspectable" into a meaningful
host setup path.
That expansion should preserve the convergent desired-state model so an
existing aligned workstation and a fresh host can both be leveled toward the
same declared baseline.

The first M5 pass should intentionally validate `shell-config` on a minimally
prepared host before introducing Homebrew as the preferred steady-state package
substrate. That keeps bootstrap honest and flushes out shell-level assumptions
that would otherwise be masked by a richer userland toolchain.

## Exit Criteria

- [x] Host playbook provisions a small but real baseline
- [x] Shell-config installation and bootstrap are automated for supported host targets
- [x] Supported remote targets converge the default login shell to `zsh`
- [x] The fortress shell behaves honestly on a minimally prepared Ubuntu host
  that has only the native bootstrap prerequisites installed
- [x] Homebrew uplift is framed as a later steady-state tool preference rather
  than a hard prerequisite for first contact with the host
- [x] Host-side prerequisite handling is clearer across Linux, macOS, and WSL
- [x] Repeated runs safely level-set previously configured or manually aligned hosts
- [x] Managed state versus user-owned customization boundaries are documented clearly
- [x] Bootstrap assumptions and carve-outs are documented

## Non-Goals

- [ ] Full cross-platform parity in one pass
- [ ] Deep editor and tmux automation
- [ ] Treating host automation as a disposable one-shot installer only
- [ ] Requiring Homebrew before `shell-config` can be installed on a supported
  Linux host
- [ ] Folding the growing Python refactor into this delivery milestone instead
  of tracking it separately as maintainability work

## Issue Drafts

- [x] Automate shell-config clone and bootstrap for supported host targets
- [x] Install the fortress profile-local `zinit` layer during host bootstrap so the full dev-fortress profile behavior is present on supported hosts
- [x] Converge the default login shell to `zsh` for non-local targets so shell-config actually activates on login
- [x] Define and enforce the minimal native bootstrap prerequisites needed
  before shell-config installation
- [x] Dogfood the fortress profile on an Ubuntu host before Homebrew uplift and
  capture where the shell degrades or breaks with only standard tools present
- [x] Add Homebrew or Linuxbrew uplift after shell-config bootstrap so
  Brew-managed tools become the preferred steady-state path later
- [x] Add host-side `uv` bootstrap handling
- [x] Include operator and test-friendly baseline tools such as `gum` and `bats-core` in the host toolchain story
- [x] Define Linux-first versus cross-platform role boundaries
- [x] Split platform-specific logic cleanly
- [x] Define level-set behavior for existing hosts that are already mostly aligned

## Verification Notes

- [x] Re-run disposable Ubuntu loop
- [x] Verify shell-config bootstrap on a real Ubuntu host before Homebrew is installed
- [x] Verify reruns stay safe after Homebrew or Linuxbrew is added later
- [x] Add at least one non-container host-planning check or dry-run path

Validated outcome:

- [x] `uv run ft host bootstrap localhost --check -K` on a real Ubuntu WSL2 host
- [x] `uv run ft host bootstrap localhost -K` on a real Ubuntu WSL2 host
- [x] repeated `uv run ft host bootstrap localhost -K` settled to `changed=0`
- [x] `uv run ft host validate localhost -K` now enforces final convergence and passed on the real Ubuntu WSL2 host

Documented carve-out retained for this milestone:

- [x] `localhost` under WSL keeps manual login-shell switching via `chsh` or `usermod`
- [x] automatic login-shell convergence remains the default only for non-local SSH targets in this milestone

## Progress Notes

- [x] Added a dedicated `dev_fortress_shell_config_bootstrap` role that clones
  `shell-config`, runs `csm bootstrap`, and persists the selected profile using
  the target user's XDG state directory
- [x] Added a dedicated `dev_fortress_shell_config_zinit` role that installs
  the fortress profile-local `zinit` checkout without turning every bootstrap
  into an implicit update cycle
- [x] Kept the first M5 slice free of Homebrew so shell behavior can be
  validated against the minimal native bootstrap substrate first
- [x] Made the native bootstrap substrate explicit and enforced it before
  `shell-config` runs; current command contract is `python3`, `git`, `curl`,
  and `zsh`
- [x] Added the first Ubuntu-only Linuxbrew uplift slice after `shell-config`
  bootstrap, using the supported prefix and a broader fortress-facing formula
  set that now includes tools such as `atuin`, `starship`, `fzf`, `bat`,
  `eza`, `zoxide`, `direnv`, `uv`, and `tenv`
- [x] The `ft` Python surface is now large enough that a separate roadmap item
  should track post-M5 refactoring work rather than letting that debt hide
  inside ongoing milestone implementation
- [x] Verified the Ubuntu-first WSL2 local-host path on a real host instead of
  relying on container or remote-host inference
- [x] Tightened `ft host validate` so the final bootstrap pass must produce a
  parseable `PLAY RECAP` and settle to `changed=0`

## Captured Outcome

- Dev Fortress now has a verified Ubuntu-first WSL2 local bootstrap path using
  the shared `ft host ...` and Ansible workflow against `localhost`
- The host playbook now provides a real Linux baseline rather than only a thin
  reachability contract: XDG layout, native prerequisites, `shell-config`
  bootstrap, fortress profile-local `zinit`, readiness reporting, and Ubuntu
  Linuxbrew uplift
- Repeated local Ubuntu WSL2 bootstrap runs are proven convergent
- The remaining local-shell switch on WSL is documented as an intentional
  milestone carve-out rather than an ambiguous gap
