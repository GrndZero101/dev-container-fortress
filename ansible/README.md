# Ansible

This directory contains host-install automation for:

- macOS
- Linux
- WSL

The intent is to keep host provisioning idempotent and high level while leaving
component-specific behavior inside the relevant component repositories.

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
uv run ft host ssh-key-enroll dev-fortress-ubuntu
uv run ft host doctor dev-fortress-ubuntu --probe
uv run ft host bootstrap localhost --check
uv run ft host bootstrap dev-fortress-ubuntu --ensure-ssh-keys
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

For the current thin foundation pass, the host playbook intentionally does not
yet apply workstation roles such as Homebrew, `shell-config`, or tmux. It
currently proves the shared contract by:

- reaching the target through the generated inventory
- validating basic target metadata and gathered facts
- ensuring XDG base directories exist for the target user
- checking for baseline tools such as `python3`, `git`, and `zsh`
- reporting current bootstrap readiness for the target

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

For current user-facing status of the workstation path, see [Workstation Usage](/home/timl/projects/tboss/dev-container-fortress/docs/workstation-usage.md).
