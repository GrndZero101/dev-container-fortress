# EC2 Development Loop

This runbook covers the Git-backed EC2 development-host loop.

The EC2 instance is treated as a disposable development host, not as a mirrored
copy of the local workstation. Local and EC2 checkouts synchronize through normal
Git commit, push, pull, and fetch workflows.

## Current Contract

Default remote layout:

```text
~/workspaces/tboss/
  dev-container-fortress/
  shell-config/
```

Rules:

- Terraform creates the machine; `ft` prepares it as a development host.
- Git is the synchronization boundary between local and EC2.
- Remote edits are valid work and should be committed or pushed like any other
  distributed development environment.
- `shell-config` is cloned beside `dev-container-fortress` by default.
- The workspace parent defaults to `~/workspaces/tboss` and can be overridden
  with `--workspace-parent`.
- Local rsync mirroring is a secondary utility, not the primary development loop.

## Provision and Bootstrap EC2

From the local `dev-container-fortress` checkout:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select --market spot
uv run ft infra aws-disposable-ubuntu apply
uv run ft host validate dev-fortress-ec2-dev
```

For a more stable daily-driver host, switch the same stack to on-demand before
planning or applying:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select --market on-demand --instance-type t4g.medium
uv run ft infra aws-disposable-ubuntu plan
```

Both capacity commands write
`infra/aws-disposable-ubuntu/capacity.auto.tfvars.json`, which Terraform loads
automatically. The file is intentionally local-only so each provisioning run
starts from reviewed inputs without committing account- or market-specific
choices. The selector JSON also shows the on-demand comparison price and Spot
discount percentage when AWS Pricing data is available.

To look for a Graviton Spot host while excluding burstable `t` families:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select \
  --market spot \
  --architecture arm64 \
  --min-vcpu 2 \
  --min-memory-gib 8 \
  --exclude-families 't*'
```

If `--architecture` is omitted, the selector searches all architectures and all
families. If `--architecture amd64` is supplied, x86_64 default families are
used unless `--families` is provided explicitly. All-family searches can be
large; constrain with `--families` during exploratory runs when speed matters.
Both `--families` and `--exclude-families` accept comma-separated `fnmatch`
patterns against EC2 family names, such as `m*,r*` or `t*`.

Use `--sort-by discount` when the selected candidate should be the highest Spot
discount rather than the default volatility-adjusted score. Pair broad searches
with ceilings such as `--max-vcpu`, `--max-memory-gib`, `--max-hourly-price`,
`--max-spot-monthly`, and `--max-on-demand-hourly` to avoid selecting much
larger shapes or higher monthly Spot costs than intended.

Save repeatable selector criteria with `--save-preset <name>` and reload them
with `--load-preset <name>`. Explicit CLI flags override loaded values, so a
saved baseline can be tweaked per run. Successful preset-backed runs and runs
with explicit selector options update the local `last` preset, which can be
reloaded with `--last`; plain selections without selector options leave `last`
unchanged.

The selector caches AWS discovery data in the XDG cache directory by default.
Use `--refresh-cache` when you want fresh AWS reads or `--no-cache` when you
want to bypass cached metadata for one run. Recent Spot history cache entries
are trusted briefly before any incremental refresh is attempted; tune that with
`--spot-history-fresh-ttl-minutes`.

Interactive runs show selector progress on stderr, including cache hits,
pricing counts, and Spot history record counts. The JSON result stays on stdout.
Use `--progress` or `--no-progress` to override the automatic terminal behavior.
Spot history fetches run concurrently; tune the worker count with `--workers`.

The apply step imports the Terraform-emitted target into the configured
`hosts.toml` by default. The validation step proves SSH, host bootstrap, and
convergence before using the host as a development machine.

## Initialize Remote Checkouts

Clone or update the default repo set on the EC2 host:

```zsh
uv run ft deploy init dev-fortress-ec2-dev
```

That initializes:

```text
~/workspaces/tboss/dev-container-fortress
~/workspaces/tboss/shell-config
```

Override the parent directory when needed:

```zsh
uv run ft deploy init dev-fortress-ec2-dev \
  --workspace-parent ~/workspaces/custom-tboss
```

Override clone sources or branches when testing forks:

```zsh
uv run ft deploy init dev-fortress-ec2-dev \
  --dev-repo-url git@github.com:GrndZero101/dev-container-fortress.git \
  --dev-branch main \
  --shell-config-repo-url git@github.com:GrndZero101/shell-config.git \
  --shell-config-branch main
```

Use `--skip-shell-config` only when the remote host should not clone
`shell-config`.

## Run Remote Checks

Run commands from the remote `dev-container-fortress` checkout:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft doctor
uv run ft deploy exec dev-fortress-ec2-dev -- uv run pytest ft/tests
```

For remote workspace validation:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- \
  uv run ft workspace build ubuntu-full \
    --shell-config-source local \
    --shell-config-stage-from ../shell-config

uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft workspace up ubuntu-full
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft workspace validate ubuntu-full
```

`ft deploy exec` runs from the remote `dev-container-fortress` checkout, so
`../shell-config` is the sibling clone, and `up` and `validate` find that clone
without a flag.

> [!WARNING]
> `ft deploy exec` quotes each argument for the remote shell, so `~` and
> `$HOME` are not expanded. Use paths relative to the remote checkout or
> absolute paths. To run a shell snippet inside the workspace, pass it as one
> argument:
>
> ```zsh
> uv run ft deploy exec dev-fortress-ec2-dev -- \
>   uv run ft workspace exec ubuntu-full -- zsh -lc 'git status -sb'
> ```

For disposable container parity checks on EC2:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container refresh ubuntu
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container validate ubuntu
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container refresh alpine
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container validate alpine
```

## Develop and Push From the Workspace

Open a shell inside the workspace on the host:

```zsh
uv run ft host ssh dev-fortress-ec2-dev
# then, on the host:
cd ~/workspaces/tboss/dev-container-fortress
uv run ft workspace enter ubuntu-full
```

A fresh host has no Git identity and no forge login. Set both once per host;
they persist across workspace replacement because the identity lives in the
bind-mounted checkout and the forge login lives in the persisted `config-gh` or
`config-glab` mount.

### Git identity

Set the identity on each checkout, inside the workspace:

```zsh
uv run ft identity --local --name "Your Name" --email "<id>+<user>@users.noreply.github.com"
```

On a terminal, `uv run ft identity --local` prompts for whatever is missing
instead. Plain `git config user.name` and `git config user.email` work too.

> [!IMPORTANT]
> If your GitHub account keeps its email private, GitHub declines pushes whose
> commits use that private address. Use the noreply address from
> GitHub → Settings → Emails. For an employer or GitLab identity, use the
> address that forge expects instead.

Set it per checkout rather than with `--global`. The workspace's
`~/.gitconfig` is not a persisted path, so a global identity is lost when the
container is replaced.

### GitHub login

The host has no browser, so use the device flow:

```zsh
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh auth status
```

`gh` prints a one-time code. Open <https://github.com/login/device> on any
machine and enter it within about 15 minutes; after that the code expires and
`gh` fails with `context deadline exceeded`. `gh auth setup-git` makes `gh` the
Git credential helper, so `git push` over HTTPS works.
`uv run ft identity --login github` runs the same login and `setup-git`, and
skips when `gh` is already logged in.

> [!NOTE]
> The container has no keyring, so `gh` stores the token in plain text in the
> persisted `config-gh` mount on the host disk. The disk is encrypted and
> deleted with the instance, but the token stays valid on GitHub until you run
> `gh auth logout` or revoke it under GitHub → Settings → Applications.

### GitLab and corporate forges

Use `glab auth login`, which persists in the `config-glab` mount, or the
forge's documented token flow. When a device or browser flow is blocked, set a
personal access token through the forge CLI or Git credential helper by hand.
Only the GitHub path above has been exercised end to end.

### Commit and push

```zsh
git add <paths>
git commit
git push
```

Then pull on the workstation:

```zsh
git pull --ff-only
```

## Remote Editor Use

Open the EC2 host through VS Code Remote SSH, Codex over SSH, or a later
devcontainer-on-EC2 workflow. Continue development inside:

```text
~/workspaces/tboss/dev-container-fortress
```

Install a managed OpenSSH config include for VS Code Remote SSH:

```zsh
uv run ft host ssh-config dev-fortress-ec2-dev --install --ensure-include
```

That writes `~/.ssh/config.d/dev-container-fortress` and ensures `~/.ssh/config`
contains an `Include` line for it. The managed include is rewritten each time,
so repeated EC2 reprovisioning does not accumulate stale host entries. VS Code
can then connect to the stable host alias:

```text
dev-fortress-ec2-dev
```

> [!IMPORTANT]
> From WSL2, the command above only updates the WSL `~/.ssh/config`. VS Code on
> Windows runs Remote-SSH with Windows OpenSSH and never reads that file, so
> it cannot resolve the host alias until you install the Windows-side config
> below.

When running from WSL2 but connecting with VS Code on Windows, install a
Windows-side SSH config instead:

```zsh
uv run ft host ssh-config dev-fortress-ec2-dev \
  --windows \
  --install \
  --ensure-include
```

That writes to the Windows user's `.ssh` directory as seen from WSL, exports the
managed private key and known-hosts file there, and renders `C:/...` paths for
Windows OpenSSH. The command resolves the Windows profile from `%USERPROFILE%`
or WSL Windows interop; it does not guess from the WSL username because Windows
and WSL user IDs may differ. If the Windows user path cannot be inferred, pass
it explicitly. This is required when WSL interop is disabled, and when more
than one Windows profile exists:

```zsh
uv run ft host ssh-config dev-fortress-ec2-dev \
  --windows \
  --windows-ssh-dir /mnt/c/Users/<you>/.ssh \
  --install \
  --ensure-include
```

Commit and push work from whichever host owns the active edit session. Pull on
the other host when switching back. This keeps the machine disposable while
still making remote development real work, not a throwaway mirror.

## Legacy Mirror Utility

`ft deploy sync` still exists as a one-way rsync utility for quick remote test
mirroring, but it is no longer the primary EC2 development loop. Prefer
`ft deploy init` plus Git synchronization for daily-driver use.

## Tear Down

When the remote development host is no longer needed, push any work first,
then:

```zsh
uv run ft infra aws-disposable-ubuntu destroy
```

`destroy` leaves the imported target in `hosts.toml` with the old address. The
next `apply` overwrites it, so no cleanup is needed before reprovisioning.
