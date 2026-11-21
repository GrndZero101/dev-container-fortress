# TODO

The short "what to do next" queue. Strategy and milestone order live in
[`docs/project/ROADMAP.md`](docs/project/ROADMAP.md); scope, issue drafts, and progress live in
the milestone files under [`docs/project/milestones/`](docs/project/milestones/). Keep each
item here to one line plus a link, and delete it once the milestone file
records the result.

## Up Next

1. **`M5e` baseline run:** on a fresh bare-metal Ubuntu install, follow the
   [developer path](DEVELOPMENT.md#rocket-zero-to-hero-developer-path) from the
   top, timing each step, through a workbench opened in VS Code with a login
   and push from inside. Record the times and every snag in the
   [M5e file](docs/project/milestones/M5e-developer-workstation.md). Wait for the
   `main` CI run from the `M5c` merge to publish the images first.
2. **`M5f`:** workbench guardrails and credentials, then Claude Code bypass
   mode; see the [M5f file](docs/project/milestones/M5f-agent-workbench-guardrails.md).
3. **`M5e`:** developer mode for `shell-config`, macOS host mode, and a
   shorter developer path, shaped by the baseline run.
4. **`M6b`:** finish the documentation consolidation: richer command
   docstrings for the generated CLI reference, and a fresh-host read-through;
   see the [M6b file](docs/project/milestones/M6b-documentation-consolidation.md).

## Parked

- Bump `.python-version` to 3.15 once an `ansible-core` release supports it;
  2.21.5 crashes on 3.15 (`dataclasses` has no `_is_type`).
- Find what wipes `WSLInterop` when a sibling WSL2 distro shuts down (it now
  reproduces with a fresh store distro), and consider a self-heal timer;
  `wsl-restore-interop` restores it meanwhile.
- Decide Alpine's long-term future: it is the only consumer of the `ft install`
  downloader (`installer.py`, `tools.toml`). Retire it, slim it to `apk`
  without `tenv`, `glow`, and `oh-my-posh`, or keep both toolchains; see the
  [M5c file](docs/project/milestones/M5c-composable-container-workspaces.md).
- Optional: turn off build-record artifacts in CI with
  `DOCKER_BUILD_RECORD_UPLOAD: false`.
