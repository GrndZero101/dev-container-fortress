# Ansible

This directory contains host-install automation for:

- macOS
- Linux
- WSL

The intent is to keep host provisioning idempotent and high level while leaving
component-specific behavior inside the relevant component repositories.

The deeper design goal is convergence toward a declared Dev Fortress baseline.
In practice that means this Ansible layer should be safe to rerun on:

- a fresh machine
- a previously Dev Fortress-managed machine
- an existing manually prepared machine that is already broadly aligned

The expected behavior is level-setting rather than brittle one-shot setup.
Roles should move a host toward the intended baseline, adopt compatible
pre-existing state where reasonable, and make drift or unsupported conditions
visible instead of quietly depending on snowflake history.

## Design Rules

Preferred implementation style:

- use built-in Ansible modules when they can describe the target state cleanly
- keep tasks idempotent and rerunnable
- distinguish Dev Fortress-managed state from user-owned state explicitly
- document unsupported host differences rather than hiding them in ad hoc task logic

Use `shell` or `command` only when truly justified, such as:

- no suitable built-in module exists
- the external command is itself the thing being validated or controlled
- the task stays narrow and auditable

Avoid large shell-script blobs or wrapper-script indirection when a built-in
module such as `file`, `package`, `apt`, `homebrew`, `git`, `template`,
`copy`, `lineinfile`, `authorized_key`, or `stat` would express the intent more
clearly.

Repo validation should reinforce those rules.
Use the repo-local tooling through `uv run`, including:

- `ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" uv run ansible-playbook --syntax-check ansible/playbooks/host.yml`
- `ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" uv run ansible-lint ansible`
- `uv run pre-commit run --all-files`

Examples:

- `shell-config` owns shell behavior
- tmux config should own tmux behavior
- this layer installs and wires those components together

## Target Contract

Dev Fortress now treats host provisioning targets as named units described by a
small TOML contract rather than by workstation-only assumptions.

Start from the example target file:

- [hosts.example.toml](/home/timl/projects/tboss/dev-container-fortress/ft/targets/hosts.example.toml)

Copy it to:

- `${XDG_CONFIG_HOME:-$HOME/.config}/dev-container-fortress/hosts.toml`

Current baseline fields:

- `name`
- `kind`
- `connection`
- `host`
- `user`
- `port`
- `auth_method`
- `ssh_key_name`
- `ansible_python_interpreter`
- `tags`

Current operator helpers:

- `uv run ft host list`
- `uv run ft host show <target>`
- `uv run ft host inventory`
- `uv run ft host ssh-key-path <target>`
- `uv run ft host ssh-key <target>`
- `uv run ft host ssh-key-enroll <target>`
- `uv run ft host doctor [target]`
- `uv run ft host bootstrap [target]`

## Native Bootstrap Prerequisite Contract

Before `shell-config` bootstrap runs, Dev Fortress now enforces a small native
command substrate for supported Linux targets.

Current required commands:

- `python3`
- `git`
- `curl`
- `zsh`

This is intentionally narrow. It is the minimum native layer needed to reach
the host, converge baseline packages, and bootstrap `shell-config` before
Homebrew or Linuxbrew is introduced as the preferred steady-state toolchain.

## Inventory Contract

`ft host inventory` now renders a minimal Ansible inventory from that shared
target model.

The inventory is intentionally thin for the first foundation pass:

- `ansible_connection`
- `ansible_host`
- `ansible_port`
- `ansible_user`
- `ansible_ssh_private_key_file` when the target uses a managed SSH key
- `ansible_ssh_common_args` for disposable Docker SSH targets using a Dev Fortress-managed known-hosts file
- `dev_fortress_target_kind`
- `dev_fortress_target_tags`

This is meant to stabilize the target and transport contract before the repo
grows broader workstation or Terraform-driven host provisioning.

Current bootstrap command shape is now expected to become:

```zsh
uv run ft host doctor localhost
uv run ft host ssh-key dev-fortress-ubuntu
uv run ft host ssh-key dev-fortress-alpine
uv run ft host ssh-key-enroll dev-fortress-ubuntu
uv run ft host ssh-key-enroll dev-fortress-alpine
uv run ft host doctor dev-fortress-ubuntu --probe
uv run ft host doctor dev-fortress-alpine --probe
uv run ft host bootstrap localhost --check
uv run ft host bootstrap dev-fortress-ubuntu --ensure-ssh-keys
uv run ft host bootstrap dev-fortress-alpine --ensure-ssh-keys
```

Under the hood, `ft host bootstrap` renders temporary inventory and runs:

```zsh
ansible-playbook \
  -i <(uv run ft host inventory) \
  /home/timl/projects/tboss/dev-container-fortress/ansible/playbooks/host.yml
```

The playbook is now inventory-driven rather than pinned to `localhost`, so the
same operator surface can grow from local bootstrap targets into SSH-based
remote targets later.

For the current M5 foundation pass, the host playbook still does not yet apply
full workstation roles such as tmux. It now proves the shared
contract by:

- reaching the target through the generated inventory
- validating basic target metadata and gathered facts
- ensuring XDG base directories exist for the target user
- converging a minimal baseline package set on supported Linux targets such as Ubuntu and Alpine
- converging and then asserting the native bootstrap prerequisite command contract (`python3`, `git`, `curl`, `zsh`)
- cloning and bootstrapping `shell-config` using only that minimal native prerequisite layer
- installing the fortress profile-local `zinit` checkout so the richer plugin-backed shell behavior is available on supported hosts
- converging the target user's login shell to `zsh` for non-local targets by default
- installing Linuxbrew in the supported Ubuntu prefix and converging a reduced first-pass formula set for Ubuntu targets
- installing Linuxbrew in the supported Ubuntu prefix and converging the core fortress-facing tool set for Ubuntu targets
- cloning `kickstart.nvim` into a parallel Neovim app config and exposing an
  `nvim-kickstart` launcher on supported Ubuntu targets
- installing Docker CE on Ubuntu workstation and cloud targets using Docker's
  official apt repository, including `buildx` and Compose plugins
- checking for baseline tools such as `python3`, `git`, `curl`, and `zsh`
- reporting current shell-config and Homebrew installation state for the target

This is intentional. Dev Fortress now treats native OS packages as the
bootstrap substrate and then layers Linuxbrew uplift on top for supported
Ubuntu targets. That keeps first contact honest while still moving the host
toward the preferred steady-state toolchain afterward.

For Ubuntu workstation and cloud targets, the same host bootstrap now also
converges a repo-owned Docker Engine baseline. The current implementation uses
Docker CE from Docker's official Ubuntu apt repository plus the `buildx` and
Compose plugins, and it intentionally skips disposable `kind = "docker"`
targets so the repo does not try to install Docker inside its own SSH test
containers.

For the fortress profile specifically, host bootstrap now also installs the
profile-local `zinit` checkout under the target user's XDG data directory.
That matches the existing Docker image behavior and ensures the fortress plugin
layer is present when the profile activates on real hosts.

The current Ubuntu Linuxbrew formula set is aimed at the fortress profile and
its broader operator workflow baseline, including tools such as:

- `atuin`
- `bat`
- `bats-core`
- `btop`
- `coreutils`
- `duf`
- `eza`
- `fd`
- `fzf`
- `git-delta`
- `glow`
- `gnupg`
- `gopass`
- `gum`
- `helix`
- `jq`
- `jsongrep`
- `kubernetes-cli`
- `lazygit`
- `mtr`
- `neovim`
- `nerdfetch`
- `nmap`
- `oh-my-posh`
- `pass`
- `pbzip2`
- `ripgrep`
- `rustic`
- `starship`
- `syncthing`
- `television`
- `tenv`
- `tmux`
- `tree`
- `tree-sitter-cli`
- `uv`
- `yazi`
- `yq`
- `zoxide`
- `direnv`

Homebrew is expected to pull the necessary transitive dependencies for those
formulae. Notable examples include `pass` and `gopass` bringing in the required
GPG substrate automatically. Platform-specific formulas such as
`reattach-to-user-namespace` remain macOS-only and should stay out of the
Ubuntu/WSL Linuxbrew set.

The canonical Homebrew tool-pool definition now lives in:

- [ft/tools/tool-pool.toml](/home/timl/projects/github/GrndZero101/tboss/dev-container-fortress/ft/tools/tool-pool.toml)

The host playbook and repo Brewfiles are expected to stay aligned with that
manifest.

For Neovim specifically, host bootstrap now also installs the upstream
`kickstart.nvim` starter config into a parallel XDG app directory and provides
an `nvim-kickstart` wrapper. This keeps the IDE-style starter profile
available without taking ownership of an existing user `~/.config/nvim`.

For the first remote-target pass, public-key enrollment is explicit rather than
hidden inside bootstrap. `ft host ssh-key-enroll <target>` uses the configured
target connection details plus the managed private key to append the matching
public key into the remote `authorized_keys` file when it is not already
present.

> [!NOTE]
> Disposable Docker SSH targets now use a Dev Fortress-managed known-hosts file
> under `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/known_hosts/`.
> The current policy refreshes that file from `ssh-keyscan` for Docker-style
> ephemeral targets before probe, enrollment, and bootstrap flows. A richer
> long-lived workstation host-key policy is still follow-up work.

The disposable Docker host loop is now validated on both:

- Ubuntu, with package convergence via `ansible.builtin.apt`
- Alpine, with package convergence via `community.general.apk`

For the first real remote-host pass, the recommended operator sequence is:

```zsh
uv run ft host show dev-fortress-ec2-dev
uv run ft host ssh-key dev-fortress-ec2-dev
uv run ft host ssh-key-enroll dev-fortress-ec2-dev
uv run ft host doctor dev-fortress-ec2-dev --probe
uv run ft host bootstrap dev-fortress-ec2-dev --check
uv run ft host bootstrap dev-fortress-ec2-dev
```

That assumes the target is defined in your user `hosts.toml` and points at a
reachable Ubuntu host using `connection = "ssh"` and
`ansible_python_interpreter = "/usr/bin/python3"`.

For current user-facing status of the workstation path, see [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md).
