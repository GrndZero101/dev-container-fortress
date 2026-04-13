# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

`dev-container-fortress` is a provisioning and packaging workspace for portable developer environments. It produces Docker images (Ubuntu and Alpine) usable as VS Code devcontainers, and provides `ft` — a CLI tool for managing tool installations, container targets, and SSH host targets.

## Common Commands

All commands should be run from the repo root. The project uses `uv` as the package/environment manager (Python 3.14 required).

**Run all tests:**
```zsh
uv run pytest
```

**Run a single test file:**
```zsh
uv run pytest ft/tests/test_manifest.py
```

**Run a single test by name:**
```zsh
uv run pytest ft/tests/test_manifest.py::test_load_manifest_reads_multiple_tool_definitions
```

**Lint:**
```zsh
uv run ruff check ft/
```

**Format check:**
```zsh
uv run ruff format --check ft/
```

**Run the `ft` CLI locally:**
```zsh
uv run --project ./ft ft <subcommand>
```

**Build container images:**
```zsh
docker buildx build --load -f containers/ubuntu/Dockerfile -t dev-container-fortress:ubuntu-test .
docker buildx build --load -f containers/alpine/Dockerfile -t dev-container-fortress:alpine-test .
```

**Container lifecycle via `just` (wraps `ft container ...`):**
```zsh
just test-build [ubuntu|alpine]
just test-up [ubuntu|alpine]
just test-validate [ubuntu|alpine]
just test-down [ubuntu|alpine]
just test-reset [ubuntu|alpine]
just test-exec ubuntu <cmd>
just test-shell ubuntu
just test-ssh-key ubuntu
just test-ssh-probe ubuntu
```

## Architecture

### Repository Layout

- `ft/` — the `ft` Python package (uv workspace member). This is where almost all active development happens.
  - `ft/src/ft/` — source code
  - `ft/tests/` — pytest tests
  - `ft/tools/tools.toml` — the canonical tool manifest consumed at runtime
  - `ft/targets/hosts.example.toml` — example host-target config
- `containers/` — Dockerfiles and shared bootstrap scripts for Ubuntu and Alpine targets
- `.devcontainer/` — thin VS Code devcontainer wrappers over the Dockerfiles
- `docs/` — design contracts and usage documentation
- `brew/` — Brewfile variants for host workstation setup (macOS, WSL, Linux)
- `scripts/` — helper scripts (`test-container.zsh`, `stage-shell-config.zsh`)
- `justfile` — task runner front door for container development workflows

### `ft` Package Architecture

The `ft` CLI (Typer-based) has four command groups: `tool`, `container`, `host`, `completion`.

**Data flow for tool installation:**
1. `ft/tools/tools.toml` defines tools as TOML — loaded by `manifest.py` → validated into `models.py` Pydantic models
2. `installer.py` resolves the manifest into a concrete `InstallPlan` (templating URL/filename fields, selecting the right OS/arch/target asset)
3. `installer.py` downloads, verifies checksums, extracts archives, and places binaries under `install_root`

**Key models (`models.py`):**
- `ToolManifest` → `dict[str, ToolDefinition]`
- `ToolDefinition` → `list[ToolAsset]` + `IntegrityConfig`
- `ToolAsset` has `os`, `arch`, optional `target` (for distro-specific assets like Ubuntu vs Alpine musl/gnu), and either `url` or `url_template`
- `HostTargetManifest` / `HostTargetDefinition` — models SSH and local host targets

**Settings (`settings.py`):** `FtSettings` (pydantic-settings) reads from `FT_*` environment variables. Defaults: manifest at `ft/tools/tools.toml`, target `ubuntu`.

**Platform detection (`platforms.py`):** normalizes `platform.machine()` → `amd64`/`arm64` and `platform.system()` → `linux`/`darwin`.

### Manifest Design

`ft/tools/tools.toml` is config-driven. Tools declare `url_template` fields with `{version}`, `{os}`, `{arch}`, `{filename}` placeholders. Asset `target` field enables Ubuntu/Alpine divergence (e.g., `atuin` uses `gnu` for Ubuntu and `musl` for Alpine). Prefer extending the manifest over adding installer-specific code. See `ft/tools/README.md` for the full field reference.

### Container Design

Both Dockerfiles follow the same contract (see `docs/container-standards.md`):
- Build-time `uv` from Astral's distroless image; runtime `uv` from Astral's shell installer
- Non-root `vscode` runtime user with `sudo`
- XDG-style layout: `$HOME/.local/bin`, `$XDG_DATA_HOME`, `$XDG_CONFIG_HOME`, `$XDG_STATE_HOME`
- `ft` installed as `uv tool install`; tools installed via `ft tool install`
- Optional corporate CA via `CORPORATE_CA_CERT_DIR` build arg (opt-in only)
- Optional local `shell-config` source via `SHELL_CONFIG_SOURCE=local` build arg

Host config lives at `${XDG_CONFIG_HOME}/dev-container-fortress/hosts.toml` (copy from `ft/targets/hosts.example.toml`).

### Ansible Layer

`ansible/` contains the host bootstrap automation. It is intentionally thin for now — the playbook (`ansible/playbooks/host.yml`) proves reachability, validates the target contract, ensures XDG directories exist, and reports tool readiness. Real roles live under `ansible/roles/` (currently scaffolded; M4 work converts this to real role files).

`ft host bootstrap <target>` renders a temporary Ansible inventory via `ft host inventory` and runs the playbook over it. The inventory is generated from the host-target model, not written by hand.

**End-to-end SSH bootstrap sequence for a disposable Ubuntu target:**
```zsh
uv run --project ./ft ft host ssh-key dev-fortress-ubuntu       # generate managed key
uv run --project ./ft ft container up ubuntu                    # start container (mounts key)
uv run --project ./ft ft host doctor dev-fortress-ubuntu --probe  # verify SSH reachability
uv run --project ./ft ft host ssh-key-enroll dev-fortress-ubuntu  # authorize key in container
uv run --project ./ft ft host bootstrap dev-fortress-ubuntu --check  # Ansible check mode
```

## Planning and Workflow

This project uses milestone-based squash merges. Strategy lives in `docs/ROADMAP.md`; execution detail lives in `docs/milestones/<milestone>.md`.

**Current milestone status (as of initial CLAUDE.md creation):**
- `now`: M3a — one-liner installer and onramp (`feat/m0003a-installer-and-onramp`)
- `next`: M4 (first real Ansible roles), M5 (host bootstrap expansion), M6 (CLI maturity), M7 (local verification workflow), M7a (secrets management)

**Branch naming:** `feat/<sortable-id>-<short-name>` where milestone IDs are zero-padded (e.g., `M3a` → `m0003a`, `M4` → `m0004`).

**Merge policy:** squash merge into `main` once a milestone's exit criteria are met. Commit freely at verified checkpoints on the feature branch.

**"Done" means:** code, docs, and live verification move together. A milestone is not done until all three are complete.

## Design Principles

These come from the roadmap and should guide implementation decisions:

- `ft` is the operator surface — keep logic in `ft`, not in `just` or shell scripts
- Prefer config-driven manifests over installer-specific code
- Shell behavior belongs in `shell-config` (a separate repo); this repo wires it in
- `ansible/` installs and wires components; component repos own their own behavior
- Prove transport and bootstrap paths before deepening workstation automation
- Keep "done" meaningful — operational truth belongs in README and usage docs once work is implemented
