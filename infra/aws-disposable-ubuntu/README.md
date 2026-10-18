# AWS Disposable Ubuntu

This directory is reserved for the first real-cloud Dev Fortress host target.

The intended use is:

- provision one disposable Ubuntu VM, using cheap EC2 Spot or stable on-demand capacity
- output the minimal connection facts needed to join the existing
  `ft host ...` workflow
- destroy and recreate the VM cleanly so daily development keeps exercising the
  bootstrap path from the beginning

The first pass should favor:

- simple public reachability over complex networking
- explicit SSH user and AMI assumptions
- low-cost disposable testing over broad cloud abstraction
- a fixed documented instance-shape fallback even if spot-selection helpers are added

The target is not meant to become a generic AWS platform module on day one.
It exists to prove the Dev Fortress host loop against a real VM.

## Validation Status

This stack has now been exercised against a real Ubuntu EC2 instance in
`ap-southeast-1`:

- Terraform provisioned the host successfully
- the generated target flowed into `ft host doctor --probe`
- `ft host bootstrap --check` and normal bootstrap both succeeded
- Session Manager console access worked after the instance profile was attached

- `terraform destroy` and `ft infra aws-disposable-ubuntu destroy` tore hosts
  down cleanly, including a disposable Arch host on 2026-10-17

## Current Shape

The first Terraform pass here is intentionally small:

- default-VPC-first networking
- one SSH security group
- one EC2 instance, Ubuntu by default, with the OS chosen from a data-driven profile map
- one EC2 IAM role and instance profile for AWS Systems Manager Session Manager, when the OS image ships the agent
- optional Spot market request with an explicit on-demand stability mode
- one EC2 key pair created from operator-supplied public key material
- dynamic SSH ingress detection from the current public IP when explicit CIDRs are not supplied
- outputs that can be copied into `hosts.toml`

This is intentionally not a full AWS platform layer.

## Files

- `versions.tf`: Terraform and provider requirements
- `providers.tf`: AWS provider setup
- `variables.tf`: operator-facing inputs
- `data.tf`: default VPC plus the Ubuntu or Arch AMI lookup
- `iam.tf`: Session Manager role, policy attachment, and instance profile
- `main.tf`: key pair, security group, and instance resources
- `outputs.tf`: connection facts and a convenience TOML fragment
- `spot_select.py`: stack-local EC2 capacity selector used by `ft`
- `terraform.tfvars.example`: example local input file

## Expected Operator Flow

The preferred operator loop now runs through `ft`, which derives the managed SSH
public key automatically and passes it to Terraform via `TF_VAR_ssh_public_key`.

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in the stable values.
2. Select a capacity mode with `uv run ft infra aws-disposable-ubuntu capacity select`.
3. Run `uv run ft infra aws-disposable-ubuntu plan`.
4. Run `uv run ft infra aws-disposable-ubuntu apply`.
5. Run `uv run ft host doctor <target> --probe`.
6. Run `uv run ft host bootstrap <target> --check`.
7. Run `uv run ft host bootstrap <target>`.
8. Run `uv run ft host bootstrap <target>` again to confirm convergence.
9. Initialize remote Git checkouts with `uv run ft deploy init <target>`.
10. Destroy the host when validation is complete with `uv run ft infra aws-disposable-ubuntu destroy`.

Example cheap Spot loop:

```zsh
cp infra/aws-disposable-ubuntu/terraform.tfvars.example infra/aws-disposable-ubuntu/terraform.tfvars
uv run ft infra aws-disposable-ubuntu capacity select --market spot
uv run ft infra aws-disposable-ubuntu plan
uv run ft infra aws-disposable-ubuntu apply
uv run ft host doctor dev-fortress-ec2-dev --probe
uv run ft host bootstrap dev-fortress-ec2-dev --check
uv run ft host bootstrap dev-fortress-ec2-dev
uv run ft host bootstrap dev-fortress-ec2-dev
uv run ft deploy init dev-fortress-ec2-dev
uv run ft infra aws-disposable-ubuntu destroy
```

Example stable daily-driver loop:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select --market on-demand --instance-type t4g.medium
uv run ft infra aws-disposable-ubuntu plan
uv run ft infra aws-disposable-ubuntu apply
```

`ft deploy init` clones or updates the development checkouts on the remote host
under `~/workspaces/tboss` by default:

```text
~/workspaces/tboss/
  dev-container-fortress/
  shell-config/
```

Override the remote parent with `--workspace-parent` when needed.

When `--architecture` is omitted, the selector considers all supported
architectures and does not apply a default family allow-list. When
`--architecture arm64` or `--architecture amd64` is supplied, the selector uses
matching default families unless `--families` is provided explicitly.
Unrestricted all-family searches can touch hundreds of instance types; use
`--families` for faster exploratory runs when you already know the broad class
you want.
Both `--families` and `--exclude-families` accept comma-separated `fnmatch`
patterns against the EC2 family name, so `m*,r*` or `t*` are valid filters.

Example Graviton Spot search that excludes burstable `t` families:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select \
  --market spot \
  --architecture arm64 \
  --min-vcpu 2 \
  --min-memory-gib 8 \
  --exclude-families 't*'
```

Example x86_64 Spot search using architecture-aware defaults:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select \
  --market spot \
  --architecture amd64 \
  --min-vcpu 2 \
  --min-memory-gib 8
```

Use `--sort-by` when the first selected candidate should optimize for something
other than the default volatility-adjusted score. Supported values are `score`,
`spot-price`, `discount`, `savings`, `on-demand-price`, `vcpu`, and `memory`.
For example, to select the highest Spot discount percentage while keeping the
search bounded:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select \
  --market spot \
  --min-vcpu 2 \
  --min-memory-gib 8 \
  --max-vcpu 8 \
  --max-memory-gib 32 \
  --max-spot-monthly 50 \
  --exclude-families 't*' \
  --sort-by discount
```

Ceiling filters are available for vCPU, memory, Spot hourly/monthly price, and
on-demand hourly price: `--max-vcpu`, `--max-memory-gib`, `--max-hourly-price`,
`--max-spot-monthly`, and `--max-on-demand-hourly`.

Capacity selector inputs can be saved as named presets and loaded later. Explicit
CLI flags override loaded preset values, so presets are useful baselines rather
than locked profiles:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select \
  --market spot \
  --min-vcpu 2 \
  --min-memory-gib 8 \
  --max-spot-monthly 50 \
  --exclude-families 't*' \
  --sort-by discount \
  --save-preset cheap-dev

uv run ft infra aws-disposable-ubuntu capacity select \
  --load-preset cheap-dev \
  --max-spot-monthly 80
```

Successful preset-backed runs and runs with explicit selection criteria also
update the special local `last` preset. This includes `--save-preset`,
`--load-preset`, `--last`, and selector options such as `--min-vcpu`,
`--architecture`, or `--sort-by`. A plain `capacity select` without selector
options does not update `last`. Reload it with:

```zsh
uv run ft infra aws-disposable-ubuntu capacity select --last
```

Named presets are stored under
`infra/aws-disposable-ubuntu/capacity-presets/`. The special `last.json` file is
local-only and ignored by Git.

`capacity select` writes
`infra/aws-disposable-ubuntu/capacity.auto.tfvars.json` by default. Terraform
loads that file automatically. This makes the selected market, instance type,
architecture, subnet, Spot max price, on-demand hourly price, and Spot discount
visible before apply. The generated file is local-only and ignored by Git.

AWS discovery data is cached under the XDG cache directory by default. Instance
type metadata, default subnet discovery, instance type offerings, and the
regional on-demand price catalog use TTL-based cache entries. Spot history is
cached per instance type and refreshed incrementally from the newest cached
timestamp with a small overlap window. Use `--refresh-cache` to force fresh AWS
reads or `--no-cache` for a single uncached run.
Recent Spot history cache entries are trusted briefly before any incremental
refresh is attempted; tune that with `--spot-history-fresh-ttl-minutes`.

When run from an interactive terminal, `capacity select` shows progress on
stderr while keeping the machine-readable JSON on stdout. Use `--progress` to
force the display or `--no-progress` to suppress it. Spot history fetches run
concurrently; tune the worker count with `--workers`.

`ft infra aws-disposable-ubuntu apply` also imports the Terraform-emitted host
target into your configured `hosts.toml` by default, so the manual TOML copy step
is no longer required in the common case.

The raw Terraform path still works when needed:

```zsh
cd infra/aws-disposable-ubuntu
terraform init
terraform validate
terraform plan
terraform apply
terraform output host_target_toml_fragment
```

When `enable_session_manager = true` (the default), the instance is also given
an IAM role and instance profile with the AWS-managed
`AmazonSSMManagedInstanceCore` policy. That is the main requirement for opening
an AWS Systems Manager Session Manager shell from the EC2 console. For standard
Ubuntu AWS images, we currently assume the SSM Agent is already present.

By default the plan can detect your current public IP using
`https://checkip.amazonaws.com/` and turn it into a `/32` SSH ingress rule.
If you prefer explicit access rules, set `ssh_ingress_cidrs` yourself and
disable `auto_detect_ssh_ingress_cidr`.

Destroy when done:

```zsh
terraform destroy
```

## Arch Hosts

Set `os = "arch"` to boot the private Arch AMI that
[`../aws-arch-ami/`](../aws-arch-ami/) registers from the official, signed Arch
cloud image. The stack picks the newest self-owned AMI named
`dev-fortress-arch-*`, logs in as `arch`, and requires `amd64` capacity.

Keep Arch hosts in their own Terraform workspace so they never replace the
Ubuntu host in the default state. `TF_WORKSPACE` and `TF_VAR_*` pass straight
through `ft`:

```zsh
terraform -chdir=infra/aws-disposable-ubuntu workspace new arch
uv run ft infra aws-disposable-ubuntu capacity select --market spot --architecture amd64
export TF_WORKSPACE=arch TF_VAR_os=arch
uv run ft infra aws-disposable-ubuntu apply --target-name dev-fortress-ec2-arch
uv run ft host validate dev-fortress-ec2-arch
uv run ft infra aws-disposable-ubuntu destroy --target-name dev-fortress-ec2-arch
unset TF_WORKSPACE TF_VAR_os
```

> [!NOTE]
> `capacity select` rewrites the shared `capacity.auto.tfvars.json`, and auto
> tfvars take precedence over `TF_VAR_*`. Rerun it with your usual Ubuntu
> settings before the next Ubuntu apply.
>
> The Arch image has no SSM agent. Its OS profile sets `ssm_agent = false`, so
> the stack skips the Session Manager role and Arch hosts are reached over SSH
> only.

## Adding an OS Target

Every OS-specific fact lives in one entry of `local.os_profiles` in
[`locals.tf`](locals.tf). Nothing else in the stack branches on `var.os`, and the
`os` and `architecture` validations read their allowed values from the map.

| Field | Meaning |
| --- | --- |
| `ssh_user` | login user the cloud image creates through cloud-init |
| `ssm_agent` | whether the image ships the Session Manager agent |
| `architectures` | supported values of `var.architecture` (`amd64`, `arm64`) |
| `ami_ssm_parameter` | public SSM parameter path; `%s` becomes the architecture |
| `ami_owners`, `ami_name_pattern` | newest AMI matching these, filtered by architecture |

Set either `ami_ssm_parameter`, or both `ami_owners` and `ami_name_pattern`, and
leave the other fields `null`. For example, a Debian profile would use Debian's
public SSM parameters, and a Fedora profile would use the Fedora project's AMI
owner ID with a name pattern.

> [!IMPORTANT]
> A profile must not reference `var.os` or `var.architecture`; their validations
> read this map, so a reference creates a Terraform dependency cycle. Put the
> architecture in the SSM path as `%s` instead.

Adding a profile only makes the host reachable. The OS still needs support in
`ft host bootstrap` and the Ansible roles before `ft host validate` can pass.

## Cost, Interruption, and Trust Caveats

> [!WARNING]
> A running host bills until you destroy it, including its root volume. Treat
> every host as disposable and run `destroy` as soon as validation finishes.

- Spot hosts are one-time requests with `instance_interruption_behavior =
  "terminate"`. AWS can reclaim them at any time, and anything on the host is
  lost. Use `capacity select --market on-demand` when a session must survive.
- Every new host presents a new SSH host key. `ft` refreshes the managed
  `known_hosts` entry for `kind = "cloud"` targets instead of trusting the key
  blindly in your personal `~/.ssh/known_hosts`.
- SSH ingress defaults to your current public IP as a `/32`. Re-apply after your
  IP changes, or pin `ssh_ingress_cidrs` explicitly.

## Current Assumptions

- AWS credentials are available through the normal Terraform AWS provider chain
- the AWS account has a default VPC and default subnets in the chosen region
- Ubuntu cloud images use the `ubuntu` SSH user, and Arch images use `arch`
- standard Ubuntu AWS images already include the SSM Agent for Session Manager
- the operator supplies a trusted CIDR for SSH ingress, or allows automatic public-IP detection
- ARM64 is the default cost-conscious path, with a fixed instance-type fallback

These assumptions are deliberate for the first real-cloud pass and can be
broadened later if the workflow proves valuable.
