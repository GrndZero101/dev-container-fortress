# ft CLI reference

Operator CLI for Dev Fortress provisioning, tool installation, and environment validation.

**Usage**:

```console
$ ft [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `plan`: Compatibility alias for `ft tool plan`.
* `doctor`: Run a quick operator-oriented health check...
* `identity`: Set the Git identity, and optionally start...
* `install`: Compatibility alias for `ft tool install`.
* `tool`: Manage tool installation plans and...
* `container`: Operate and validate Dev Fortress...
* `host`: Model, inspect, and render SSH-oriented...
* `workspace`: Operate mounted Dev Fortress daily-driver...
* `infra`: Run thin Terraform-backed infrastructure...
* `deploy`: Prepare remote Dev Fortress development...
* `options`: List and choose optional host bootstrap...
* `devcontainer`: Render the repository&#x27;s devcontainer...
* `workbench`: Create and render workbenches: multi-repo...
* `completion`: Generate and install shell completion...

## `ft plan`

Compatibility alias for `ft tool plan`.

**Usage**:

```console
$ ft plan [OPTIONS]
```

**Options**:

* `--tool <str>`: Plan only the named tool.
* `--manifest <path>`: Path to the tool manifest TOML file.
* `--target <str>`: Named target context for the current build or host.
* `--system <str>`: Override the detected operating system.
* `--architecture <str>`: Override the detected architecture.
* `--install-root <path>`: Override the configured install root.
* `--resolve-latest / --use-manifest-version`: Resolve current upstream GitHub releases for tools configured to do so.  [default: resolve-latest]
* `--help`: Show this message and exit.

## `ft doctor`

Run a quick operator-oriented health check across host and container state.

**Usage**:

```console
$ ft doctor [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional container target selector to inspect. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all known disposable container targets.

**Options**:

* `--json`: Render structured JSON for agentic or automated health checks.
* `--help`: Show this message and exit.

## `ft identity`

Set the Git identity, and optionally start a forge login.

Explicit values replace the current identity. Otherwise an existing
identity is kept, a terminal is prompted for missing fields, and a
non-interactive run skips with the manual commands instead of blocking.

**Usage**:

```console
$ ft identity [OPTIONS]
```

**Options**:

* `--name <str>`: Git user.name to set.  [env var: DEV_CONTAINER_FORTRESS_GIT_NAME]
* `--email <str>`: Git user.email to set.  [env var: DEV_CONTAINER_FORTRESS_GIT_EMAIL]
* `--local`: Set the identity for the current checkout instead of globally. Use inside workspaces, where ~/.gitconfig is not persisted.
* `--prompt / --no-prompt`: Prompt on a terminal for any field that is still missing.  [default: prompt]
* `--login <str>`: Also start a forge login: github (gh) or gitlab (glab).  [env var: DEV_CONTAINER_FORTRESS_FORGE_LOGIN]
* `--help`: Show this message and exit.

## `ft install`

Compatibility alias for `ft tool install`.

**Usage**:

```console
$ ft install [OPTIONS]
```

**Options**:

* `--tool <str>`: Install only the named tool.
* `--manifest <path>`: Path to the tool manifest TOML file.
* `--target <str>`: Named target context for the current build or host.
* `--system <str>`: Override the detected operating system.
* `--architecture <str>`: Override the detected architecture.
* `--install-root <path>`: Override the configured install root.
* `--healthcheck / --no-healthcheck`: Run the configured healthcheck after installation.
* `--resolve-latest / --use-manifest-version`: Resolve current upstream GitHub releases for tools configured to do so.  [default: resolve-latest]
* `--help`: Show this message and exit.

## `ft tool`

Manage tool installation plans and installs from the shared manifest.

**Usage**:

```console
$ ft tool [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `plan`: Print the resolved install plan for one...
* `install`: Install one tool or the full enabled tool...
* `formulae`: Print the Homebrew formulae for one...

### `ft tool plan`

Print the resolved install plan for one tool or the full enabled set.

**Usage**:

```console
$ ft tool plan [OPTIONS]
```

**Options**:

* `--tool <str>`: Plan only the named tool.
* `--manifest <path>`: Path to the tool manifest TOML file.
* `--target <str>`: Named target context for the current build or host.
* `--system <str>`: Override the detected operating system.
* `--architecture <str>`: Override the detected architecture.
* `--install-root <path>`: Override the configured install root.
* `--resolve-latest / --use-manifest-version`: Resolve current upstream GitHub releases for tools configured to do so.  [default: resolve-latest]
* `--help`: Show this message and exit.

### `ft tool install`

Install one tool or the full enabled tool set from the shared manifest.

**Usage**:

```console
$ ft tool install [OPTIONS]
```

**Options**:

* `--tool <str>`: Install only the named tool.
* `--manifest <path>`: Path to the tool manifest TOML file.
* `--target <str>`: Named target context for the current build or host.
* `--system <str>`: Override the detected operating system.
* `--architecture <str>`: Override the detected architecture.
* `--install-root <path>`: Override the configured install root.
* `--healthcheck / --no-healthcheck`: Run the configured healthcheck after installation.
* `--resolve-latest / --use-manifest-version`: Resolve current upstream GitHub releases for tools configured to do so.  [default: resolve-latest]
* `--help`: Show this message and exit.

### `ft tool formulae`

Print the Homebrew formulae for one platform, one per line.

The container images write this list at build time, and
``ft-brew-floor`` installs whatever is missing from it at start.

**Usage**:

```console
$ ft tool formulae [OPTIONS]
```

**Options**:

* `--manifest <path>`: Path to the tool-pool TOML file. Defaults to the repo&#x27;s ft/tools/tool-pool.toml.
* `--platform <str>`: Tool-pool platform: linux, wsl, or macos.  [default: linux]
* `--help`: Show this message and exit.

## `ft container`

Operate and validate Dev Fortress disposable container targets for human and future agentic workflows.

**Usage**:

```console
$ ft container [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `validate`: Validate shell, prompt, PATH, and core...
* `build`: Build one or more disposable container...
* `status`: Show Docker status for one or more managed...
* `up`: Start or replace one or more disposable...
* `down`: Stop and remove one or more disposable...
* `reset`: Remove one or more disposable container...
* `logs`: Follow logs for one managed disposable...
* `exec`: Run one command inside one managed...
* `shell`: Open one interactive zsh login shell in...
* `refresh`: Rebuild one target image and replace its...
* `enter`: Ensure one target is ready, then open an...

### `ft container validate`

Validate shell, prompt, PATH, and core toolchain state for one or more targets.

**Usage**:

```console
$ ft container validate [OPTIONS] {target}
```

**Arguments**:

* `target`: Target selector for disposable test containers. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.  [required]

**Options**:

* `--json`: Render structured JSON for agentic or automated validation consumers.
* `--help`: Show this message and exit.

### `ft container build`

Build one or more disposable container images for local testing.

**Usage**:

```console
$ ft container build [OPTIONS] {target}
```

**Arguments**:

* `target`: Target selector for disposable container image builds. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.  [required]

**Options**:

* `--shell-config-source <str>`: Choose whether the image installs shell-config from GitHub or from a staged repo-local checkout.  [default: github]
* `--shell-config-repo-url <str>`: GitHub repository URL to clone when using --shell-config-source github.  [default: https://github.com/GrndZero101/shell-config.git]
* `--shell-config-branch <str>`: Git branch to clone when using --shell-config-source github.  [default: main]
* `--shell-config-local-dir <str>`: Repo-relative staged shell-config path inside the Docker build context when using --shell-config-source local.
* `--shell-config-stage-from <directory>`: Absolute host checkout to stage into the repo build context before a local shell-config build.
* `--no-cache`: Disable Docker build cache for this build. Useful when a moving Git branch appears stale under buildx.
* `--help`: Show this message and exit.

### `ft container status`

Show Docker status for one or more managed disposable container targets.

**Usage**:

```console
$ ft container status [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional target selector for managed disposable containers. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.

**Options**:

* `--help`: Show this message and exit.

### `ft container up`

Start or replace one or more disposable container targets.

**Usage**:

```console
$ ft container up [OPTIONS] {target}
```

**Arguments**:

* `target`: Target selector for disposable containers to start. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft container down`

Stop and remove one or more disposable container targets.

**Usage**:

```console
$ ft container down [OPTIONS] {target}
```

**Arguments**:

* `target`: Target selector for disposable containers to remove. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft container reset`

Remove one or more disposable container targets and their tagged images.

**Usage**:

```console
$ ft container reset [OPTIONS] {target}
```

**Arguments**:

* `target`: Target selector for disposable containers and images to remove. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft container logs`

Follow logs for one managed disposable container target.

**Usage**:

```console
$ ft container logs [OPTIONS] {target}
```

**Arguments**:

* `target`: One target name or selector that must resolve to exactly one managed disposable container.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft container exec`

Run one command inside one managed disposable container target.

**Usage**:

```console
$ ft container exec [OPTIONS] {target} [command]...
```

**Arguments**:

* `target`: One target name or selector that must resolve to exactly one managed disposable container.  [required]
* `command...`: Optional command to run inside the container. When omitted, a small identity command runs. Use `--` before the inner command if it has its own flags, for example: `ft container exec ubuntu -- zsh -lc &#x27;echo $TERM&#x27;`.

**Options**:

* `--help`: Show this message and exit.

### `ft container shell`

Open one interactive zsh login shell in one managed disposable container target.

**Usage**:

```console
$ ft container shell [OPTIONS] {target}
```

**Arguments**:

* `target`: One target name or selector that must resolve to exactly one managed disposable container.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft container refresh`

Rebuild one target image and replace its managed disposable container.

**Usage**:

```console
$ ft container refresh [OPTIONS] {target}
```

**Arguments**:

* `target`: One target name or selector that must resolve to exactly one managed disposable container.  [required]

**Options**:

* `--shell-config-source <str>`: Choose whether the image installs shell-config from GitHub or from a staged repo-local checkout.  [default: github]
* `--shell-config-repo-url <str>`: GitHub repository URL to clone when using --shell-config-source github.  [default: https://github.com/GrndZero101/shell-config.git]
* `--shell-config-branch <str>`: Git branch to clone when using --shell-config-source github.  [default: main]
* `--shell-config-local-dir <str>`: Repo-relative staged shell-config path inside the Docker build context when using --shell-config-source local.
* `--shell-config-stage-from <directory>`: Absolute host checkout to stage into the repo build context before a local shell-config build.
* `--no-cache`: Disable Docker build cache for this refresh. Useful when a moving Git branch appears stale under buildx.
* `--help`: Show this message and exit.

### `ft container enter`

Ensure one target is ready, then open an interactive shell inside it.

**Usage**:

```console
$ ft container enter [OPTIONS] {target}
```

**Arguments**:

* `target`: One target name or selector that must resolve to exactly one managed disposable container.  [required]

**Options**:

* `--help`: Show this message and exit.

## `ft host`

Model, inspect, and render SSH-oriented Dev Fortress host targets for future provisioning workflows.

**Usage**:

```console
$ ft host [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List the configured Dev Fortress host...
* `show`: Show one configured host target in detail.
* `inventory`: Render a minimal Ansible inventory from...
* `import-terraform`: Import Terraform-emitted host targets into...
* `ssh-key-path`: Print the expected Dev Fortress-managed...
* `ssh-config`: Render or install an OpenSSH config block...
* `ssh-key`: Ensure the expected managed SSH key exists...
* `ssh-key-enroll`: Enroll one managed public key into the...
* `ssh`: Open an SSH session on one target, or run...
* `doctor`: Inspect host-target readiness before...
* `validate`: Run the standard doctor/bootstrap...
* `bootstrap`: Run the thin inventory-driven host...
* `secrets`: Validate host-side GPG and pass readiness...

### `ft host list`

List the configured Dev Fortress host targets.

**Usage**:

```console
$ ft host list [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all configured targets.

**Options**:

* `--config <file>`: Path to the host target TOML config. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft host show`

Show one configured host target in detail.

**Usage**:

```console
$ ft host show [OPTIONS] {target}
```

**Arguments**:

* `target`: One host target name or selector that must resolve to exactly one configured host target.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft host inventory`

Render a minimal Ansible inventory from the configured host targets.

**Usage**:

```console
$ ft host inventory [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector for the generated inventory. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all configured targets.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--json`: Render the generated inventory as structured JSON instead of YAML.
* `--help`: Show this message and exit.

### `ft host import-terraform`

Import Terraform-emitted host targets into the configured hosts.toml.

**Usage**:

```console
$ ft host import-terraform [OPTIONS]
```

**Options**:

* `--terraform-dir <directory>`: Terraform working directory to read with `terraform output -json`. Defaults to the disposable Ubuntu stack under infra/.  [default: (infra/aws-disposable-ubuntu in the checkout)]
* `--config <file>`: Optional host target config path. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--json`: Render the import result as structured JSON instead of a table.
* `--help`: Show this message and exit.

### `ft host ssh-key-path`

Print the expected Dev Fortress-managed SSH key path for one host target.

**Usage**:

```console
$ ft host ssh-key-path [OPTIONS] {target}
```

**Arguments**:

* `target`: One host target name or selector that must resolve to exactly one configured host target.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--public`: Print the public key path instead of the private key path.
* `--help`: Show this message and exit.

### `ft host ssh-config`

Render or install an OpenSSH config block for one host target.

**Usage**:

```console
$ ft host ssh-config [OPTIONS] {target}
```

**Arguments**:

* `target`: One SSH host target name or selector that must resolve to exactly one configured host target.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--host-alias <str>`: OpenSSH Host alias to render. Defaults to the target name.
* `--install`: Write the rendered block to the managed Dev Fortress SSH include file.
* `--ensure-include`: Ensure ~/.ssh/config includes the managed Dev Fortress SSH config file.
* `--windows`: Install for Windows OpenSSH from WSL by exporting key material and rendering Windows paths.
* `--windows-ssh-dir <directory>`: Windows .ssh directory as seen from WSL, such as /mnt/c/Users/name/.ssh. Defaults to Windows USERPROFILE.
* `--include-path <file>`: Managed SSH config include file to write or reference.
* `--ssh-config-path <file>`: Primary SSH config file to update when --ensure-include is used.
* `--help`: Show this message and exit.

### `ft host ssh-key`

Ensure the expected managed SSH key exists for one SSH host target.

**Usage**:

```console
$ ft host ssh-key [OPTIONS] {target}
```

**Arguments**:

* `target`: One host target name or selector that must resolve to exactly one configured host target.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--help`: Show this message and exit.

### `ft host ssh-key-enroll`

Enroll one managed public key into the remote authorized_keys file.

**Usage**:

```console
$ ft host ssh-key-enroll [OPTIONS] {target}
```

**Arguments**:

* `target`: One SSH host target name or selector that must resolve to exactly one configured host target.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--help`: Show this message and exit.

### `ft host ssh`

Open an SSH session on one target, or run one command there.

For example, `ft host ssh dev-fortress-ec2-dev -- uname -a` runs `uname -a`
and exits with its status.

**Usage**:

```console
$ ft host ssh [OPTIONS] [target] [remote_command]...
```

**Arguments**:

* `target`: Optional SSH host target name or selector that must resolve to exactly one configured host target.
* `remote_command...`: Optional command to run on the target instead of a shell; put it after --.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `-i, --interactive`: Interactively choose one SSH host target.
* `--help`: Show this message and exit.

### `ft host doctor`

Inspect host-target readiness before attempting bootstrap.

**Usage**:

```console
$ ft host doctor [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector to inspect. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all configured targets.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--probe`: Attempt a small non-interactive SSH probe for SSH targets.
* `--json`: Render structured JSON for automation or agentic consumers.
* `-i, --interactive`: Interactively choose one or more host targets to inspect.
* `--help`: Show this message and exit.

### `ft host validate`

Run the standard doctor/bootstrap convergence loop for one or more host targets.

**Usage**:

```console
$ ft host validate [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector to validate. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--json`: Render structured JSON for automation or agentic consumers.
* `-i, --interactive`: Interactively choose one or more host targets to validate.
* `-K, --ask-become-pass`: Pass --ask-become-pass through to ansible-playbook during bootstrap stages.
* `--help`: Show this message and exit.

### `ft host bootstrap`

Run the thin inventory-driven host bootstrap playbook for one or more targets.

**Usage**:

```console
$ ft host bootstrap [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector to bootstrap. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all configured targets.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--ensure-ssh-keys`: Generate missing managed SSH keys for SSH targets before bootstrap.
* `--check`: Run ansible-playbook in check mode.
* `-K, --ask-become-pass`: Pass --ask-become-pass through to ansible-playbook.
* `--options <str>`: Optional components for this run, comma-separated or repeated, or &#x27;none&#x27;. Overrides DEV_CONTAINER_FORTRESS_OPTIONS and the saved selection; see `ft options`.
* `--mode <str>`: host converges the full workstation; workspace stops at the bootstrap floor plus Docker, for a thin host that runs a daily-driver workspace, and skips the optional components.  [default: host]
* `--help`: Show this message and exit.

### `ft host secrets`

Validate host-side GPG and pass readiness using shared Dev Fortress secrets checks.

**Usage**:

```console
$ ft host secrets [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `validate`: Validate host-side GPG/pass readiness with...

#### `ft host secrets validate`

Validate host-side GPG/pass readiness with shared secrets checks.

**Usage**:

```console
$ ft host secrets validate [OPTIONS] [target]
```

**Arguments**:

* `target`: Optional host target selector to validate. Supports exact names, shell-style wildcards, and the alias &#x27;all&#x27;. Defaults to all configured targets.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

## `ft workspace`

Operate mounted Dev Fortress daily-driver workspace containers for day-to-day development.

**Usage**:

```console
$ ft workspace [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `build`: Build one workspace image from its...
* `pull`: Use the published image for one workspace...
* `status`: Show Docker status for one or more managed...
* `up`: Start or replace one managed workspace...
* `down`: Stop and remove one managed workspace...
* `reset`: Remove one managed workspace container...
* `exec`: Run one command inside one managed...
* `enter`: Ensure one workspace is ready, then open...
* `doctor`: Render a small health report for one...
* `validate`: Validate shell, mounts, and layer-specific...
* `mount-plan`: Render the resolved host-to-container...
* `auth`: Inspect auth and persisted-state handoff...
* `secrets`: Bootstrap and inspect disposable secrets...

### `ft workspace build`

Build one workspace image from its underlying Ubuntu-first container target.

**Usage**:

```console
$ ft workspace build [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-source <str>`: Choose whether the image installs shell-config from GitHub or from a staged repo-local checkout.  [default: github]
* `--shell-config-repo-url <str>`: GitHub repository URL to clone when using --shell-config-source github.  [default: https://github.com/GrndZero101/shell-config.git]
* `--shell-config-branch <str>`: Git branch to clone when using --shell-config-source github.  [default: main]
* `--shell-config-local-dir <str>`: Repo-relative staged shell-config path inside the Docker build context when using --shell-config-source local.
* `--shell-config-stage-from <directory>`: Absolute host checkout to stage into the repo build context before a local shell-config build.
* `--no-cache`: Disable Docker build cache for this workspace image build.
* `--help`: Show this message and exit.

### `ft workspace pull`

Use the published image for one workspace profile instead of a local build.

**Usage**:

```console
$ ft workspace pull [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile with a published image, such as ubuntu-full.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft workspace status`

Show Docker status for one or more managed workspace profiles.

**Usage**:

```console
$ ft workspace status [OPTIONS] [profile]
```

**Arguments**:

* `profile`: Optional named workspace profile. Defaults to all repo-owned workspace profiles.

**Options**:

* `--help`: Show this message and exit.

### `ft workspace up`

Start or replace one managed workspace container profile.

**Usage**:

```console
$ ft workspace up [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-checkout <directory>`: Optional live shell-config checkout to bind-mount into the workspace. Defaults to a sibling ../shell-config checkout when present.
* `--options <str>`: Optional components for this run, comma-separated or repeated, or &#x27;none&#x27;. Overrides DEV_CONTAINER_FORTRESS_OPTIONS and the saved selection; workspaces install claude-code and skip host-only options. See `ft options`.
* `--help`: Show this message and exit.

### `ft workspace down`

Stop and remove one managed workspace container profile.

**Usage**:

```console
$ ft workspace down [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--help`: Show this message and exit.

### `ft workspace reset`

Remove one managed workspace container profile and its tagged image.

**Usage**:

```console
$ ft workspace reset [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--brew`: Also remove the workspace&#x27;s Homebrew volume. The next `up` re-seeds it from the image; rebuild the image without cache first for a completely fresh Homebrew.
* `--help`: Show this message and exit.

### `ft workspace exec`

Run one command inside one managed workspace container profile.

**Usage**:

```console
$ ft workspace exec [OPTIONS] {profile} [command]...
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]
* `command...`: Optional command to run inside the workspace. Use `--` before the inner command when it has its own flags.

**Options**:

* `--help`: Show this message and exit.

### `ft workspace enter`

Ensure one workspace is ready, then open an interactive shell inside it.

**Usage**:

```console
$ ft workspace enter [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-checkout <directory>`: Optional live shell-config checkout to bind-mount into the workspace. Defaults to a sibling ../shell-config checkout when present.
* `--options <str>`: Optional components for this run, comma-separated or repeated, or &#x27;none&#x27;. Overrides DEV_CONTAINER_FORTRESS_OPTIONS and the saved selection; workspaces install claude-code and skip host-only options. See `ft options`.
* `--help`: Show this message and exit.

### `ft workspace doctor`

Render a small health report for one mounted daily-driver workspace profile.

**Usage**:

```console
$ ft workspace doctor [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-checkout <directory>`: Optional live shell-config checkout to verify for bind-mount readiness. Defaults to a sibling ../shell-config checkout when present.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft workspace validate`

Validate shell, mounts, and layer-specific commands inside one workspace.

**Usage**:

```console
$ ft workspace validate [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-checkout <directory>`: Optional live shell-config checkout to validate for bind-mount presence. Defaults to a sibling ../shell-config checkout when present.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft workspace mount-plan`

Render the resolved host-to-container mount plan for one workspace profile.

**Usage**:

```console
$ ft workspace mount-plan [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--shell-config-checkout <directory>`: Optional live shell-config checkout to include in the mount plan. Defaults to a sibling ../shell-config checkout when present.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft workspace auth`

Inspect auth and persisted-state handoff points for mounted Dev Fortress workspace containers.

**Usage**:

```console
$ ft workspace auth [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `doctor`: Inspect auth and persisted-state handoff...
* `validate`: Validate runtime browser-auth helpers and...

#### `ft workspace auth doctor`

Inspect auth and persisted-state handoff points for one workspace profile.

**Usage**:

```console
$ ft workspace auth doctor [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

#### `ft workspace auth validate`

Validate runtime browser-auth helpers and selected auth-oriented CLIs.

**Usage**:

```console
$ ft workspace auth validate [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft workspace secrets`

Bootstrap and inspect disposable secrets state for mounted Dev Fortress workspace containers.

**Usage**:

```console
$ ft workspace secrets [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `init-test`: Create disposable GPG/pass state for...

#### `ft workspace secrets init-test`

Create disposable GPG/pass state for testing a secrets workspace.

**Usage**:

```console
$ ft workspace secrets init-test [OPTIONS] {profile}
```

**Arguments**:

* `profile`: One named workspace profile from the repo-owned workspace manifest.  [required]

**Options**:

* `--force`: Remove existing workspace GPG/pass state before creating disposable test material.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

## `ft infra`

Run thin Terraform-backed infrastructure workflows that feed the existing Dev Fortress host loop.

**Usage**:

```console
$ ft infra [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `aws-disposable-ubuntu`: Operate the disposable Ubuntu AWS...
* `aws-test-fleet`: Operate the short-lived multi-OS EC2...

### `ft infra aws-disposable-ubuntu`

Operate the disposable Ubuntu AWS Terraform stack with Dev Fortress managed SSH keys and host-target import wiring.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `plan`: Run terraform init, validate, and plan for...
* `apply`: Run terraform init, validate, and apply...
* `destroy`: Run terraform init and destroy for the...
* `capacity`: Select EC2 capacity inputs for the...

#### `ft infra aws-disposable-ubuntu plan`

Run terraform init, validate, and plan for the disposable Ubuntu stack.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu plan [OPTIONS]
```

**Options**:

* `--terraform-dir <directory>`: Terraform working directory for the disposable Ubuntu stack.  [default: (infra/aws-disposable-ubuntu in the checkout)]
* `--seed-config <file>`: Seed host manifest used to derive the managed SSH key.  [default: (infra/aws-disposable-ubuntu/hosts.seed.toml in the checkout)]
* `--target-name <str>`: Managed SSH key and Terraform host target name to use.  [default: dev-fortress-ec2-dev]
* `--help`: Show this message and exit.

#### `ft infra aws-disposable-ubuntu apply`

Run terraform init, validate, and apply for the disposable Ubuntu stack.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu apply [OPTIONS]
```

**Options**:

* `--terraform-dir <directory>`: Terraform working directory for the disposable Ubuntu stack.  [default: (infra/aws-disposable-ubuntu in the checkout)]
* `--seed-config <file>`: Seed host manifest used to derive the managed SSH key.  [default: (infra/aws-disposable-ubuntu/hosts.seed.toml in the checkout)]
* `--target-name <str>`: Managed SSH key and Terraform host target name to use.  [default: dev-fortress-ec2-dev]
* `--config <file>`: Optional host target config path. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--auto-import / --no-auto-import`: Import the Terraform host target into hosts.toml after apply.  [default: auto-import]
* `--auto-approve`: Pass -auto-approve to terraform apply.
* `--json`: Render the import result as structured JSON when auto-importing.
* `--help`: Show this message and exit.

#### `ft infra aws-disposable-ubuntu destroy`

Run terraform init and destroy for the disposable Ubuntu stack.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu destroy [OPTIONS]
```

**Options**:

* `--terraform-dir <directory>`: Terraform working directory for the disposable Ubuntu stack.  [default: (infra/aws-disposable-ubuntu in the checkout)]
* `--seed-config <file>`: Seed host manifest used to derive the managed SSH key.  [default: (infra/aws-disposable-ubuntu/hosts.seed.toml in the checkout)]
* `--target-name <str>`: Managed SSH key and Terraform host target name to use.  [default: dev-fortress-ec2-dev]
* `--auto-approve`: Pass -auto-approve to terraform destroy.
* `--help`: Show this message and exit.

#### `ft infra aws-disposable-ubuntu capacity`

Select EC2 capacity inputs for the disposable Ubuntu Terraform stack.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu capacity [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `select`: Select Spot or on-demand EC2 inputs for...

##### `ft infra aws-disposable-ubuntu capacity select`

Select Spot or on-demand EC2 inputs for the disposable Ubuntu stack.

**Usage**:

```console
$ ft infra aws-disposable-ubuntu capacity select [OPTIONS]
```

**Options**:

* `--market <str>`: Capacity market to select: spot for cheaper disposable hosts or on-demand for stability.  [default: spot]
* `--region <str>`: AWS region to inspect for instance capacity.  [default: ap-southeast-1]
* `--architecture <str>`: Optional instance architecture filter: arm64, amd64, or x86_64.
* `--min-vcpu <int range>`: Minimum vCPU count.  [default: 2; x&gt;=1]
* `--min-memory-gib <float range>`: Minimum memory in GiB.  [default: 4.0; x&gt;=0.5]
* `--max-vcpu <int range>`: Optional maximum vCPU count ceiling.  [x&gt;=1]
* `--max-memory-gib <float range>`: Optional maximum memory ceiling in GiB.  [x&gt;=0.5]
* `--max-on-demand-hourly <float range>`: Optional maximum on-demand USD hourly price ceiling.  [x&gt;=0.0]
* `--families <str>`: Optional comma-separated EC2 family patterns to consider, in fallback preference order.
* `--exclude-families <str>`: Comma-separated EC2 family patterns to remove from the candidate set.
* `--instance-type <str>`: Optional exact instance type override within the requested spec.
* `--lookback-hours <int range>`: Spot price history window used for spot selection.  [default: 168; x&gt;=1]
* `--min-samples <int range>`: Minimum spot price history samples required per instance type and AZ.  [default: 2; x&gt;=1]
* `--max-hourly-price <float range>`: Optional maximum current spot price in USD per hour.  [x&gt;=0.0]
* `--max-spot-monthly <float range>`: Optional maximum current spot price in USD per month.  [x&gt;=0.0]
* `--sort-by <str>`: Candidate ordering: score, spot-price, discount, savings, on-demand-price, vcpu, or memory.  [default: score]
* `--volatility-weight <float range>`: Multiplier applied to spot price standard deviation while ranking.  [default: 2.0; x&gt;=0.0]
* `--load-preset <str>`: Load capacity selector inputs from a named preset before applying explicit CLI overrides.
* `--save-preset <str>`: Save the effective capacity selector inputs as a named preset after successful selection.
* `--last`: Load the special last capacity selector preset.
* `--top <int range>`: Number of ranked candidates to include in JSON output.  [default: 10; x&gt;=1]
* `--workers <int range>`: Maximum concurrent Spot history fetch workers.  [default: 8; x&gt;=1]
* `--spot-history-fresh-ttl-minutes <float range>`: Minutes to trust cached Spot history before refreshing incrementally.  [default: 15; x&gt;=0.0]
* `--include-previous-generation`: Include previous-generation EC2 instance types.
* `--cache / --no-cache`: Reuse XDG-local AWS discovery cache where possible.  [default: cache]
* `--refresh-cache`: Ignore cached AWS discovery data and repopulate it.
* `--cache-root <directory>`: Override the selector cache directory.
* `--instance-types-cache-ttl-hours <float range>`: TTL for EC2 instance type metadata cache.  [default: 168; x&gt;=0.0]
* `--subnets-cache-ttl-hours <float range>`: TTL for default VPC subnet discovery cache.  [default: 1; x&gt;=0.0]
* `--offerings-cache-ttl-hours <float range>`: TTL for instance type AZ offerings cache.  [default: 6; x&gt;=0.0]
* `--pricing-cache-ttl-hours <float range>`: TTL for on-demand pricing cache.  [default: 24; x&gt;=0.0]
* `--progress / --no-progress`: Show selector progress on stderr. Defaults to auto when stderr is a TTY.
* `--write-tfvars / --no-write-tfvars`: Write Terraform auto tfvars for the selected capacity mode.  [default: write-tfvars]
* `--tfvars-path <file>`: Terraform auto tfvars path to write when --write-tfvars is enabled.  [default: (infra/aws-disposable-ubuntu/capacity.auto.tfvars.json in the checkout)]
* `--help`: Show this message and exit.

### `ft infra aws-test-fleet`

Operate the short-lived multi-OS EC2 verification fleet: one apply creates every host, one destroy removes them all.

**Usage**:

```console
$ ft infra aws-test-fleet [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `plan`: Run terraform init, validate, and plan for...
* `apply`: Apply the EC2 test fleet, then import...
* `destroy`: Destroy every host in the EC2 test fleet...
* `check`: Run every fleet host&#x27;s check in parallel...

#### `ft infra aws-test-fleet plan`

Run terraform init, validate, and plan for the EC2 test fleet.

**Usage**:

```console
$ ft infra aws-test-fleet plan [OPTIONS]
```

**Options**:

* `--set <str>`: Host set to use from now on: lts (Ubuntu LTS on amd64 and arm64, the default) or full (every OS target on both architectures). Saved for later runs.
* `--help`: Show this message and exit.

#### `ft infra aws-test-fleet apply`

Apply the EC2 test fleet, then import every host into hosts.toml.

**Usage**:

```console
$ ft infra aws-test-fleet apply [OPTIONS]
```

**Options**:

* `--set <str>`: Host set to use from now on: lts (Ubuntu LTS on amd64 and arm64, the default) or full (every OS target on both architectures). Saved for later runs.
* `--config <file>`: Optional host target config path. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--auto-approve`: Pass -auto-approve to terraform apply.
* `--json`: Render the import result as structured JSON.
* `--help`: Show this message and exit.

#### `ft infra aws-test-fleet destroy`

Destroy every host in the EC2 test fleet and drop them from hosts.toml.

**Usage**:

```console
$ ft infra aws-test-fleet destroy [OPTIONS]
```

**Options**:

* `--config <file>`: Optional host target config path. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--auto-approve`: Pass -auto-approve to terraform destroy.
* `--help`: Show this message and exit.

#### `ft infra aws-test-fleet check`

Run every fleet host&#x27;s check in parallel and report the results.

Ubuntu hosts run the one-liner on the box, then again, which must report
changed=0. Other OSes run `ft host validate` from this machine. Each step
is logged under the XDG state directory.

**Usage**:

```console
$ ft infra aws-test-fleet check [OPTIONS]
```

**Options**:

* `--only <str>`: Shell-style pattern over fleet host names, such as &#x27;*ubuntu-2604*&#x27;.  [default: *]
* `--ref <str>`: Branch, tag, or commit for the Ubuntu one-liner checks to install. Defaults to main; push a branch before testing it.
* `--timeout <int range>`: Limit for each check step, in minutes.  [default: 25; x&gt;=1]
* `--markdown`: Also print the results as a markdown table.
* `--config <file>`: Optional host target config path. Defaults to FT_HOST_CONFIG or the XDG-managed hosts.toml path.
* `--help`: Show this message and exit.

## `ft deploy`

Prepare remote Dev Fortress development hosts and run remote validation commands.

**Usage**:

```console
$ ft deploy [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `init`: Clone or update development checkouts on...
* `sync`: Mirror local Dev Fortress checkouts to one...
* `exec`: Run one command from the remote Dev...

### `ft deploy init`

Clone or update development checkouts on one remote SSH target.

**Usage**:

```console
$ ft deploy init [OPTIONS] {target}
```

**Arguments**:

* `target`: One SSH host target to initialize as a Git-backed development host, such as dev-fortress-ec2-dev.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--workspace-parent, --remote-root <str>`: Remote parent directory that receives Git checkouts.  [default: ~/workspaces/tboss]
* `--dev-repo-url <str>`: Git URL for the dev-container-fortress checkout.  [default: https://github.com/GrndZero101/dev-container-fortress.git]
* `--dev-branch <str>`: Git branch to checkout for dev-container-fortress.  [default: main]
* `--shell-config-repo-url <str>`: Git URL for the shell-config checkout.  [default: https://github.com/GrndZero101/shell-config.git]
* `--shell-config-branch <str>`: Git branch to checkout for shell-config.  [default: main]
* `--skip-shell-config`: Only initialize dev-container-fortress and skip shell-config.
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft deploy sync`

Mirror local Dev Fortress checkouts to one remote SSH target.

**Usage**:

```console
$ ft deploy sync [OPTIONS] {target}
```

**Arguments**:

* `target`: One SSH host target to mirror local checkouts to, such as dev-fortress-ec2-dev.  [required]

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--remote-root <str>`: Legacy remote root that receives mirrored dev-container-fortress and shell-config checkouts.  [default: ~/workspaces/tboss]
* `--shell-config-checkout <directory>`: Local shell-config checkout to mirror. Defaults to sibling ../shell-config when present.
* `--skip-shell-config`: Only mirror dev-container-fortress and skip shell-config.
* `--dry-run`: Show rsync changes without writing remote files.
* `--delete / --no-delete`: Delete remote files that no longer exist in the local checkouts.  [default: delete]
* `--json`: Render structured JSON for automation or agentic consumers.
* `--help`: Show this message and exit.

### `ft deploy exec`

Run one command from the remote Dev Fortress checkout.

**Usage**:

```console
$ ft deploy exec [OPTIONS] {target} [command]...
```

**Arguments**:

* `target`: One SSH host target that already has remote checkouts.  [required]
* `command...`: Command to run from the remote dev-container-fortress checkout. Use `--` before commands with flags.

**Options**:

* `--config <file>`: Path to the host target TOML config.
* `--workspace-parent, --remote-root <str>`: Remote parent directory that contains the Git checkouts.  [default: ~/workspaces/tboss]
* `--help`: Show this message and exit.

## `ft options`

List and choose optional host bootstrap components, such as Claude Code. Nothing optional is installed unless selected.

**Usage**:

```console
$ ft options [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `pick`: Choose optional components in a checkbox...

### `ft options pick`

Choose optional components in a checkbox picker and save the selection.

**Usage**:

```console
$ ft options pick [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `ft devcontainer`

Render the repository&#x27;s devcontainer definitions from the same data that ft workspace uses.

**Usage**:

```console
$ ft devcontainer [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `render`: Write the devcontainer definitions from...

### `ft devcontainer render`

Write the devcontainer definitions from the shared runtime data.

Mounts, start steps, and option environment come from the table that
ft workspace uses, and build-arg defaults from the target Dockerfiles.

**Usage**:

```console
$ ft devcontainer render [OPTIONS]
```

**Options**:

* `--check`: Write nothing; fail when a committed definition differs from a fresh render. For pre-commit and CI.
* `--help`: Show this message and exit.

## `ft workbench`

Create and render workbenches: multi-repo devcontainers defined in ~/.config/dev-container-fortress/workbenches/&lt;name&gt;.toml.

**Usage**:

```console
$ ft workbench [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `init`: Write a workbench file and render its folder.
* `render`: Regenerate a workbench folder&#x27;s...
* `clone`: Clone a workbench&#x27;s repos that are missing...
* `list`: List saved workbenches with their folder,...

### `ft workbench init`

Write a workbench file and render its folder.

The file lands in ~/.config/dev-container-fortress/workbenches/&lt;name&gt;.toml,
where it can be edited by hand or kept in dotfiles.

**Usage**:

```console
$ ft workbench init [OPTIONS] {name}
```

**Arguments**:

* `name`: Workbench name: lowercase letters, digits, &#x27;-&#x27;.  [required]

**Options**:

* `--repo <str>`: Git URL to clone into repos/. Repeatable.
* `--profile <str>`: ft workspace profile that supplies the image, layers, and mounts.  [default: ubuntu-base]
* `--options <str>`: Comma-separated optional components, such as claude-code, or &#x27;none&#x27;. Defaults to DEV_CONTAINER_FORTRESS_OPTIONS or the saved selection; host-only options are skipped.
* `--mount <str>`: Persisted mount to add, such as aws. Repeatable.
* `--extension <str>`: VS Code extension to add. Repeatable.
* `--directory <str>`: Folder to render into. Default: ~/workbenches/&lt;name&gt;.
* `--local-build <str>`: Build the image from this Dev Fortress checkout instead of pulling.
* `--force`: Overwrite an existing workbench file.
* `--help`: Show this message and exit.

### `ft workbench render`

Regenerate a workbench folder&#x27;s devcontainer and workspace files.

**Usage**:

```console
$ ft workbench render [OPTIONS] [workbench]
```

**Arguments**:

* `workbench`: Workbench name or TOML path. Default: every workbench.

**Options**:

* `--check`: Write nothing; fail when a rendered file is stale.
* `--help`: Show this message and exit.

### `ft workbench clone`

Clone a workbench&#x27;s repos that are missing from its repos/ folder.

Clones run on the host with its Git credentials; existing folders are left
alone.

**Usage**:

```console
$ ft workbench clone [OPTIONS] [workbench]
```

**Arguments**:

* `workbench`: Workbench name or TOML path. Default: every workbench.

**Options**:

* `--help`: Show this message and exit.

### `ft workbench list`

List saved workbenches with their folder, profile, and repos.

**Usage**:

```console
$ ft workbench list [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `ft completion`

Generate and install shell completion artifacts for Dev Fortress CLIs into XDG-managed runtime paths.

**Usage**:

```console
$ ft completion [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `show`: Print ft shell completion source for one...
* `path`: Print the XDG-managed completion artifact...
* `install`: Generate and install ft shell completion...

### `ft completion show`

Print ft shell completion source for one supported shell.

**Usage**:

```console
$ ft completion show [OPTIONS] [shell]
```

**Arguments**:

* `shell`: Shell name to generate completion source for. Currently: zsh.  [default: zsh]

**Options**:

* `--help`: Show this message and exit.

### `ft completion path`

Print the XDG-managed completion artifact path for one supported shell.

**Usage**:

```console
$ ft completion path [OPTIONS] [shell]
```

**Arguments**:

* `shell`: Shell name to resolve the installed completion artifact path for.  [default: zsh]

**Options**:

* `--help`: Show this message and exit.

### `ft completion install`

Generate and install ft shell completion into an XDG-managed runtime path.

**Usage**:

```console
$ ft completion install [OPTIONS] [shell]
```

**Arguments**:

* `shell`: Shell name to generate and install completion for. Currently: zsh.  [default: zsh]

**Options**:

* `--help`: Show this message and exit.
