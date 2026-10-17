# Initial Release and GHCR Image Publishing Plan

This note captures the intended direction for getting `dev-container-fortress`
to an initial public release and making it usable as the base image for
multi-repo VS Code workspaces.

## Goal

Publish reusable Ubuntu, Ubuntu daily-driver, and Alpine Dev Fortress container
images that can be consumed by a separate workspace/orchestration repository.

The immediate target is a `v0.1.0` release that proves:

- Ubuntu, Ubuntu daily-driver, and Alpine images build repeatably
- the images contain the expected developer toolchain
- the images are published to GitHub Container Registry
- a parent workspace repository can use one image as its devcontainer
- docs explain both local development and external consumption

## Intended Consumer Model

The preferred workflow is to keep `dev-container-fortress` as the toolchain
image project, then use a separate workspace repo for multi-repo development.

Example workspace repo:

```text
tboss-workspace/
  .git/
  .devcontainer/
    devcontainer.json
    local-build/
      devcontainer.json
  tboss.code-workspace
  repos/
    .gitkeep
    dev-container-fortress/
    shell-config/
    minecraft-docker/
```

The parent workspace repo should ignore child repositories:

```gitignore
/repos/*
!/repos/.gitkeep
```

The workspace file should reference the child repos explicitly:

```json
{
  "folders": [
    { "path": "repos/dev-container-fortress" },
    { "path": "repos/shell-config" },
    { "path": "repos/minecraft-docker" }
  ]
}
```

The parent workspace devcontainer should usually consume the published
daily-driver image:

```json
{
  "name": "tboss workspace",
  "image": "ghcr.io/grndzero101/dev-container-fortress:ubuntu-full",
  "remoteUser": "vscode",
  "workspaceFolder": "/workspaces/tboss-workspace",
  "customizations": {
    "vscode": {
      "settings": {
        "terminal.integrated.defaultProfile.linux": "zsh"
      },
      "extensions": [
        "ms-python.python",
        "ms-azuretools.vscode-docker",
        "hashicorp.terraform",
        "tamasfe.even-better-toml"
      ]
    }
  }
}
```

## Orchestrator Workspace Repo

Create a separate thin orchestrator repo, likely named `tboss-workspace`, that
owns the devcontainer scaffolding for day-to-day multi-repo development.

This repo should not build or own the toolchain. It should consume the published
Dev Fortress image and provide the VS Code workspace shape around independently
cloned child repositories.

Responsibilities:

- define `.devcontainer/devcontainer.json`
- define `tboss.code-workspace`
- provide a stable `repos/` parent for child Git checkouts
- ignore child repo contents by default
- document how to clone additional projects under `repos/`
- optionally include helper scripts or tasks for common clone/open workflows

Initial scaffold:

```text
tboss-workspace/
  .git/
  .devcontainer/
    devcontainer.json
  repos/
    .gitkeep
  tboss.code-workspace
  README.md
```

The orchestrator should support this expansion without committing child repos:

```text
tboss-workspace/
  repos/
    dev-container-fortress/
    shell-config/
    minecraft-docker/
    other-projects/
```

The default `.devcontainer/devcontainer.json` should consume the published
Ubuntu daily-driver image:

```json
{
  "name": "tboss workspace",
  "image": "ghcr.io/grndzero101/dev-container-fortress:ubuntu-full",
  "remoteUser": "vscode",
  "workspaceFolder": "/workspaces/tboss-workspace",
  "customizations": {
    "vscode": {
      "settings": {
        "terminal.integrated.defaultProfile.linux": "zsh"
      },
      "extensions": [
        "ms-python.python",
        "ms-azuretools.vscode-docker",
        "hashicorp.terraform",
        "tamasfe.even-better-toml"
      ]
    }
  }
}
```

`dev-container-fortress` remains responsible for building and publishing the
image. The orchestrator repo remains responsible for composing project
checkouts into one usable development surface.

Use a local build only when actively changing `dev-container-fortress` itself:

```json
{
  "name": "tboss workspace",
  "build": {
    "dockerfile": "../repos/dev-container-fortress/containers/ubuntu/Dockerfile",
    "context": "../repos/dev-container-fortress",
    "args": {
      "WORKSPACE_TOOL_LAYER_GITFORGE": "1",
      "WORKSPACE_TOOL_LAYER_SECRETS": "1",
      "WORKSPACE_TOOL_LAYER_AWS": "1",
      "SHELL_CONFIG_SOURCE": "local",
      "SHELL_CONFIG_LOCAL_DIR": ".local/sources/shell-config"
    }
  },
  "remoteUser": "vscode",
  "containerUser": "vscode",
  "workspaceFolder": "/workspaces/tboss-workspace"
}
```

## Image Names and Tags

Initial published images should be:

```text
ghcr.io/grndzero101/dev-container-fortress:ubuntu
ghcr.io/grndzero101/dev-container-fortress:ubuntu-full
ghcr.io/grndzero101/dev-container-fortress:alpine
ghcr.io/grndzero101/dev-container-fortress:ubuntu-v0.1.0
ghcr.io/grndzero101/dev-container-fortress:ubuntu-full-v0.1.0
ghcr.io/grndzero101/dev-container-fortress:alpine-v0.1.0
```

The amd64-only Arch image publishes as `arch`, `arch-v<version>`, and
`arch-sha-<short-sha>` once the `M9a` target lands.

Floating tags:

- `ubuntu`
- `ubuntu-full`
- `alpine`

Versioned rollback tags:

- `ubuntu-v0.1.0`
- `ubuntu-full-v0.1.0`
- `alpine-v0.1.0`

Optional later tags:

- `ubuntu-YYYY-MM`
- `alpine-YYYY-MM`
- commit SHA tags for debugging CI output:
  `ubuntu-sha-<short-sha>`, `ubuntu-full-sha-<short-sha>`, and
  `alpine-sha-<short-sha>`

## Release Work

Suggested implementation sequence:

1. Stabilize Dockerfile inputs and build args.
2. Decide exact public image names and tag policy.
3. Create the thin `tboss-workspace` orchestrator repo scaffold and validate
   the consumer shape locally.
4. Add a GitHub Actions workflow that builds Ubuntu, Ubuntu daily-driver, and
   Alpine images.
5. Add GHCR publishing through `docker/build-push-action`.
6. Add smoke tests before pushing or before release tagging.
7. Point the default `tboss-workspace` devcontainer at the published
   `ubuntu-full` image.
8. Document workspace consumption with a published image.
9. Cut the first `v0.1.0` release.

Likely files involved:

```text
.github/workflows/ci.yml
containers/ubuntu/Dockerfile
containers/alpine/Dockerfile
docs/devcontainer-usage.md
docs/container-usage.md
README.md
DEVELOPMENT.md
../tboss-workspace/.devcontainer/devcontainer.json
../tboss-workspace/.devcontainer/local-build/devcontainer.json
../tboss-workspace/tboss.code-workspace
../tboss-workspace/README.md
```

## Smoke Test Expectations

Before publishing a release image, verify that Ubuntu, Ubuntu daily-driver, and
Alpine images provide the core toolchain:

```zsh
whoami
zsh --version
git --version
rg --version
uv --version
ft --version
tenv --version
starship --version
zoxide --version
atuin --version
nvim --version
fzf --version
```

Also verify the target-specific plan:

```zsh
ft plan --manifest /home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml --target ubuntu --use-manifest-version
ft plan --manifest /home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml --target alpine --use-manifest-version
```

For the `ubuntu-full` image, also verify the daily-driver layers:

```zsh
gh --version
glab --version
aws --version
gpg --version
pass --version
```

## GitHub Packages Notes

GitHub Free can publish public images to GitHub Container Registry.

Current practical assumptions:

- public GHCR container images are suitable for this project
- keep image sprawl low even when storage is free
- retain a small number of floating and versioned tags
- periodically delete obsolete image versions from GitHub Packages

## Non-Goals for the Initial Release

- Do not require the workspace repo to be a Git submodule parent.
- Do not require child repos to be committed into the workspace repo.
- Do not make every downstream project depend on the workspace repo.
- Do not solve every host/workstation bootstrap case before publishing images.
- Do not over-build tag retention automation before image publishing works.

## Desired End State

`dev-container-fortress` becomes the independently released toolchain image
project.

Workspace/orchestration repos become thin consumers:

```json
{
  "name": "project workspace",
  "image": "ghcr.io/grndzero101/dev-container-fortress:ubuntu-full",
  "remoteUser": "vscode",
  "workspaceFolder": "/workspaces/project-workspace"
}
```

This keeps the toolchain release lifecycle separate from project workspace
composition, while still allowing one VS Code devcontainer to operate across
multiple related repositories.
