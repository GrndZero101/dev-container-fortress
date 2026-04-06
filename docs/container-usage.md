# Container Usage

This document describes how to build and use the Ubuntu and Alpine images directly with Docker.

See [Container Standards](/home/timl/projects/tboss/dev-container-fortress/docs/container-standards.md) for the container contract and [containers/README.md](/home/timl/projects/tboss/dev-container-fortress/containers/README.md) for implementation details.

## Current Status

Works today:

- Ubuntu image build
- Alpine image build
- non-root `vscode` runtime user
- XDG-style home layout
- runtime `uv`
- installed `ft` CLI
- installed `ft` zsh completion artifact in the XDG data tree
- installed interaction baseline: `starship`, `zoxide`, `atuin`, and `fzf`
- installed `tenv`
- cloned and bootstrapped `shell-config`
- default fortress shell profile
- optional opt-in corporate CA support for builds

## Build the Images

Ubuntu:

```zsh
docker buildx build --load   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-test   .
```

Alpine:

```zsh
docker buildx build --load   -f containers/alpine/Dockerfile   -t dev-container-fortress:alpine-test   .
```

## Run the Images

Ubuntu:

```zsh
docker run --rm -it dev-container-fortress:ubuntu-test zsh
```

Alpine:

```zsh
docker run --rm -it dev-container-fortress:alpine-test zsh
```

## Local Test Harness

For repeatable local human testing, use `ft` as the primary operator interface.
The repo-owned helper and matching `just` recipes still exist, but they now act
mainly as transitional shims rather than the source of truth.

Helper entrypoint:

```zsh
zsh ./scripts/test-container.zsh help
```

Primary `ft` style:

```zsh
ft doctor
ft doctor --json
ft completion path zsh
ft container build ubuntu
ft container up alpine
ft container validate alpine
ft container validate --json alpine
ft container status
ft container refresh ubuntu
ft container enter ubuntu
ft container shell ubuntu
ft container exec ubuntu -- printenv TERM
```

Optional `just` shim:

```zsh
just test-build ubuntu
just test-up alpine
just test-validate alpine
just test-status
```

Other useful `ft` examples:

```zsh
ft doctor alpine
ft container down alpine
ft container reset alpine
ft container logs ubuntu
ft tool plan --tool atuin --target ubuntu
ft container validate 'alp*'
```

The grouped `ft` command structure is now the primary operator direction.
The local `just` front door delegates to `ft` for the day-to-day container
workflow and is best treated as a compatibility shim.

Use `ft doctor` as the first stop when Docker, images, or managed test
containers feel out of sync. It gives a fast host-and-container pass before the
deeper `ft container validate <target>` shell checks.
Use `--json` with either command when the caller is an agent or another
automation layer that should consume structured results instead of scraping
human-readable tables.

For the most common human loops:

- `ft container refresh <target>` means rebuild the image and replace the container
- `ft container enter <target>` means ensure the target is ready and then open an interactive shell
- `ft container exec <target> -- <command ...>` is the safest form when the inner command has its own flags, for example `ft container exec ubuntu -- zsh -lc 'echo $TERM'`

Use positional target arguments such as `ubuntu` or `alpine`.
Avoid `target=ubuntu` style overrides here so the test harness stays aligned
with normal `just` usage.

> [!NOTE]
> Alpine login shells source `/etc/profile`, which resets `PATH` to system
> directories only. The image therefore installs a small `/etc/profile.d`
> fragment so user-local paths such as `${HOME}/.local/bin` remain visible for
> `ft`-installed tools during interactive login shells.

Typical loop:

```zsh
just test-build ubuntu
just test-up ubuntu
just test-validate ubuntu
just test-status
just test-shell ubuntu
just test-logs ubuntu
just test-down ubuntu
```

### Ubuntu and Alpine Parity Check

Use this short parity pass after container, shell, or toolchain changes:

1. Rebuild and replace each target container.
2. Run `fortress-hud` inside both targets.
3. Confirm the prompt engine resolves the same way in both targets unless a difference is intentional.
4. Confirm the managed shell tools surface the same way in both targets: `starship`, `atuin`, `zoxide`, and `fzf`.
5. Confirm `${HOME}/.local/bin` is still present on `PATH` in both login shells.
6. Confirm `zsh-tll-citadel-dev-fortress` remains the active profile in both targets.

For a faster repeatable pass, use the built-in validator:

```zsh
just test-validate ubuntu
just test-validate alpine

ft container validate ubuntu
ft container validate alpine
```

Suggested commands:

```zsh
just test-build ubuntu
just test-ssh-key ubuntu
just test-up ubuntu
just test-ssh-probe ubuntu
just test-ssh ubuntu
just test-validate ubuntu
just test-shell ubuntu
fortress-hud
printf '%s\n' ${PATH//:/ }

just test-build alpine
just test-up alpine
just test-validate alpine
just test-shell alpine
fortress-hud
printf '%s\n' ${PATH//:/ }
```

The helper uses deterministic names so humans and AI agents can both reason
about the same test targets:

- image tag: `dev-container-fortress:<target>-test`
- container name: `dev-fortress-<target>-test`

Supported helper commands today:

- `build`
- `up`
- `validate`
- `status`
- `logs`
- `exec`
- `shell`
- `down`
- `reset`
- `ssh-key`
- `ssh`

Supported `just` recipes today:

- `test-build <target>`
- `test-up <target>`
- `test-validate <target>`
- `test-status [target]`
- `test-logs <target>`
- `test-exec <target> <command...>`
- `test-shell <target>`
- `test-down <target>`
- `test-reset <target>`
- `test-ssh-key <target>`
- `test-ssh-probe <target>`
- `test-ssh <target>`

Current delegation split:

- `test-build`, `test-up`, `test-status`, `test-validate`, `test-down`,
  `test-reset`, `test-logs`, `test-exec`, `test-shell`, `test-ssh-key`, and
  `test-ssh-probe` all run through `ft`
- `test-ssh` uses the system `ssh` client against the disposable Ubuntu target

> [!NOTE]
> The Ubuntu disposable target now starts an SSH daemon on `127.0.0.1:2222`
> when launched through `ft container up ubuntu`. If the managed public key for
> `dev-fortress-ubuntu` already exists, startup mounts it into the container and
> authorizes it automatically. SSH trust now uses a Dev Fortress-managed
> known-hosts file under `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/known_hosts/`.
> Alpine remains shell-only for now.

Recommended disposable SSH loop for Ubuntu:

```zsh
just test-build ubuntu
just test-ssh-key ubuntu
just test-up ubuntu
just test-ssh-probe ubuntu
just test-ssh ubuntu
```

## Validate the Runtime

Split runtime validation into two passes:

- container baseline validation for the runtime user, XDG layout, and core provisioning
- fortress shell validation through `fortress-hud`

### Container Baseline Validation

Inside either container:

```zsh
whoami
echo $HOME
echo $XDG_DATA_HOME
echo $XDG_STATE_HOME
uv --version
readlink ~/.zshenv
cat ${XDG_CONFIG_HOME:-$HOME/.config}/shell-config/active-profile
command -v csm
ft plan --manifest /home/vscode/.local/share/dev-container-fortress/ft/tools/tools.toml --target ubuntu
tenv --version
```

For the Alpine image, change `--target ubuntu` to `--target alpine`.

Expected baseline behavior:

- `whoami` prints `vscode`
- `HOME` is `/home/vscode`
- `XDG_STATE_HOME` is `/home/vscode/.local/state`
- `uv` is available
- `~/.zshenv` points at the installed `shell-config` selector
- `csm` is on `PATH`
- the saved active profile is `zsh-tll-citadel-dev-fortress` unless you changed the build-time default
- `starship` is installed, so fortress `auto` prompt resolution stays consistent across Ubuntu and Alpine
- `ft` can resolve plans for the full enabled tool set
- `tenv` is already installed and runnable

### Fortress Shell Validation

Inside the same container, validate the active shell profile with:

```zsh
fortress-hud
fortress-hud --env
```

Use this to confirm:

- the active profile is `zsh-tll-citadel-dev-fortress`
- resolved fortress settings and their sources look correct
- prompt engine configuration resolved as expected
- shell-facing tool availability matches the image contents

> [!TIP]
> Prefer `fortress-hud` for shell and profile validation instead of growing long ad hoc command lists. It gives a more complete runtime view and stays aligned with future fortress feature changes.

## Optional Corporate CA Support

Corporate CA support is opt-in.

Prepare a directory under the repo root that contains one or more PEM-formatted `.crt` files, for example:

```zsh
mkdir -p .local/certs
cp /path/to/your-root-ca.crt .local/certs/
cp /path/to/your-intermediate-ca.crt .local/certs/
```

Then build with the directory path:

```zsh
docker buildx build --load   --build-arg CORPORATE_CA_CERT_DIR=.local/certs   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-ca-test   .
```

The same pattern works for Alpine.

If `CORPORATE_CA_CERT_DIR` is unset or empty, the CA step is skipped.
If it is set, the build requires:

- the directory to exist
- at least one `.crt` file
- each `.crt` file to parse as a valid PEM certificate

> [!IMPORTANT]
> Keep private certificate material under an ignored path such as `.local/certs/` and do not commit it.

## Shell-Config Source Modes

By default, `ft container build` and the raw Dockerfiles clone `shell-config` from GitHub:

```zsh
ft container build ubuntu
ft container build ubuntu --shell-config-branch feature-ohmyposh_disble_transient_prompt
```

The equivalent raw Docker form is:

```zsh
docker buildx build --load   --build-arg SHELL_CONFIG_SOURCE=github   --build-arg SHELL_CONFIG_REPO_URL=https://github.com/GrndZero101/shell-config.git   --build-arg SHELL_CONFIG_BRANCH=main   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-test   .
```

To use a repo-local source instead, `ft` can stage a sanitized checkout for you:

```zsh
ft container build ubuntu \
  --shell-config-source local \
  --shell-config-stage-from /absolute/path/to/shell-config
```

If you want the manual path instead, first stage an existing absolute-path checkout into the repo build context:

```zsh
zsh ./scripts/stage-shell-config.zsh /absolute/path/to/shell-config
```

Then build with local mode:

```zsh
docker buildx build --load   --build-arg SHELL_CONFIG_SOURCE=local   --build-arg SHELL_CONFIG_LOCAL_DIR=.local/sources/shell-config   -f containers/ubuntu/Dockerfile   -t dev-container-fortress:ubuntu-local-shell-config   .
```

> [!TIP]
> Docker cannot see a sibling checkout outside the build context directly. The staging helper copies your chosen host checkout into `.local/sources/shell-config` so the build can consume it.

> [!IMPORTANT]
> Moving GitHub branch refs are a poor cache key for `docker buildx`. If a GitHub-backed `shell-config` build appears to be one commit behind, prefer either:
>
> - `ft container build <target> --shell-config-source local --shell-config-stage-from /absolute/path/to/shell-config`
> - `ft container build <target> --no-cache`
> - `docker buildx prune --all`
>
> `docker system prune -a` alone may not clear the relevant `buildx` cache.
