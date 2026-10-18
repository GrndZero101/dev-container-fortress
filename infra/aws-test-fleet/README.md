# AWS Test Fleet

This root creates a short-lived fleet of fresh EC2 hosts, one per supported OS
target, so one verification pass covers them all. One apply creates every
host, and one destroy removes them all. Each host is an instance of the shared
[`../modules/disposable-host/`](../modules/disposable-host/) module, the same
definition the single-host [`../aws-disposable-ubuntu/`](../aws-disposable-ubuntu/)
root uses.

## :desktop_computer: Default Fleet

| Host | OS | Instance | Login user |
| --- | --- | --- | --- |
| `dev-fortress-fleet-ubuntu-2404` | Ubuntu 24.04 | `m8i.large` (amd64) | `ubuntu` |
| `dev-fortress-fleet-ubuntu-2604` | Ubuntu 26.04 | `m8g.large` (arm64) | `ubuntu` |
| `dev-fortress-fleet-ubuntu-2610` | Ubuntu 26.10 | `m8g.large` (arm64) | `ubuntu` |
| `dev-fortress-fleet-arch` | Arch Linux | `m8i.large` (amd64 only) | `arch` |
| `dev-fortress-fleet-alpine` | Alpine 3.24 | `m8g.large` (arm64) | `alpine` |

Every host trusts one shared managed `ft` SSH key, `dev-fortress-fleet`, and
SSH ingress is limited to your current public IP, detected once for the fleet.

## :clipboard: Before You Apply

- AWS credentials through the normal provider chain. For the `tboss-mgmt`
  account, refresh SSO with `aws sso login --sso-session TBOSS` when Terraform
  reports `InvalidGrantException`
- the private Arch AMI from [`../aws-arch-ami/`](../aws-arch-ami/). Without it
  the plan stops with a message saying so; drop `arch` from `hosts` to run the
  rest

To change the fleet, set `hosts` in a `terraform.tfvars` in this directory, or
export it as JSON in `TF_VAR_hosts`. Each entry takes `os`, `architecture`,
`instance_type`, and optionally `ubuntu_release` or `alpine_release`.

## :rocket: Run the Fleet

```zsh
uv run ft infra aws-test-fleet plan
uv run ft infra aws-test-fleet apply
```

`apply` imports every host into your `hosts.toml`, so the usual `ft host`
commands work on them by name or by wildcard:

```zsh
uv run ft host list
uv run ft host doctor 'dev-fortress-fleet-*' --probe
```

Then run each target's check:

| Target | Check |
| --- | --- |
| Ubuntu hosts | `uv run ft host ssh <host>`, run the one-liner from the [quickstart](../../docs/quickstart.md) on the box, then run it again for `changed=0` |
| Arch and Alpine | `uv run ft host validate <host>`, which bootstraps over SSH and expects a second pass with `changed=0` |

The one-liner supports Ubuntu only, so Arch and Alpine use the SSH bootstrap
from the operator's machine.

## :broom: Tear Down

```zsh
uv run ft infra aws-test-fleet destroy
```

The imported `hosts.toml` entries stay behind. They are harmless, and the next
apply overwrites them with the new hosts.

> [!WARNING]
> Every host bills until you destroy it, including its root volume. Five hosts
> for half an hour cost well under a dollar on demand, and less as Spot, but a
> forgotten fleet does not. Destroy it as soon as the checks finish.

## :moneybag: Capacity

Hosts are one-time Spot requests by default, which AWS can reclaim at any time.
When Spot capacity is short, or a check must not be interrupted, use on-demand
instead:

```zsh
TF_VAR_enable_spot=false uv run ft infra aws-test-fleet apply
```

The fleet does not read the single-host stack's `capacity.auto.tfvars.json`.
