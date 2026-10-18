# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/ROADMAP.md`](docs/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/milestones/`](docs/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **Finish `M5a`:** rerun the EC2 loop from
   [`docs/ec2-development-loop.md`](docs/ec2-development-loop.md) alone, then
   tick the EC2 exit criterion and `M5a-6` in the
   [M5a file](docs/milestones/M5a-disposable-daily-driver-container.md).
2. **Merge `M5a`:** squash-merge `feat/m0005a-disposable-daily-driver-container`
   into `main` once its exit criteria are ticked.
3. **Start `M5b` Zero to Hero:** settle the open decisions in the
   [M5b file](docs/milestones/M5b-zero-to-hero-workstation-composability.md)
   (where tmux profiles live, the default tmux profile, and image pull versus
   local build for `workspace` mode), then begin with the `M5b-1` privilege
   spike.

## Parked

- Align the `tboss-workspace` devcontainers with the persisted state contract;
  tracked in that repo's `TODO.md`.
- Optional: turn off build-record artifacts in CI with
  `DOCKER_BUILD_RECORD_UPLOAD: false`.
