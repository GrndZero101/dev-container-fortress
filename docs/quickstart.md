# Zero to Hero Quickstart

One command takes a fresh Ubuntu or WSL2 Ubuntu machine to a Dev Fortress
workstation: Docker, the managed zsh shell from
[`shell-config`](https://github.com/GrndZero101/shell-config), the Homebrew
toolchain, and the `ft` operator CLI. This page is the whole onramp; the other
docs go deeper on one area each.

## :clipboard: Before You Start

You need:

- Ubuntu or WSL2 Ubuntu. Ubuntu 26.04 LTS is the tested baseline, on amd64 and
  arm64
- `curl`, and a user that can `sudo`
- one terminal for the whole run

> [!NOTE]
> On other platforms, including macOS today, only `--mode cli` works, and it
> needs `git` and `zsh` already installed. See [Install Modes](#gear-install-modes).

On WSL2, also check:

- `systemd` is on, which Docker needs. The installer checks it and tells you
  how to enable it if it is off
- you start from the Linux filesystem, such as `~`, not from `/mnt/c/...`

## :rocket: 1. Run the Installer

```sh
cd ~
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | sh
```

The checkout lands in `./dev-container-fortress` under the directory you start
from, so starting from `~` gives `~/dev-container-fortress`. Pass `--dir` to
choose another place.

`sudo` asks for your password once, at the start. The installer then:

1. installs the native prerequisites (`git`, `zsh`, `python3`, and a few more)
2. clones or refreshes the checkout
3. installs `uv`, the Python that `.python-version` pins, a live `ft` CLI, and
   a user-level Ansible
4. converges this machine with `ft host bootstrap localhost`: Docker,
   `shell-config`, zsh as your login shell, the Homebrew toolchain, and a
   kickstart Neovim launcher
5. sets your Git identity if it is missing

A fresh host takes about five minutes. The installer keeps the `sudo` session
alive in the background for the Ansible run, so keep the same terminal open
until it prints `Install complete`.

## :package: 2. Pick Extras (Optional)

Large or opinionated extras are off unless you select them:

| Option | What it adds |
| --- | --- |
| `claude-code` | Claude Code through its native installer (about 270 MB; updates itself) |
| `tmux-minimal` | plain tmux settings: no plugins, no downloads, tmux 3.2+ |
| `tmux-full` | catppuccin theme, tpm plugins, a `sesh` session picker, and `gitmux` status; tmux 3.8+ |
| `tmux-raidboss` | `tmux-full` plus a second status line of system modules; tmux 3.8+ |

Pick at most one tmux profile. Without one, tmux keeps its stock settings and
Dev Fortress writes no tmux config.

Select options in one of three ways:

| Way | Example | Lasts |
| --- | --- | --- |
| Flag or variable | `sh -s -- --options claude-code,tmux-full` | this run; overrides the saved choice |
| Checkbox picker | `sh -s -- --interactive`, or `ft options pick` later | saved to `options.toml` |
| Config file | `enabled = ["claude-code"]` in `${XDG_CONFIG_HOME:-~/.config}/dev-container-fortress/options.toml` | every later bootstrap |

For example:

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  sh -s -- --options claude-code,tmux-full
```

`ft options` lists the choices and shows what the next bootstrap installs.
Removing an option later stops managing it but does not uninstall it.

> [!TIP]
> Selecting any tmux profile installs all three. Switch between them later with
> `csm tmux-profile <name>`, or back to stock tmux with
> `csm tmux-profile none`; a bootstrap re-run keeps your choice. Personal tmux
> settings go in `${XDG_CONFIG_HOME:-~/.config}/tmux/local.conf`, which every
> profile loads last.

## :bust_in_silhouette: 3. Git Identity

The installer ends with `ft identity`, which sets the global Git `user.name`
and `user.email`:

- an existing identity is kept
- `DEV_CONTAINER_FORTRESS_GIT_NAME` and `DEV_CONTAINER_FORTRESS_GIT_EMAIL` set
  it without a prompt
- otherwise it prompts on the terminal for whatever is missing, and skips with
  the `git config` commands when there is no terminal

Run `ft identity --help` later to change it, or to start a `gh` or `glab`
login with `--login`.

> [!IMPORTANT]
> If your GitHub account keeps its email private, GitHub declines pushes from
> that address. Use the noreply address from GitHub → Settings → Emails. For a
> corporate forge or GitLab, use the address that forge expects.

## :white_check_mark: 4. Open a New Terminal

The new terminal starts the managed zsh login shell. Its first start downloads
the shell plugins, which takes a few seconds. Then check the result:

```sh
ft --help
docker run --rm hello-world
ft host validate localhost -K
```

`ft host validate` runs a check-mode pass, a real pass, and a second pass that
must report `changed=0`. `-K` asks for your `sudo` password.

## :house: Existing Machines

Re-running Dev Fortress on a machine you already set up by hand is safe. It
converges toward the same baseline without deleting your files:

| Your file | What Dev Fortress does |
| --- | --- |
| `~/.zshenv` | `shell-config` moves it to `~/.zshenv.backup.<timestamp>` and links its own |
| `~/.zshrc` | left in place, but the managed zsh no longer reads it |
| `~/.profile`, `~/.zprofile` | adds only a marked `DEV FORTRESS HOMEBREW` block |
| `~/.tmux.conf` | left alone; no tmux profile is linked while it exists |
| `~/.gitconfig` identity | kept |
| `~/.config/nvim` | left alone; kickstart Neovim gets its own `nvim-kickstart` launcher |

The run ends with a list of anything you should act on, just above the play
recap. Carry personal zsh settings from your old `~/.zshrc` into `env.zsh`
(exports) or `aliases.zsh` under
`${XDG_CONFIG_HOME:-~/.config}/shell-config.local/zsh-tll-citadel-dev-fortress/`,
then remove `~/.zshrc`.

> [!TIP]
> To keep your current login shell, run the installer with
> `DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL=0`.

## :arrows_counterclockwise: Re-run and Update

Run the same one-liner again. It fast-forwards the checkout, re-applies your
saved options, and finishes in well under a minute when nothing changed.

From inside the checkout, `ft host bootstrap localhost -K` converges again
without re-running the installer.

## :gear: Install Modes

| Mode | What it does |
| --- | --- |
| `host` (default) | Prerequisites, `ft`, and the full `localhost` bootstrap above |
| `cli` | Prerequisites (Ubuntu only), the checkout, `uv`, `ft`, and Ansible; no other host changes |
| `workspace` | A thin host: prerequisites, `ft`, and Docker, plus the `ubuntu-full` daily-driver container image |

`workspace` mode keeps the daily-driver toolchain in a container instead of on
the host: no `shell-config`, login shell, Homebrew, or extras.

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  sh -s -- --mode workspace
```

When it finishes, open a new terminal so your user picks up the `docker`
group, then run `ft workspace enter ubuntu-full`. The image is built locally by
default, because corporate networks may block public registries; add
`--workspace-image published` to pull the published image instead, which is
faster but amd64 only today.

> [!TIP]
> A thin host becomes a full workstation when you re-run the installer without
> `--mode workspace`. Going the other way removes nothing.

## :wrench: Every Override

Pass flags through the pipe with `sh -s --`. Every flag also has an
environment variable:

| Variable | Flag | Purpose |
| --- | --- | --- |
| `DEV_CONTAINER_FORTRESS_MODE` | `--mode` | `host`, `cli`, or `workspace` |
| `DEV_CONTAINER_FORTRESS_OPTIONS` | `--options` | extras for this run, such as `claude-code,tmux-full`, or `none` |
| `DEV_CONTAINER_FORTRESS_INTERACTIVE` | `--interactive` | `1` picks extras in a checkbox list |
| `DEV_CONTAINER_FORTRESS_WORKSPACE_IMAGE` | `--workspace-image` | workspace mode: `local` (default) or `published` |
| `DEV_CONTAINER_FORTRESS_DIR` | `--dir` | the checkout location |
| `DEV_CONTAINER_FORTRESS_REF` | `--ref` | a branch, tag, or commit |
| `DEV_CONTAINER_FORTRESS_REPO` | `--repo` | an alternate Git repository URL |
| `DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL` | | `0` keeps your current login shell |
| `DEV_CONTAINER_FORTRESS_GIT_NAME` | | Git `user.name` without a prompt |
| `DEV_CONTAINER_FORTRESS_GIT_EMAIL` | | Git `user.email` without a prompt |
| `DEV_CONTAINER_FORTRESS_FORGE_LOGIN` | | `github` or `gitlab`: also start a forge login |
| `DEV_CONTAINER_FORTRESS_PYTHON_VERSION` | | override the `.python-version` pin for `bootstrap.zsh` |

### Testing a branch

Install a branch with `--ref <branch>`. `raw.githubusercontent.com` can serve a
cached `install.sh` for a few minutes after a push, so for a branch you just
changed, fetch the installer by commit SHA:

```sh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/<sha>/install.sh | \
  sh -s -- --ref <branch>
```

## :window: WSL2 Notes

- Dev Fortress installs Docker CE inside the distro. If you already use Docker
  Desktop's WSL integration in the same distro, pick one runtime rather than
  mixing them
- VS Code on Windows reads the Windows SSH config, not the one inside WSL.
  Write host entries there with `ft host ssh-config <target> --install --windows`
- stopping any other WSL2 distro can switch off Windows interop for all of
  them, which breaks `wsl.exe`, `cmd.exe`, browser opening, and the Windows Git
  credential manager. `sudo systemctl restart systemd-binfmt` restores it

More detail: [WSL Bootstrap Notes](wsl-bootstrap.md).

## :ambulance: Troubleshooting

| Symptom | Fix |
| --- | --- |
| The run stopped partway | Re-run the one-liner; it is safe to repeat. The error also prints the `ft host bootstrap` command to resume from the checkout |
| `sudo` asked again, or Ansible said a password is required | Run the whole install in one terminal; the cached `sudo` session belongs to it |
| `docker: permission denied` | Open a new terminal so your user picks up the `docker` group |
| WSL2 says `systemd` is off | Add `[boot]` and `systemd=true` to `/etc/wsl.conf`, run `wsl --shutdown` from Windows, and re-run |

## :compass: Next Steps

- [Container Usage](container-usage.md) and
  [Devcontainer Usage](devcontainer-usage.md) for daily-driver containers and
  VS Code devcontainers
- [Workstation Usage](workstation-usage.md) to bootstrap other machines over
  SSH with `ft host ...`
- [EC2 Development Loop](ec2-development-loop.md) for a disposable cloud
  development host
- [DEVELOPMENT.md](../DEVELOPMENT.md) to work on Dev Fortress itself
