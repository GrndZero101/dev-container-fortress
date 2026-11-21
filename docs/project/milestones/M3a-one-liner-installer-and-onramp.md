# M3a One-Liner Installer and Onramp

## Status

- [x] Milestone complete
- [ ] Current active milestone

## Objective

Add a real one-liner install path and align the top-level onboarding docs with
it.

## Exit Criteria

- [x] A repo-owned `install.sh` supports clone-and-bootstrap onboarding
- [x] The installer is safe to run non-interactively on supported developer platforms
- [x] `README.md` quickstart leads with the one-liner installer and a clone fallback
- [x] `DEVELOPMENT.md` documents the installer, clone fallback, and expected prerequisites
- [x] Shell syntax verification covers the new installer entrypoint

## Non-Goals

- [ ] Full workstation provisioning
- [ ] Curl-installed binary distribution of `ft`
- [ ] Platform-specific package-manager bootstrap beyond the current repo bootstrap

## Issue Drafts

### M3a-1 Add repo installer entrypoint

- [x] Problem: the repo has `bootstrap.zsh`, but no true one-liner install entrypoint
- [x] Scope: add a repo-owned installer that clones or refreshes the checkout and runs the bootstrap
- [x] Acceptance: installer supports a default GitHub path and an override for repo/ref/destination
- [x] Acceptance: installer fails clearly on missing prerequisites

### M3a-2 Align README onboarding

- [x] Problem: README quickstart assumes the repo is already present locally
- [x] Scope: update README to lead with the installer and a truthful clone fallback
- [x] Acceptance: no machine-specific paths remain in quickstart
- [x] Acceptance: top-level onboarding is honest about current capability

### M3a-3 Align development docs and verification

- [x] Problem: development onboarding and bootstrap verification are no longer documented from the same entrypoint
- [x] Scope: update development docs and add syntax verification for the new installer
- [x] Acceptance: `DEVELOPMENT.md` matches the installer workflow
- [x] Acceptance: `sh -n install.sh` passes

## Verification Notes

- [x] `sh -n install.sh`
- [x] `zsh -n bootstrap.zsh`
- [x] README and development docs reviewed for generic paths and truthful onboarding

## Branch and Merge Plan

The installer landed directly on `main` in `1972f8a`. The syntax hook that
closes the last exit criterion landed with the 2026-10-17 roadmap sweep.

## Captured Outcome

Verified on 2026-10-17:

- `install.sh` is POSIX `sh`, never reads from the terminal, and supports
  `DEV_CONTAINER_FORTRESS_REPO`, `DEV_CONTAINER_FORTRESS_REF`, and
  `DEV_CONTAINER_FORTRESS_DIR` overrides
- run with stdin closed in a fresh container, it cloned `main`, ran
  `bootstrap.zsh`, and left a working `ft`, warning only that Docker was absent
- missing required commands fail with `Missing required command: <name>`
- `README.md` and `DEVELOPMENT.md` lead with the one-liner and a clone fallback,
  with no machine-specific paths
- the `sh syntax` pre-commit hook now checks `install.sh` locally and in CI
