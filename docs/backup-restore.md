# Backup and Restore

## Status

Dev Fortress should treat backup and restore as a general operator capability,
not as a secrets-only feature.

The first concrete use case is restoring the secrets baseline into fresh or
disposable environments. The same primitive should stay flexible enough for
workspace state, project snapshots, and ad hoc operator backups.

Current direction:

- use `rustic` as the preferred backup/restore primitive where available
- install `rustic` on host targets through the Homebrew tool pool
- add container support later through the repo-owned downloader or image layer
- keep restore behavior explicit and staging-first by default
- expose shell ergonomics through a future `shell-config` curated module

## Principles

- Backup tooling should be useful beyond one predefined profile.
- Named profiles should cover common repeatable workflows.
- Ad hoc backup and restore should remain easy for operator use.
- Restores should default to a staging directory, not overwrite live state.
- In-place restore should require an explicit flag and confirmation.
- Repository credentials and backup repository credentials must stay out of
  Docker image layers.
- Backup profiles should document what they include, what they exclude, and how
  to verify a restore.

## Packaging Policy

Host targets:

- prefer Homebrew-managed `rustic` after the native bootstrap phase
- validate `rustic` as part of the host tool baseline where practical

Container targets:

- do not install `rustic` through the base OS package manager by default
- add it later through the repo-owned downloader or an explicit image layer
- keep secrets restore possible without requiring `rustic` inside the image on
  the first pass

## Profile Model

Recommended first-pass profile shape:

```text
profile name
  purpose
  included paths
  excluded paths
  repository target
  restore target
  restore verification
```

Profiles should be declarative enough for documentation, `ft`, and shell
helpers to share the same mental model later.

## Initial Profiles

### `secrets`

Purpose:
Restore the local GPG plus `pass` baseline into a fresh workspace or host.

Included state:

- exported GPG secret key backup or offline key bundle
- ownertrust export when needed
- password-store directory or private password-store Git checkout
- restore metadata such as key IDs and expected `.gpg-id` values

Excluded state:

- live agent sockets
- transient pinentry state
- unencrypted scratch exports
- backup repository credentials

Recommended restore verification:

```zsh
gpg --list-secret-keys --keyid-format LONG
test -f ~/.password-store/.gpg-id
pass show <known-entry>
```

### `workspace-state`

Purpose:
Preserve selected Dev Fortress workspace state that is useful but not suitable
for baking into images.

Candidate state:

- selected workspace state under
  `${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/workspaces`
- selected CLI config or auth state when explicitly approved by the operator
- cache only when it materially improves restore time

This profile should stay conservative. It must not silently capture secrets
that belong in the `secrets` profile.

### `project-ad-hoc`

Purpose:
Make quick operator snapshots before risky local work.

Expected behavior:

- default source is the current directory
- default restore target is a staging directory
- command output should clearly show the repository, snapshot ID, source path,
  and restore path

This should remain flexible and should not require every path to be
pre-declared.

## Future Shell Module

A future `shell-config` curated module should make `rustic` feel like an
operator tool without hiding risk.

Recommended module name:

- `rustic`

Recommended first-pass functions:

- `rustic-profile`: list known backup profiles and show what each owns
- `rustic-backup`: run a profile-backed or ad hoc backup
- `rustic-snapshots`: list snapshots with useful filters
- `rustic-restore`: restore into a staging path by default
- `rustic-check`: run repository health checks
- `rustic-secrets-backup`: explicit secrets-profile backup helper
- `rustic-secrets-restore`: explicit secrets-profile restore helper

Recommended alias policy:

- add short aliases only after the functions prove stable
- avoid aliases that make destructive restore behavior too easy to trigger
- prefer explicit names for secrets and in-place restore operations

Possible later aliases:

```zsh
rbk        # rustic-backup
rbks       # rustic-snapshots
rbr        # rustic-restore
rbp        # rustic-profile
rbcheck    # rustic-check
```

Restore UX rules:

- default restore target should be a timestamped staging directory
- `--in-place` should be explicit
- `--confirm` should be required for in-place restore
- interactive snapshot selection is useful, but the selected snapshot and target
  path must be printed before execution

## Dev Fortress Boundaries

`dev-container-fortress` should own:

- tool installation policy
- profile documentation
- validation expectations
- future `ft backup ...` command contracts if they become worthwhile

`shell-config` should own:

- interactive helper functions
- ergonomic aliases
- fuzzy snapshot selection
- shell-native status and debug surfaces

The boundary matters because backup/restore must remain usable from plain
commands and automation even if shell ergonomics are unavailable.

## Host Carry-Over

The readiness model should carry over to host OS targets, but the execution
transport should change by target type.

Shared logical checks:

- `gpg_home_present`
- `gpg_secret_key_present`
- `password_store_present`
- `password_store_initialized`

Current executor:

- workspace containers run the checks through `docker exec`

Future executors:

- WSL2/local Linux can run the same checks locally
- macOS can run the same logical checks with macOS-specific GPG and pinentry
  setup guidance
- EC2 or other remote Linux hosts can run the same checks over SSH or through
  Ansible tasks

This keeps `workspace` as the proving ground without forcing host OS targets
into the workspace container implementation.

## Next Implementation Steps

1. Keep `rustic` in the host Homebrew tool pool.
2. Add a `shell-config` curated-module design note for `rustic`.
3. Decide whether container `rustic` belongs in the downloader manifest or a
   dedicated workspace layer.
4. Define a minimal secrets restore smoke test that does not require committing
   real secret material.
5. Add `ft` validation only after the profile format is stable enough to avoid
   churn.
