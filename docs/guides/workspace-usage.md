# Workspace Usage

A **workspace** is the mounted daily-driver container: one long-running
container, driven from a terminal with `ft workspace ...`, that bind-mounts
your live checkouts and keeps logins and caches on the host so they survive
the container being replaced.

Dev Fortress has three container surfaces. Pick by intent:

| Surface | Use it to |
| --- | --- |
| `ft workspace ...` (this page) | work day to day in a terminal, inside a container that mounts your checkouts |
| [`ft workbench ...`](workbench-usage.md) | open a set of your own repos as a VS Code devcontainer |
| [`ft container ...`](container-usage.md) | build and validate the disposable test images |

Every command and flag is in the
[`ft workspace` reference](../reference/cli.md#ft-workspace).

## Before You Start

You need Docker and `ft`, which the [quickstart](../quickstart.md) installs.
Its `workspace` install mode prepares a thin host for exactly this: Docker and
`ft`, with the toolchain kept in the container.

## Start a Workspace

```zsh
ft workspace doctor ubuntu-full
ft workspace build ubuntu-full
ft workspace up ubuntu-full
ft workspace enter ubuntu-full
```

- `doctor` reports whether Docker, the image, and the mounts are ready
- `build` builds the image locally. `ft workspace pull <profile>` fetches the
  image CI publishes instead, for profiles that have one; it is faster, and
  amd64 only today
- `up` starts the container, replacing any existing one
- `enter` opens an interactive shell, starting the workspace first if needed

After a first `build` or `pull`, `ft workspace enter ubuntu-full` is the only
command you need day to day.

## Profiles

A profile names an image, the state it persists, and its optional tool layers.
They are defined in
[`ft/workspaces/profiles.toml`](../../ft/workspaces/profiles.toml).

| Profile | Adds to the Ubuntu base |
| --- | --- |
| `ubuntu-base` | nothing; the smallest workspace |
| `ubuntu-gitforge` | persisted GitHub CLI and GitLab CLI logins |
| `ubuntu-secrets` | GPG and `pass`; see [Secrets Management](secrets-management.md) |
| `ubuntu-cloud-aws` | AWS CLI state |
| `ubuntu-cloud-azure` | Azure CLI state |
| `ubuntu-full` | all of the above; the recommended daily driver |
| `ubuntu-full-rolling` | `ubuntu-full` on the newest Ubuntu release |

## What Is Mounted

- the live `dev-container-fortress` checkout, at
  `/workspace/dev-container-fortress`, which is also the working directory
- a sibling `../shell-config` checkout, at `/workspace/shell-config`, when one
  exists. Pass `--shell-config-checkout <directory>` to `up` to use another
- the profile's persisted state: caches, shell history, `zoxide` data, and the
  login state for whichever of `gh`, `glab`, AWS, Azure, GPG, and `pass` the
  profile includes. It lives under the Dev Fortress XDG state tree on the
  host, so `down`, `reset`, and image rebuilds do not log you out

`ft workspace mount-plan <profile>` prints the exact host and container paths.

## Extras

`ft workspace up` and `ft workspace enter` honour the options you saved with
`ft options`, and both take `--options` for one run. A workspace installs
`claude-code` when it starts and keeps its login and self-updates on persisted
mounts. The tmux profiles are host-only, so workspaces skip them.

## Signing In

Sign in to forges and clouds from inside the workspace as usual, for example
`gh auth login`. The state lands on a persisted mount.

```zsh
ft workspace auth doctor ubuntu-full
ft workspace auth validate ubuntu-full
```

`auth doctor` reports the auth and persisted-state handoff points for the
profile; `auth validate` checks the browser-auth helper and the profile's
auth-oriented CLIs in the running workspace.

> [!NOTE]
> A container cannot always receive a `localhost` OAuth callback. Opening a
> browser works, including on WSL2, where the workspace hands the URL to the
> Windows browser unless `BROWSER` or `GH_BROWSER` is set. For tools such as
> AWS CLI SSO, prefer a device-code flow:
> `aws sso login --use-device-code`.

## Everyday Commands

```zsh
ft workspace status
ft workspace exec ubuntu-full -- zsh -lc 'pwd'
ft workspace validate ubuntu-full
ft workspace down ubuntu-full
ft workspace reset ubuntu-full
```

- `exec` runs one command; put `--` before a command that has its own flags
- `validate` checks the shell, the mounts, and each tool layer in the running
  workspace
- `down` stops and removes the container
- `reset` removes the container and its image. Persisted state stays

## Related

- [EC2 Development Loop](ec2-development-loop.md) runs a workspace on a
  disposable cloud host
- [Secrets Management](secrets-management.md) covers GPG and `pass` in the
  `ubuntu-secrets` and `ubuntu-full` profiles
- [Daily-Driver Design](../design/daily-driver-design.md) records why
  workspaces are separate from the test containers
