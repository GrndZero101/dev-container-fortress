# AWS Test Fleet

This root creates a short-lived fleet of fresh EC2 hosts, one per supported OS
target, so one verification pass covers them all. One apply creates every
host, and one destroy removes them all. Each host is an instance of the shared
[`../modules/disposable-host/`](../modules/disposable-host/) module, the same
definition the single-host [`../aws-disposable-ubuntu/`](../aws-disposable-ubuntu/)
root uses.

## :desktop_computer: Fleet Sets

The fleet comes in named sets, defined in [`locals.tf`](locals.tf):

| Set | When | Hosts |
| --- | --- | --- |
| `lts` (default) | spot checks during everyday work | Ubuntu 26.04 on amd64 and arm64 |
| `full` | major milestones | Ubuntu 24.04, 26.04, and 26.10, and Alpine 3.24, each on amd64 and arm64, plus Arch on amd64: nine hosts |

Every amd64 host runs on `m8i.large` and every arm64 host on `m8g.large`, both
2 vCPU and 8 GiB, so each architecture mirrors the other. Arch Linux publishes
no arm64 image, so Arch has no arm64 mirror. Hosts are named
`dev-fortress-fleet-<os>-<release>-<architecture>`, such as
`dev-fortress-fleet-ubuntu-2604-arm64`, with the login user each image creates
(`ubuntu`, `arch`, or `alpine`).

Every host trusts one shared managed `ft` SSH key, `dev-fortress-fleet`, and
SSH ingress is limited to your current public IP, detected once for the fleet.

## :clipboard: Before You Apply

- AWS credentials through the normal provider chain. For the `tboss-mgmt`
  account, refresh SSO with `aws sso login --sso-session TBOSS` when Terraform
  reports `InvalidGrantException`
- the private Arch AMI from [`../aws-arch-ami/`](../aws-arch-ami/). Without it
  the plan stops with a message saying so; drop `arch` from `hosts` to run the
  rest

Choose a set with `--set`, which `ft` saves to `fleet.auto.tfvars.json` here,
so later plans and applies keep the same hosts until you choose again. For a
one-off mix, set `hosts` in a `terraform.tfvars` in this directory, or export it
as JSON in `TF_VAR_hosts`; it replaces the set. Each entry takes `os` and
`architecture`, and optionally `release` and `instance_type`.

## :rocket: Run the Fleet

```zsh
uv run ft infra aws-test-fleet plan             # the saved set, lts at first
uv run ft infra aws-test-fleet apply --set full # switch to full and keep it
```

`apply` imports every host into your `hosts.toml` and drops fleet hosts that
are no longer in the fleet, so the usual `ft host` commands work on them by
name or by wildcard:

```zsh
uv run ft host list
uv run ft host doctor 'dev-fortress-fleet-*' --probe
```

Then check every host at once:

```zsh
uv run ft infra aws-test-fleet check                      # installs main
uv run ft infra aws-test-fleet check --ref <branch>       # tests a pushed branch
uv run ft infra aws-test-fleet check --only '*2604*' --markdown
```

Each host gets the check its OS supports, and all of them run in parallel:

| Target | Check | Passes when |
| --- | --- | --- |
| Ubuntu | the one-liner on the box over SSH, then again | both exit 0, and the re-run reports `changed=0` |
| Arch and Alpine | `ft host validate` from this machine | it exits 0, which needs a converged second pass |

The one-liner supports Ubuntu only, so Arch and Alpine use the SSH bootstrap
from the operator's machine. `--ref` installs a branch, tag, or commit, fetched
by its commit SHA so a stale cached copy of the branch is never used; push the
branch first.

A live table shows each host's phase and time, and the run ends with a summary,
plus a markdown table with `--markdown` for milestone notes. Every step logs
to `${XDG_STATE_HOME:-~/.local/state}/dev-container-fortress/fleet-runs/<time>/`,
and the command exits non-zero when any host fails. Each step stops after
`--timeout` minutes (25 by default). To look at one host by hand, run a
command on it with `uv run ft host ssh <host> -- <command>`.

> [!NOTE]
> Alpine's cloud image grants root through `doas`, not `sudo`. The host
> playbook detects that and switches Ansible's `become` to `doas`, so nothing
> extra is needed. On Alpine the bootstrap converges the base packages,
> `shell-config`, and the login shell; Docker and Homebrew are skipped there by
> design.

## :broom: Tear Down

```zsh
uv run ft infra aws-test-fleet destroy
```

`destroy` also removes the fleet hosts from `hosts.toml`. It touches only
targets named `dev-fortress-fleet-*` that use the fleet key, and if nothing
else is left it removes the file, so `ft` falls back to the repo example.

Switching sets replaces hosts whose names are not in the new set: going from
`full` back to `lts` keeps the two Ubuntu 26.04 hosts and destroys the other
seven.

> [!WARNING]
> Every host bills until you destroy it, including its root volume. On demand
> in `ap-southeast-1` (October 2026 list prices: `m8i.large` US$0.1323 and
> `m8g.large` US$0.1122 an hour), the `lts` pair costs about US$0.24 an hour
> and the nine-host `full` set about US$1.11 an hour; Spot is cheaper. A
> forgotten fleet still adds up, so destroy it as soon as the checks finish.

## :moneybag: Capacity

Hosts are one-time Spot requests by default, which AWS can reclaim at any time.
When Spot capacity is short, or a check must not be interrupted, use on-demand
instead:

```zsh
TF_VAR_enable_spot=false uv run ft infra aws-test-fleet apply
```

The fleet does not read the single-host stack's `capacity.auto.tfvars.json`.
