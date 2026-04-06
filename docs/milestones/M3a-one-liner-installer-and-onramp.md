# M3a One-Liner Installer and Onramp

## Status

- [ ] Milestone complete
- [x] Current active milestone

## Objective

Add a real one-liner install path and align the top-level onboarding docs with
it.

## Exit Criteria

- [ ] A repo-owned `install.sh` supports clone-and-bootstrap onboarding
- [ ] The installer is safe to run non-interactively on supported developer platforms
- [ ] `README.md` quickstart leads with the one-liner installer and a clone fallback
- [ ] `DEVELOPMENT.md` documents the installer, clone fallback, and expected prerequisites
- [ ] Shell syntax verification covers the new installer entrypoint

## Non-Goals

- [ ] Full workstation provisioning
- [ ] Curl-installed binary distribution of `ft`
- [ ] Platform-specific package-manager bootstrap beyond the current repo bootstrap

## Issue Drafts

### M3a-1 Add repo installer entrypoint

- [ ] Problem: the repo has `bootstrap.zsh`, but no true one-liner install entrypoint
- [ ] Scope: add a repo-owned installer that clones or refreshes the checkout and runs the bootstrap
- [ ] Acceptance: installer supports a default GitHub path and an override for repo/ref/destination
- [ ] Acceptance: installer fails clearly on missing prerequisites

### M3a-2 Align README onboarding

- [ ] Problem: README quickstart assumes the repo is already present locally
- [ ] Scope: update README to lead with the installer and a truthful clone fallback
- [ ] Acceptance: no machine-specific paths remain in quickstart
- [ ] Acceptance: top-level onboarding is honest about current capability

### M3a-3 Align development docs and verification

- [ ] Problem: development onboarding and bootstrap verification are no longer documented from the same entrypoint
- [ ] Scope: update development docs and add syntax verification for the new installer
- [ ] Acceptance: `DEVELOPMENT.md` matches the installer workflow
- [ ] Acceptance: `sh -n install.sh` passes

## Verification Notes

- [ ] `sh -n install.sh`
- [ ] `zsh -n bootstrap.zsh`
- [ ] README and development docs reviewed for generic paths and truthful onboarding

## Branch and Merge Plan

- [ ] Branch from `main` as `feat/m3a-installer-and-onramp`
- [ ] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once exit criteria are met
- [ ] Squash merge into `main`
