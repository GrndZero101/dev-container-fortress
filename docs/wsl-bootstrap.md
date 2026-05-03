# WSL Bootstrap Runbook

This runbook describes the current practical path for bringing up Dev Fortress
inside a fresh Ubuntu WSL2 distribution.

Current model:

- Windows is the outer host
- the Ubuntu WSL2 distribution is the Dev Fortress target
- bootstrap runs from inside WSL against `localhost`
- SSH is not required for the first WSL bootstrap pass

This is the right path for early WSL testing because the current target model
already supports a local host target with `connection = "local"`.

## Scope

This runbook is for:

- fresh Ubuntu under WSL2
- local bootstrap inside the Linux distro
- validating the current host-bootstrap path against `localhost`

This runbook is not for:

- native Windows PowerShell or CMD shell setup
- Windows-side SSH into WSL as the primary bootstrap path
- full Windows host management

## Assumptions

- you are inside an Ubuntu WSL2 shell
- the distro is new or close to stock
- you can use `sudo`
- you want the repo cloned into the Linux filesystem, not `/mnt/c/...`

> [!IMPORTANT]
> Clone into the Linux filesystem, for example under `~/src`.
> Do not use `/mnt/c/...` for the main checkout if you want credible shell,
> Ansible, and Linuxbrew validation.

## 1. Install baseline packages

The current minimal starting point is:

```zsh
sudo apt update
sudo apt install -y git curl zsh python3 ca-certificates rsync
```

Why these first:

- `git` and `curl` are needed for repo bootstrap paths
- `zsh` is part of the current native bootstrap substrate
- `python3` is needed by the Ansible/bootstrap path
- `ca-certificates` avoids unnecessary TLS failures
- `rsync` is already part of the normal Dev Fortress Linux-side workflow

## 2. Clone Dev Fortress inside WSL

```zsh
mkdir -p ~/src
cd ~/src
git clone https://github.com/GrndZero101/dev-container-fortress.git
cd dev-container-fortress
```

## 3. Bootstrap the repo

Use either the manual bootstrap or the one-liner installer.

Manual:

```zsh
zsh ./bootstrap.zsh
```

Installer-style:

```zsh
curl -fsSL https://raw.githubusercontent.com/GrndZero101/dev-container-fortress/main/install.sh | \
  DEV_CONTAINER_FORTRESS_DIR="$HOME/src/dev-container-fortress" sh
```

At the end of this step, the repo-local `uv` environment should be ready and
`bootstrap.zsh` should also install a live `ft` CLI into the user tool path.

Quick check:

```zsh
command -v ft
ft --help
```

## 4. Create the local host target config

The example target file already includes `localhost` as a local workstation
target.

```zsh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress"
cp ./ft/targets/hosts.example.toml \
  "${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml"
```

## 5. Inspect the local target

```zsh
uv run ft host list
uv run ft host show localhost
uv run ft host doctor localhost
uv run ft host bootstrap localhost --check -K
```

This is the first sanity gate before a real local bootstrap.

## 6. Run the real local bootstrap

```zsh
uv run ft host bootstrap localhost -K
```

Current expected behavior for the Ubuntu/WSL local path:

- XDG directories are converged
- the native bootstrap substrate is checked
- `shell-config` is cloned and bootstrapped
- the fortress profile-local `zinit` checkout is installed
- Linuxbrew uplift is attempted for supported Ubuntu targets
- readiness state is reported at the end

## 7. Enter a fresh shell

For a WSL local bootstrap, Dev Fortress does not currently change the default
login shell automatically because `localhost` uses `connection = "local"`.
Set the WSL user's default shell to `zsh` explicitly:

```zsh
sudo chsh -s "$(command -v zsh)" "$USER"
```

If `chsh` is unavailable or awkward in your WSL setup, use:

```zsh
sudo usermod --shell "$(command -v zsh)" "$USER"
```

Then start a fresh shell so the resulting environment is exercised for real:

```zsh
exec zsh
```

Useful follow-up checks:

```zsh
cat ~/.local/state/shell-config/active-profile
readlink ~/.zshenv
readlink ~/.local/bin/csm
```

## 8. Validate the local target again

Use the higher-level validation command once the first bootstrap has landed:

```zsh
uv run ft host validate localhost -K
```

That runs:

- `doctor --probe`
- `bootstrap --check`
- `bootstrap`
- second `bootstrap` convergence pass

For a local WSL target, the important outcome is that the final bootstrap pass
settles to `changed=0`. `ft host validate localhost -K` now treats that as part
of the validation contract rather than only checking the Ansible exit code.

## Optional: Docker loop inside WSL

Dev Fortress host bootstrap now converges Docker CE automatically for Ubuntu
`workstation` targets such as WSL `localhost`, but only when the WSL distro is
running with `systemd`.

That gives the repo one consistent Ubuntu Docker baseline across:

- WSL `localhost`
- real Ubuntu cloud targets such as EC2

This path intentionally avoids making Docker Desktop integration part of the
Dev Fortress host contract. If you already rely on Docker Desktop plus WSL
integration, do not mix that path with the repo-managed Docker CE install on
the same distro unless you are deliberately choosing one runtime model.

After the bootstrap run that installs Docker, refresh your login session before
expecting non-`sudo` Docker usage:

```zsh
newgrp docker
```

or simply start a fresh shell/login.

Then the container validation loop is available as usual:

```zsh
uv run ft container build ubuntu
uv run ft container build alpine
uv run ft host validate dev-fortress-ubuntu
uv run ft host validate dev-fortress-alpine
```

## Current caveats

- WSL support is still partial, not closed as a finished milestone
- the local bootstrap path is the correct first validation path; SSH-to-WSL is
  not required
- Linuxbrew, shell startup, and local Ansible execution need to be tested in
  the real WSL environment rather than inferred from macOS or EC2 behavior
- Docker CE management in WSL now expects `systemd`; if your distro does not
  expose `systemd`, the Docker role will fail fast with an explicit message
- native Windows shell setup remains out of scope for this runbook

## Recommended development setup

If you want to actively develop WSL support rather than just run a one-off
bootstrap:

- keep a dedicated WSL-native checkout
- open it through VS Code Remote - WSL or equivalent
- run Codex and the Dev Fortress loop from inside WSL

That is the only credible way to debug WSL-specific path, shell, Linuxbrew, and
Ansible behavior.
