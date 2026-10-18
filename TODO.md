# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/ROADMAP.md`](docs/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/milestones/`](docs/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **`M5b`:** pick up from the "Resume Here" section of the
   [M5b file](docs/milestones/M5b-zero-to-hero-workstation-composability.md);
   next is the quickstart (`M5b-8`), then the PR; the brownfield and
   `tmux-full` runs passed.
2. **Parallel EC2 test hosts:** verification now runs on the `dev-fortress`
   host (brownfield) and disposable EC2. Give each `ft` disposable-Ubuntu host
   name its own Terraform workspace so several cheap hosts can run and tear
   down independently; today a second name replaces the first host.
3. **Then `M5c`:** Homebrew in the containers, Claude Code everywhere, and
   the devcontainer and CLI terminal-mode flows; see the
   [M5c file](docs/milestones/M5c-composable-container-workspaces.md).

## Parked

- Bump `.python-version` to 3.15 once an `ansible-core` release supports it;
  2.21.5 crashes on 3.15 (`dataclasses` has no `_is_type`).
- Find what wipes `WSLInterop` when a sibling WSL2 distro shuts down (it now
  reproduces with a fresh store distro), and consider a self-heal timer;
  `wsl-restore-interop` restores it meanwhile.
- Align the `tboss-workspace` devcontainers with the persisted state contract;
  tracked in that repo's `TODO.md`.
- Optional: turn off build-record artifacts in CI with
  `DOCKER_BUILD_RECORD_UPLOAD: false`.
