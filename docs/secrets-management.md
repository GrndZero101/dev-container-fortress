# Secrets Management

## Status

Dev Fortress now has a first-pass local secrets baseline for daily-driver
workspace profiles.

Supported baseline:

- GPG is the local encryption and signing substrate.
- `pass` is the first supported password-store workflow.
- Secret material is runtime-mounted into workspaces.
- Private keys and password stores are never copied into Docker image layers.

Intentional follow-up:

- `gopass` may be added as a richer alternative later, but it is not the first
  supported baseline.
- `op` CLI integration still needs an explicit contract.
- Hardware-token provisioning remains documented guidance rather than automatic
  setup.

## Quick Start

From the `dev-container-fortress` checkout:

```zsh
uv run ft workspace build ubuntu-secrets
uv run ft workspace up ubuntu-secrets
uv run ft workspace validate ubuntu-secrets
uv run ft workspace auth validate ubuntu-secrets
```

On a fresh workspace, `auth validate` should show the GPG and password-store
mounts as present, but no usable secret material yet:

```text
OK   gpg_home_present           present
INFO gpg_secret_key_present     missing
OK   password_store_present     present
INFO password_store_initialized missing
```

For disposable testing only, create throwaway GPG and `pass` state:

```zsh
uv run ft workspace secrets init-test ubuntu-secrets
uv run ft workspace auth validate ubuntu-secrets
```

After `init-test`, the readiness checks should show usable test state:

```text
OK gpg_secret_key_present     present
OK password_store_initialized initialized
```

Do not use `init-test` for real secrets. It creates no-passphrase disposable
material so the integration path can be tested safely.

## Runtime Contract

The `secrets` workspace layer installs:

- `gnupg`
- `pinentry-curses`
- `pass`

Current container packaging policy:

- `gnupg` and `pinentry-curses` come from the base image package manager for
  now because they are complex cryptographic substrate with meaningful distro
  integration.
- `pass` is currently installed with the same layer for simplicity, but it is a
  better candidate for future repo-owned downloader installation than GnuPG.
- Host targets with Homebrew support should prefer Homebrew-managed GPG and
  password-store tooling after the native bootstrap phase.
- If the base image GnuPG version becomes a real blocker, the next escalation
  should be an explicit upstream repository or source-build spike, not an
  unreviewed random PPA.

The layer expects these persisted runtime mounts:

| Host path | Container path | Purpose |
| --- | --- | --- |
| `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/workspaces/<profile>/gnupg` | `/home/vscode/.gnupg` | GPG keyring, trustdb, and agent state |
| `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/workspaces/<profile>/password-store` | `/home/vscode/.password-store` | GPG-backed `pass` store |

The GPG directory is created with mode `0700` when the workspace starts.

Do not pass private keys through Docker build args, Docker secrets, copied build
contexts, or image layers. The supported path is runtime restore into the
persisted mount, then normal use inside the running workspace.

## Common Workflows

### Start The Secrets Workspace

Use `ubuntu-secrets` when you want to test or use only the secrets baseline:

```zsh
uv run ft workspace build ubuntu-secrets
uv run ft workspace up ubuntu-secrets
uv run ft workspace auth doctor ubuntu-secrets
uv run ft workspace validate ubuntu-secrets
uv run ft workspace auth validate ubuntu-secrets
```

Use `ubuntu-full` when you also want the broader daily-driver layers:

```zsh
uv run ft workspace build ubuntu-full
uv run ft workspace up ubuntu-full
uv run ft workspace auth doctor ubuntu-full
```

### Disposable Integration Test

Use disposable test state when you want to prove the full GPG plus `pass` path
without using personal keys:

```zsh
uv run ft workspace secrets init-test ubuntu-secrets
uv run ft workspace auth validate ubuntu-secrets
```

`init-test` creates no-passphrase, short-lived test material inside the mounted
workspace state. It refuses to overwrite existing secret keys or initialized
password-store state unless `--force` is passed. Use `--force` only for
disposable test state.

If test state already exists, the command fails with `existing_secrets_state`.
That is expected protection. To intentionally replace disposable test material:

```zsh
uv run ft workspace secrets init-test ubuntu-secrets --force
```

### Real First-Time Setup

For real operator secrets, generate or restore durable key material instead of
using `init-test`.

Inside the workspace:

```zsh
gpg --full-generate-key
gpg --list-secret-keys --keyid-format LONG
pass init <gpg-key-id-or-email>
```

Recommended first check:

```zsh
pass insert dev-fortress/smoke-test
pass show dev-fortress/smoke-test
```

That proves the mounted GPG home, trustdb, and password store work together.

Do not use `ft workspace secrets init-test` for real secrets. It intentionally
uses disposable no-passphrase material so integration tests can run without
operator-owned keys.

### Inspect The Mounted State

To see where state is mounted:

```zsh
uv run ft workspace mount-plan ubuntu-secrets
uv run ft workspace mount-plan --json ubuntu-secrets
```

The important mounts are:

- `/home/vscode/.gnupg`
- `/home/vscode/.password-store`

The host-side state lives under:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/workspaces/ubuntu-secrets/
```

### Stop Or Reset

Stop the workspace without removing the image:

```zsh
uv run ft workspace down ubuntu-secrets
```

Remove the workspace container and image:

```zsh
uv run ft workspace reset ubuntu-secrets
```

`reset` does not delete the persisted host-side GPG or password-store state.
That is intentional. Persisted secrets state should only be removed with an
explicit operator decision.

## Readiness Checks

`ft workspace auth validate <profile>` reports secrets readiness in stages.
The underlying GPG and password-store readiness checks are intentionally
transport-agnostic so the same model can later be reused for host targets over
local execution, SSH, or Ansible-backed validation.

For a fresh workspace, these are expected:

- `gpg_home_present`: `OK` once the runtime mount exists
- `gpg_secret_key_present`: `INFO missing` until a secret key is generated or
  restored
- `password_store_present`: `OK` once the runtime mount exists
- `password_store_initialized`: `INFO missing` until `pass init ...` creates
  `.password-store/.gpg-id`

After setup or restore, the target state is:

- `gpg_secret_key_present`: `OK present`
- `password_store_initialized`: `OK initialized`

These checks intentionally do not fail fresh environments. They distinguish
structural readiness from restored usable secret material.

## Restore Flow

For a fresh or disposable environment, restore in this order:

1. Start the matching workspace profile once so Dev Fortress creates the mount
   directories.
2. Restore the GPG secret key material into `/home/vscode/.gnupg`.
3. Restore the password store into `/home/vscode/.password-store`.
4. Verify `gpg --list-secret-keys` shows the expected key.
5. Verify `.password-store/.gpg-id` references the restored key.
6. Run `pass show <known-entry>` as the final functional check.

The restore source can be an offline encrypted archive, a private Git remote for
the password store plus separately protected GPG backup material, or a future
`rustic` repository once the backup workflow is formalized.

## Backup Guidance

Minimum backup set:

- exported secret keys or an offline key backup
- ownertrust if you rely on trustdb state
- the password-store Git repository or directory
- recovery notes for key IDs, store remotes, and hardware-token assumptions

Recommended direction for M7a follow-up:

- use the general `rustic`-oriented backup primitive for encrypted, repeatable
  backup and restore of the GPG backup bundle plus password-store state
- keep repository credentials and backup repository credentials outside the
  Docker image
- document one smoke-tested restore path for WSL, local Docker, and disposable
  Ubuntu EC2 workspaces

See [Backup and Restore](./backup-restore.md) for the broader operator model.

## Commit Signing

For commit signing inside a workspace, prefer the same mounted GPG home used by
`pass`.

Configure Git inside the workspace after restoring the key:

```zsh
git config --global user.signingkey <gpg-key-id>
git config --global commit.gpgsign true
git config --global gpg.program gpg
```

If signing prompts fail in a TUI, check `GPG_TTY` and pinentry behavior inside
the running shell before changing the container image.
