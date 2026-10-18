# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/ROADMAP.md`](docs/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/milestones/`](docs/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **Merge `M5a`:** open the PR for
   `feat/m0005a-disposable-daily-driver-container` and squash-merge it into
   `main`; the exit criteria in the
   [M5a file](docs/milestones/M5a-disposable-daily-driver-container.md) are ticked.
2. **Start `M5b` Zero to Hero:** settle the open decisions in the
   [M5b file](docs/milestones/M5b-zero-to-hero-workstation-composability.md)
   (where tmux profiles live, the default tmux profile, and image pull versus
   local build for `workspace` mode), then begin with the `M5b-1` privilege
   spike.
3. **Then `M5c`:** Homebrew in the containers, Claude Code everywhere, and
   the devcontainer and CLI terminal-mode flows; see the
   [M5c file](docs/milestones/M5c-composable-container-workspaces.md).

## Parked

- Align the `tboss-workspace` devcontainers with the persisted state contract;
  tracked in that repo's `TODO.md`.
- Optional: turn off build-record artifacts in CI with
  `DOCKER_BUILD_RECORD_UPLOAD: false`.
