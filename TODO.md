# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/ROADMAP.md`](docs/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/milestones/`](docs/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **`M5c-7`:** the generic workbench that replaces `tboss-workspace`, built on
   the `ft devcontainer render` renderer; see the
   [M5c file](docs/milestones/M5c-composable-container-workspaces.md).
2. **`M5c-8`:** workbench filesystem guardrails and the SSH and 1Password
   credential model; see the
   [M5c file](docs/milestones/M5c-composable-container-workspaces.md).
3. **`M5c-9`:** Claude Code bypass mode with a deny-list hook in workbenches;
   see the [M5c file](docs/milestones/M5c-composable-container-workspaces.md).

## Parked

- Bump `.python-version` to 3.15 once an `ansible-core` release supports it;
  2.21.5 crashes on 3.15 (`dataclasses` has no `_is_type`).
- Find what wipes `WSLInterop` when a sibling WSL2 distro shuts down (it now
  reproduces with a fresh store distro), and consider a self-heal timer;
  `wsl-restore-interop` restores it meanwhile.
- Decide Alpine's long-term future: it is the only consumer of the `ft install`
  downloader (`installer.py`, `tools.toml`). Retire it, slim it to `apk`
  without `tenv`, `glow`, and `oh-my-posh`, or keep both toolchains; see the
  [M5c file](docs/milestones/M5c-composable-container-workspaces.md).
- Optional: turn off build-record artifacts in CI with
  `DOCKER_BUILD_RECORD_UPLOAD: false`.
