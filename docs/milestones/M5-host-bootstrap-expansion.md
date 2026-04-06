# M5 Host Bootstrap Expansion

## Status

- [ ] Milestone complete
- [x] Next candidate milestone

## Objective

Expand host provisioning from "reachable and inspectable" into a meaningful
host setup path.

## Exit Criteria

- [ ] Host playbook provisions a small but real baseline
- [ ] Shell-config bootstrap handoff is automated where intended
- [ ] Host-side prerequisite handling is clearer across Linux, macOS, and WSL
- [ ] Bootstrap assumptions and carve-outs are documented

## Non-Goals

- [ ] Full cross-platform parity in one pass
- [ ] Deep editor and tmux automation

## Issue Drafts

- [ ] Automate shell-config clone and bootstrap for supported host targets
- [ ] Add host-side `uv` bootstrap handling
- [ ] Define Linux-first versus cross-platform role boundaries
- [ ] Split platform-specific logic cleanly

## Verification Notes

- [ ] Re-run disposable Ubuntu loop
- [ ] Add at least one non-container host-planning check or dry-run path

