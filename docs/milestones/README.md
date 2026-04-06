# Milestone Drafts

This directory is the working planning surface for Dev Fortress milestones.

Use these files as:

- the in-repo source of truth for the active milestone draft
- a checkbox-driven execution list during implementation
- a copy/paste source when opening GitHub milestones and issues later

Recommended workflow:

1. Keep strategy and milestone ordering in [`docs/ROADMAP.md`](/home/timl/projects/tboss/dev-container-fortress/docs/ROADMAP.md).
2. Keep one markdown file here for each milestone.
3. Use markdown checkboxes in the milestone file while work is in flight.
4. Work on a milestone branch such as `feat/m4-first-real-host-roles`.
5. Commit freely at verified checkpoints.
6. When the milestone is stable, open the matching GitHub milestone and issues from the markdown draft.
7. Squash-merge the milestone branch once exit criteria are met.

Branch naming convention:

- milestone PR branch: `feat/<sortable-milestone-id>-<short-name>`
- doc-focused milestone branch: `docs/<sortable-milestone-id>-<short-name>`
- temp reframe branch: `<final-branch>--wip-YYYYMMDD-HHMM`

Examples:

- `feat/m0003a-installer-onramp`
- `feat/m0004-first-real-host-roles`
- `docs/m0007a-secrets-management`

Sortable milestone ID mapping:

- `M3a` -> `m0003a`
- `M4` -> `m0004`
- `M7a` -> `m0007a`

Each milestone file should contain:

- objective
- exit criteria
- non-goals
- issue drafts
- verification notes
- branch and merge guidance
