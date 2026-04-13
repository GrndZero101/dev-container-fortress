# M5 Host Bootstrap Expansion

## Status

- [ ] Milestone complete
- [x] Next candidate milestone

## Objective

Expand host provisioning from "reachable and inspectable" into a meaningful
host setup path.
That expansion should preserve the convergent desired-state model so an
existing aligned workstation and a fresh host can both be leveled toward the
same declared baseline.

## Exit Criteria

- [ ] Host playbook provisions a small but real baseline
- [ ] Shell-config bootstrap handoff is automated where intended
- [ ] Host-side prerequisite handling is clearer across Linux, macOS, and WSL
- [ ] Repeated runs safely level-set previously configured or manually aligned hosts
- [ ] Managed state versus user-owned customization boundaries are documented clearly
- [ ] Bootstrap assumptions and carve-outs are documented

## Non-Goals

- [ ] Full cross-platform parity in one pass
- [ ] Deep editor and tmux automation
- [ ] Treating host automation as a disposable one-shot installer only

## Issue Drafts

- [ ] Automate shell-config clone and bootstrap for supported host targets
- [ ] Add host-side `uv` bootstrap handling
- [ ] Include operator and test-friendly baseline tools such as `gum` and `bats-core` in the host toolchain story
- [ ] Define Linux-first versus cross-platform role boundaries
- [ ] Split platform-specific logic cleanly
- [ ] Define level-set behavior for existing hosts that are already mostly aligned

## Verification Notes

- [ ] Re-run disposable Ubuntu loop
- [ ] Add at least one non-container host-planning check or dry-run path
