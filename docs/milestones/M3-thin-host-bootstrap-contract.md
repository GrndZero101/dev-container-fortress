# M3 Thin Host Bootstrap Contract

## Status

- [x] Milestone complete

## Objective

Replace fake workstation-role assumptions with a real thin bootstrap contract.

## Exit Criteria

- [x] Host playbook no longer references missing roles
- [x] Bootstrap proves reachability and target metadata cleanly
- [x] Target user XDG directory preparation is explicit
- [x] Readiness reporting is useful for humans and agents

## Delivered Scope

- [x] Task-based thin host bootstrap playbook
- [x] Shell-config presence checks
- [x] Baseline tool checks
- [x] Docs aligned with real thin-bootstrap behavior

## Issue Drafts

- [x] Replace missing-role references with truthful tasks
- [x] Add reachability and metadata checks
- [x] Make XDG directory preparation explicit
- [x] Improve bootstrap readiness reporting

## Verification Notes

- [x] Disposable Ubuntu target remained usable
- [x] Bootstrap check mode became truthful and runnable
