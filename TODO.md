# Plan board — dev-container-fortress

> 54 tasks · 2 done · 0 doing · 18 blocked

## M-0001 M6b: Documentation consolidation (1/1) — done

- [x] T-0001 Add a paragraph and an example to the main ft command docstrings — done 2026-11-21, 4a6bc18
- [x] ~~T-0002 Operator: cold timed bare-metal Ubuntu baseline run (M5e baseline and M6b read-through)~~ — cancelled

## M-0002 M5f: Agent workbench guardrails (0/8)

- [ ] T-0003 M5f-1a: Enforce workbench filesystem guardrails in the renderer and --check
- [ ] T-0004 M5f-1b: URL-only validation in ft.browser_bridge, then the bridge in the devcontainers for CLI terminal mode
- [ ] T-0005 M5f-1c: SSH through a forwarded agent in VS Code and CLI terminal mode, with SSH commit signing — waiting on T-0003
- [ ] T-0006 M5f-1d: op through a service-account token and a non-production default AWS_PROFILE in workbenches — waiting on T-0003
- [ ] T-0007 M5f-1e: Record what a full workbench protects in the container standards and architecture docs — waiting on T-0003, T-0005, T-0006
- [ ] T-0008 M5f-2: Claude Code bypass mode by default in workbenches, with a PreToolUse deny-list hook — waiting on T-0003
- [ ] T-0009 Decide: does a workbench need Docker inside it (Docker-in-Docker, rootless, or Sysbox)? — blocked: Operator decision: record the choice with tp note, then close or unblock.
- [ ] T-0010 Operator: in-workbench agent checks and a multi-hour bypass-mode Claude Code task delivered as a PR — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.

## M-0003 M5e: Zero to Hero developer workstation (0/5)

- [ ] T-0011 M5e-1: Developer mode for shell-config — waiting on T-0002
- [ ] T-0012 M5e-2: macOS host mode in the installer — waiting on T-0002
- [ ] T-0013 M5e-3: Shorten the developer path to at most four commands — waiting on T-0011
- [ ] T-0014 Operator: M5e closing runs (bare-metal Ubuntu and Apple silicon macOS cold and timed, WSL2 regression, shell-config branch lived in for a day) — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- [ ] T-0043 Operator: cold timed bare-metal Ubuntu baseline run (M5e baseline and docs read-through) — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.

## M-0004 M6: Operator CLI maturity (0/4)

- [ ] T-0015 Refine `ft doctor --json` into a typed, tested shape
- [ ] T-0016 Refine `ft container validate --json` into a typed, tested shape
- [ ] T-0017 Migrate remaining justfile helper behavior into ft
- [ ] T-0018 Operator: review ft command help text and target semantics — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.

## M-0005 M6a: Python maintainability refactor (0/1)

- [ ] T-0019 Slice M6a into tasks (module boundaries, port order, template adoption)

## M-0006 M7: Local verification workflow (0/3)

- [ ] T-0020 Decide whether a dedicated `ft verify` surface is warranted — blocked: Operator decision: record the choice with tp note, then close or unblock.
- [ ] T-0021 Add a milestone-level verification recipe or command — waiting on T-0020
- [ ] T-0022 Unify just recipes around the intended ft paths — waiting on T-0020

## M-0007 M7a: Secrets management (0/3)

- [ ] T-0023 M7a-3: Define the op CLI integration contract
- [ ] T-0024 M7a-4: Document recovery and hardware-token considerations
- [ ] T-0025 M7a-5: Add the secure backup and restore baseline (rustic expected)

## M-0008 M5d: Sealed agent workbench (0/4)

- [ ] T-0026 M5d-1: Sealed definition and boundary contract — blocked: Gated by the roadmap: build M5d only when a concrete job needs a sealed workbench. Operator unblocks.
- [ ] T-0027 M5d-2: Egress allowlist — waiting on T-0026
- [ ] T-0028 M5d-3: `ft workbench doctor` boundary check and VS Code host-channel audit — waiting on T-0026
- [ ] T-0029 Operator: red-team checks from inside a sealed workbench, and a real bypass-mode task on untrusted input delivered as a PR — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.

## M-0009 M8: Shell UX polish (0/1)

- [ ] T-0030 Operator: scope M8 (pick candidate areas, decide what belongs in shell-config, add tasks) — blocked: Operator decision: record the choice with tp note, then close or unblock.

## M-0010 M9: Host and cloud targets (0/1)

- [ ] T-0031 Operator: re-scope M9 against what M4a and M7b already delivered, then add tasks — blocked: Operator decision: record the choice with tp note, then close or unblock.

## M-0011 Backlog: parked items, v0.1.0 follow-ups, and carry-overs from merged milestones (0/11)

- [ ] T-0032 Bump .python-version to 3.15 once an ansible-core release supports it — blocked: Waiting on an ansible-core release that supports Python 3.15 (2.21.5 crashes: dataclasses has no _is_type).
- [ ] T-0033 Find what wipes WSLInterop when a sibling WSL2 distro shuts down, and consider a self-heal timer — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- [ ] T-0034 Decide Alpine's long-term future (retire, slim to apk, or keep both toolchains) — blocked: Operator decision: record the choice with tp note, then close or unblock.
- [ ] T-0035 Turn off build-record artifacts in CI
- [ ] T-0036 Documentation site at v0.1.0: Zensical over docs/, published to GitHub Pages from CI — blocked: Scheduled with the v0.1.0 release; operator unblocks when the release starts.
- [ ] T-0037 Revise the superseded release plan (docs/project/initial-release-and-ghcr-images.md) for v0.1.0 — blocked: Operator decision: record the choice with tp note, then close or unblock.
- [ ] T-0038 Carry-over M5c: build the images for arm64 as well as amd64
- [ ] T-0039 Operator carry-over M5c: use devcontainer CLI terminal mode for a real change and push it — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- [ ] T-0040 Operator carry-over M5c: replace a container after an ad hoc `brew install` and confirm it behaves as documented — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- [ ] T-0041 Operator carry-over M5c-7: archive tboss-workspace with a pointer and close the M5a note about its persisted state — blocked: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- [ ] T-0042 Carry-over M5b: add a stock ubuntu:26.04 container CI check of the installer prerequisites

## Blockers

- T-0009: Operator decision: record the choice with tp note, then close or unblock.
- T-0010: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0014: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0018: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0020: Operator decision: record the choice with tp note, then close or unblock.
- T-0026: Gated by the roadmap: build M5d only when a concrete job needs a sealed workbench. Operator unblocks.
- T-0029: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0030: Operator decision: record the choice with tp note, then close or unblock.
- T-0031: Operator decision: record the choice with tp note, then close or unblock.
- T-0032: Waiting on an ansible-core release that supports Python 3.15 (2.21.5 crashes: dataclasses has no _is_type).
- T-0033: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0034: Operator decision: record the choice with tp note, then close or unblock.
- T-0036: Scheduled with the v0.1.0 release; operator unblocks when the release starts.
- T-0037: Operator decision: record the choice with tp note, then close or unblock.
- T-0039: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0040: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0041: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
- T-0043: Operator task: needs a person and hardware or accounts an agent session does not have. Unblock and start it when you run it; record results with tp note.
