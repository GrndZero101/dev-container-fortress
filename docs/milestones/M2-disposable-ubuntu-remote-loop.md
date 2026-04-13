# M2 Disposable Ubuntu Remote Loop

## Status

- [x] Milestone complete

## Objective

Prove one real end-to-end remote path against a disposable Ubuntu SSH target.

## Exit Criteria

- [x] Ubuntu disposable target starts an SSH daemon
- [x] Managed public key can be authorized for the disposable target
- [x] SSH probe succeeds against the live disposable target
- [x] `ft host bootstrap --check` succeeds against that target

## Delivered Scope

- [x] SSH-enabled Ubuntu disposable target
- [x] Managed public-key enrollment support
- [x] Managed known-hosts path for disposable targets
- [x] Live Docker, SSH, and Ansible verification loop

## Issue Drafts

- [x] Add SSH-capable Ubuntu disposable target behavior
- [x] Add public-key enrollment command and workflow
- [x] Add managed known-hosts support for disposable targets
- [x] Prove live Ubuntu bootstrap check loop

## Verification Notes

- [x] Live Docker build completed
- [x] Live SSH probe completed
- [x] Live `ft host bootstrap --check` completed
