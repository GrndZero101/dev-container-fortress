# M7a Secrets Management

## Status

- [ ] Milestone complete
- [x] Next candidate milestone

## Objective

Establish a real secrets-management baseline suitable for daily-driver operator
workflows across both persistent and ephemeral environments.

## Exit Criteria

- [ ] GPG setup and key-management workflow is documented for local use
- [ ] Backup, restore, transfer, and offline key-handling guidance exists
- [ ] `pass` or `gopass` setup is documented and integrated with the chosen GPG workflow
- [ ] `op` CLI integration expectations are documented and wired where appropriate
- [ ] Secure backup and restore guidance exists for secret material across multiple environments
- [ ] The secrets workflow includes an explicit restore story for fresh or disposable environments
- [ ] The supported secrets-management baseline is explicit in operator docs

## Non-Goals

- [ ] Enterprise vault orchestration beyond local operator workflows
- [ ] Fully automated hardware-token provisioning
- [ ] Cross-platform parity in the first pass
- [ ] Picking every secret-related tool in the first pass if one baseline path is enough

## Issue Drafts

### M7a-1 Define the GPG key lifecycle

- [ ] Problem: there is no standardized key-management story for daily-driver use
- [ ] Scope: define generation, backup, restore, transfer, subkeys, and offline handling expectations
- [ ] Acceptance: the local GPG lifecycle is documented clearly enough for operator setup

### M7a-2 Add password-store baseline

- [ ] Problem: there is no chosen password-store workflow for the fortress environment
- [ ] Scope: define and document `pass` or `gopass` setup with the chosen GPG key flow
- [ ] Acceptance: the baseline password-store path is explicit and repeatable

### M7a-3 Add OP CLI integration contract

- [ ] Problem: 1Password CLI integration is desirable but not yet scoped
- [ ] Scope: define how `op` fits into the local operator workflow and what Dev Fortress should wire automatically
- [ ] Acceptance: operator expectations and setup steps are documented

### M7a-4 Document recovery and hardware-token considerations

- [ ] Problem: secrets workflows are not daily-driver safe without recovery guidance
- [ ] Scope: document offline backup, restore, transfer, and YubiKey-adjacent considerations
- [ ] Acceptance: docs cover recovery and hardware-token expectations truthfully

### M7a-5 Add secure backup and restore baseline

- [ ] Problem: secret material needs an encrypted backup and restore story across machines and disposable environments
- [ ] Scope: define the baseline backup tool and workflow, with `rustic` as an expected candidate
- [ ] Acceptance: the backup and restore workflow is explicit, encrypted, and repeatable

### M7a-6 Document ephemeral-environment restore workflow

- [ ] Problem: daily-driver use requires restoring secrets into fresh or disposable environments without guesswork
- [ ] Scope: document how the secrets baseline is restored into containers, new hosts, or rebuilt workstations
- [ ] Acceptance: the ephemeral restore path is documented clearly enough for repeat use

## Verification Notes

- [ ] Supported local secrets workflow can be followed from docs without tribal knowledge
- [ ] Backup and restore flow is explicit for both persistent and ephemeral environments
- [ ] Secrets tooling expectations are aligned across README, workstation docs, and roadmap

## Branch and Merge Plan

- [ ] Branch from `main` as `feat/m7a-secrets-management`
- [ ] Commit freely at verified checkpoints
- [ ] Open one PR for the milestone once exit criteria are met
- [ ] Squash merge into `main`
