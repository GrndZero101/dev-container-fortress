# M1 SSH Target Foundation

## Status

- [x] Milestone complete

## Objective

Define a shared host target model and prove the first thin SSH-based control
plane.

## Exit Criteria

- [x] Named host target manifest exists
- [x] Managed SSH key paths are XDG-aligned
- [x] `ft host list`, `show`, `inventory`, `ssh-key`, `doctor`, and `bootstrap` exist
- [x] Generated Ansible inventory is driven from the shared target model

## Delivered Scope

- [x] Host target manifest model
- [x] Managed SSH key generation
- [x] Inventory rendering
- [x] Host doctor and probe support
- [x] Thin inventory-driven bootstrap path

## Issue Drafts

- [x] Model host targets in TOML
- [x] Add managed SSH key path and generation workflow
- [x] Generate inventory from host targets
- [x] Add host doctor and probe support
- [x] Add thin host bootstrap command

## Verification Notes

- [x] CLI behavior and edge cases were covered in tests
- [x] Shared SSH control-plane contract was established

