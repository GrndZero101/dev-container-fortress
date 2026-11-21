# Development Guide

This guide is for contributors to `dev-container-fortress`, `shell-config`, or
both. Installing and using Dev Fortress is covered by the
[quickstart](docs/quickstart.md) and the guides in the
[documentation map](README.md#documentation); this page adds only what a
contributor needs on top.

> [!NOTE]
> Use Dev Fortress to develop and validate Dev Fortress. Prefer `ft` and the
> documented loops over ad hoc commands, and treat a workflow that is still
> painful as a roadmap opportunity rather than a permanent workaround. `just`
> remains only as a thin shim over `ft`.

## :rocket: Zero to Hero: Developer Path

From a fresh Ubuntu install (bare metal, WSL2, or EC2) to a development
workstation plus a workbench for agentic development.

**1. Install the workstation.** Follow the [quickstart](docs/quickstart.md),
with two differences:

- start from the folder that holds your source trees, such as `~/src`, instead
  of `~`. The installer's checkout is a normal Git clone, and it is the one
  you develop in
- add `--options claude-code`

To install a branch that is not merged yet, add `--ref <branch>`; see
[Testing a branch](docs/quickstart.md#testing-a-branch).

**2. Clone `shell-config` beside it.**

```sh
cd ~/src
git clone https://github.com/GrndZero101/shell-config.git
```

**3. Developer setup.** Open a new terminal, which starts the managed zsh and
picks up the `docker` group, then:

```sh
cd ~/src/dev-container-fortress
uv run pre-commit install
ft identity --login github
```

Set the terminal font as
[quickstart step 5](docs/quickstart.md#abc-5-set-the-terminal-font-recommended)
describes.

**4. Agent workbench.** Compose a devcontainer holding the repos you want
agents to work on:

```sh
ft workbench init devops --profile ubuntu-full --options claude-code \
  --repo https://github.com/GrndZero101/dev-container-fortress.git \
  --repo https://github.com/GrndZero101/shell-config.git
ft workbench clone devops
code ~/workbenches/devops
```

Choose "Reopen in Container", or use terminal mode with
`devcontainer up --workspace-folder ~/workbenches/devops`. Inside, run
`ft identity --login github`, then `claude`. Details:
[workbench usage](docs/guides/workbench-usage.md).

> [!TIP]
> To run the workbench on an image built from your checkout rather than the
> published one, add `--local-build ~/src/dev-container-fortress` to
> `ft workbench init`, or set `local_build` in the workbench file later. See
> [Building the Image Locally](docs/guides/workbench-usage.md#building-the-image-locally).

The workbench holds its own clones under `repos/`, separate from `~/src`.
That is deliberate: an agent in the workbench reaches only `repos/`, never your
host checkouts. Use the `~/src` clones for the host-side loops below, such as
container builds, which need the host's Docker.

> [!IMPORTANT]
> Your login shell runs the installed `~/.config/shell-config`, not
> `~/src/shell-config`, and re-running the host bootstrap resets it to `main`.
> Do not edit it. Try `shell-config` changes in a container or workspace, which
> mount or stage the sibling clone; see
> [Shell-Config Changes](#shell-config-changes). Running the host shell from
> your clone is planned in
> [`M5e`](docs/project/milestones/M5e-developer-workstation.md).

## Development Layout

Keep both repos as sibling clones and treat them as the source of truth:

```text
~/src/
  dev-container-fortress/
  shell-config/
```

- `ft workspace ...` mounts a sibling `../shell-config` automatically
- `ft container build ... --shell-config-source local` stages from it
- the installed `${XDG_CONFIG_HOME:-$HOME/.config}/shell-config` is runtime
  state that the host bootstrap manages, not a place to edit

## Platforms

Ubuntu, on bare metal or WSL2, is the supported developer platform; the
developer path above covers it.

macOS supports only the installer's `cli` mode today, and macOS host mode is
planned in `M5e`. To contribute from macOS, install `git`, `rsync`, and Docker
Desktop (`brew install git rsync` and `brew install --cask docker`), confirm
`docker buildx version` works, then use the
[manual clone](docs/quickstart.md#manual-clone). That gives you `ft`, the
tests, and the container loops, without converging the Mac itself.

## Checks

Run these before pushing:

```zsh
uv run ruff check ft
uv run pytest ft/tests
uv run pre-commit run --all-files
```

`uv run pre-commit install` runs the hooks on every commit. They are:

- file hygiene: YAML and JSON syntax, merge markers, trailing whitespace, and
  final newlines
- `ruff` lint and format for Python
- `rumdl` for Markdown, configured in `pyproject.toml`. It also checks that
  relative links between documents resolve
- render checks, which fail when a generated file is out of date: the
  [`ft` CLI reference](docs/reference/cli.md), the `.devcontainer/`
  definitions, and the example workbench
- `ansible-playbook --syntax-check` and `ansible-lint` for `ansible/`
- `zsh -n`, `sh -n`, and `bash -n` syntax checks for the repo's shell
  entrypoints

### The CLI Reference

[`docs/reference/cli.md`](docs/reference/cli.md) is generated from the Typer
app, so the CLI documents itself: a command's docstring becomes its
description, and each `help=` string becomes the entry for that argument or
option. Never edit the file by hand. After changing a command, regenerate it:

```zsh
uv run typer ft.cli utils docs --name ft --title "ft CLI reference" \
  --output docs/reference/cli.md
```

The pre-commit hook does the same and fails when the committed copy is stale.
`ft/tests/test_cli_reference.py` fails when a command, argument, or option has
no help text.

### Continuous Integration

`.github/workflows/ci.yml` runs the same checks on every branch push:

1. `Lint and test`: the full pre-commit suite, `pytest ft/tests`, and
   `terraform fmt -check` plus `terraform validate` for every stack under `infra/`
2. `Build and smoke test`: builds each image in the matrix and runs its
   in-image smoke checks once the first job passes

Only pushes to `main` and `v*` tags publish images to GHCR. Feature branches
build and test without publishing. Pull requests from forks trigger the same
checks; same-repository pull requests reuse their branch push run.

Both jobs run on a pinned Ubuntu LTS runner (`ubuntu-26.04`), not
`ubuntu-latest`, so the runner OS only changes when the workflow is edited. When
a new Ubuntu LTS runner label is generally available, bump both `runs-on`
values together and let the branch CI run prove the move.

> [!NOTE]
> CI does not replace the local `ft` loops. It cannot run `ft host validate`
> or cloud-host checks, so keep running those locally for risky changes.

## Development Loops

The guides describe each surface; these are the loops a contributor repeats.

### Image and Container Changes

After changing a Dockerfile, shell startup, or tool installation, rebuild and
validate every target you touched:

```zsh
ft container refresh ubuntu
ft container validate ubuntu

ft container refresh alpine
ft container validate alpine

ft doctor
ft container status
```

Arch works the same way on amd64 hosts. `refresh` rebuilds the image and
replaces the container. For a closer look, `ft container enter <target>` opens
a shell; run `fortress-hud` there and confirm that:

- the active profile is `zsh-tll-citadel-dev-fortress`
- the prompt engine resolved as expected
- `starship`, `atuin`, `zoxide`, and `fzf` are available
- `${HOME}/.local/bin` is on `PATH`
- Ubuntu, Alpine, and Arch remain at parity unless a difference is intentional

The [container usage guide](docs/guides/container-usage.md) covers the rest of
the `ft container` loop, the disposable SSH targets, and corporate CA builds.

### Shell-Config Changes

Test `shell-config` changes from your sibling clone, never from the installed
checkout or a moving GitHub branch.

A workspace mounts the clone live, which is the quickest loop:

```zsh
ft workspace build ubuntu-full
ft workspace up ubuntu-full
ft workspace exec ubuntu-full -- zsh -lc 'test -d /workspace/shell-config && echo shell-config-mounted'
ft workspace enter ubuntu-full
```

To prove an image build with your changes, stage the clone into the build:

```zsh
ft container build ubuntu \
  --shell-config-source local \
  --shell-config-stage-from ../shell-config
```

[Shell-Config Source Modes](docs/guides/container-usage.md#shell-config-source-modes)
covers GitHub-backed builds and the `buildx` cache caveat that comes with
them. The [workspace usage guide](docs/guides/workspace-usage.md) covers the
workspace itself.

### Host Role Changes

Converge and validate `localhost`, or a disposable host, as the
[workstation usage guide](docs/guides/workstation-usage.md) and
[target validation runbook](docs/project/target-validation.md) describe:

```zsh
ft host bootstrap localhost --check -K
ft host validate localhost -K
```

### Machine-Readable Output

Agents and scripts should read structured results rather than tables:

```zsh
ft doctor --json
ft container validate --json ubuntu
```

## Completion

Bootstrap installs the `ft` zsh completion file to
`${XDG_DATA_HOME:-$HOME/.local/share}/dev-container-fortress/completions/zsh/_ft`.
After adding or renaming commands, refresh it and open a new shell:

```zsh
uv run ft completion install zsh
```

## Where to Look Next

- [Architecture](docs/design/architecture.md) for layering and tool selection
- [Container standards](docs/design/container-standards.md) for the image
  contract
- [Roadmap](docs/project/ROADMAP.md) and the
  [milestone workflow](docs/project/milestones/README.md) for planning
- [AGENTS.md](AGENTS.md) for coding and documentation conventions
