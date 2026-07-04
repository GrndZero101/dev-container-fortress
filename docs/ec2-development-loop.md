# EC2 Development Loop

This runbook covers the current host-master remote development loop.

The local workstation remains the source of truth. The EC2 instance is a
disposable execution mirror used to validate the same checkout against a real
Ubuntu host and Docker runtime.

## Current Contract

Local layout:

```text
<workspace>/
  dev-container-fortress/
  shell-config/
```

Remote layout:

```text
~/workspaces/dev-fortress/
  dev-container-fortress/
  shell-config/
```

Rules:

- local files win
- sync is one-way from local to EC2
- `shell-config` is mirrored with `dev-container-fortress` by default
- repo state, virtual environments, Terraform state, caches, and local runtime
  state are excluded from the mirror
- remote edits are temporary unless deliberately copied back by the operator

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
convergence before using the host as a development mirror.

## Preview the Sync

Run a dry-run first:

```zsh
uv run ft deploy sync dev-fortress-ec2-dev --dry-run
```

If `shell-config` is not a sibling checkout, pass it explicitly:

```zsh
uv run ft deploy sync dev-fortress-ec2-dev \
  --shell-config-checkout /absolute/path/to/shell-config \
  --dry-run
```

## Sync Local Changes

After reviewing the dry-run:

```zsh
uv run ft deploy sync dev-fortress-ec2-dev
```

Use `--no-delete` only when you intentionally want to leave extra remote files
in place. The default delete behavior keeps EC2 aligned with local source.

## Run Remote Checks

Run commands from the mirrored remote `dev-container-fortress` checkout:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft doctor
uv run ft deploy exec dev-fortress-ec2-dev -- uv run pytest ft/tests
```

For remote workspace validation:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- \
  uv run ft workspace build ubuntu-full \
    --shell-config-source local \
    --shell-config-stage-from ~/workspaces/dev-fortress/shell-config

uv run ft deploy exec dev-fortress-ec2-dev -- \
  uv run ft workspace up ubuntu-full \
    --shell-config-checkout ~/workspaces/dev-fortress/shell-config

uv run ft deploy exec dev-fortress-ec2-dev -- \
  uv run ft workspace validate ubuntu-full \
    --shell-config-checkout ~/workspaces/dev-fortress/shell-config
```

For disposable container parity checks on EC2:

```zsh
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container refresh ubuntu
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container validate ubuntu
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container refresh alpine
uv run ft deploy exec dev-fortress-ec2-dev -- uv run ft container validate alpine
```

## Remote Editor Use

For the host-master loop, prefer local editing and one-way sync.

If you open the EC2 mirror through VS Code Remote SSH or Codex, treat the remote
checkout as disposable. The remote tree intentionally does not receive local
`.git` state, so normal Git operations should happen locally unless you
deliberately change the workflow.

## Tear Down

When the remote mirror is no longer needed:

```zsh
uv run ft infra aws-disposable-ubuntu destroy
```
