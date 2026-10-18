# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/ROADMAP.md`](docs/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/milestones/`](docs/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **`M5b`:** pick up from the "Resume Here" section of the
   [M5b file](docs/milestones/M5b-zero-to-hero-workstation-composability.md);
   the quickstart (`M5b-8`) is done, and the PR is open
   ([#5](https://github.com/GrndZero101/dev-container-fortress/pull/5)); next
   is the green CI and the operator's squash merge.
2. **Then `M7b`:** a five-host EC2 test fleet (Ubuntu 24.04, 26.04, 26.10,
   Arch, Alpine) with one apply and one destroy; see the
   [M7b file](docs/milestones/M7b-cloud-test-fleet.md).
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
