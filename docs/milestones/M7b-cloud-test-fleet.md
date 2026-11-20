# M7b Cloud Test Fleet

## Status

- [x] Milestone complete (squash-merged in PR #6, `d13837a`, 2026-10-19)
- [ ] Active milestone

## Objective

Verify Dev Fortress on several fresh supported OS targets at once with one
cheap, short-lived EC2 fleet: one apply to create it, one destroy to remove it.

> [!NOTE]
> From 2026-10-19, routine verification runs on the operator's `dev-fortress`
> WSL2 host (the brownfield case) and on disposable EC2 hosts (fresh hosts).
> Throwaway WSL2 distros are retired: they load the workstation, and stopping
> one wipes `WSLInterop` for every distro.
>
> Decided 2026-10-19: everyday spot checks use the `lts` set, the current
> Ubuntu LTS on amd64 and arm64, the most common use case. The `full` set,
> every OS target on both architectures, runs at major milestones.

## Exit Criteria

- [x] One `terraform apply` creates a fleet set below, and one
  `terraform destroy` removes all of it (2026-10-19: the nine-host `full`
  destroy left no instances, key pairs, security groups, or IAM roles, and
  removed the fleet targets from `hosts.toml`)
- [x] `ft` imports every fleet host as a host target, with its SSH user, key,
  and trust state, without hand-editing `hosts.toml`
- [x] Each target runs its documented check and a second run reports
  `changed=0`, or the gap is recorded as a finding (first fleet run,
  2026-10-19)
- [x] The single-host `infra/aws-disposable-ubuntu/` stack keeps working
  unchanged for one-off hosts (its plan matches `main` resource for resource;
  only the per-resource tags moved off provider defaults, 2026-10-19)
- [x] The fleet run, its cost shape, and its teardown are documented, so a run
  needs no tribal knowledge (`infra/aws-test-fleet/README.md`)

## Fleet

The fleet comes in named sets (`infra/aws-test-fleet/locals.tf`), chosen with
`ft infra aws-test-fleet plan|apply --set <name>` and saved for later runs:

| Set | Hosts | Use |
| --- | --- | --- |
| `lts` (default) | Ubuntu 26.04 on amd64 and arm64 | everyday spot checks |
| `full` | Ubuntu 24.04, 26.04, and 26.10, and Alpine 3.24, each on amd64 and arm64, plus Arch on amd64 | major milestones |

amd64 hosts run on `m8i.large` and arm64 hosts on `m8g.large`, matched shapes
(2 vCPU, 8 GiB), so each architecture mirrors the other. Arch Linux publishes
no arm64 image, so Arch has no arm64 mirror.

| Target | AMI source | Check |
| --- | --- | --- |
| Ubuntu | Canonical SSM parameter | the one-liner on the box, then a re-run |
| Arch Linux | private AMI from `infra/aws-arch-ami/` | `ft host validate` over SSH, then a re-run |
| Alpine 3.24 | official Alpine cloud-init AMI (owner `538276064493`) | `ft host validate` over SSH, then a re-run |

Arch and Alpine use the SSH path because the one-liner's host mode supports
Ubuntu only.

Checked on 2026-10-19 in `ap-southeast-1`: Canonical publishes 24.04, 26.04,
and 26.10 for both architectures, Alpine publishes 3.24.2 cloud-init AMIs for
both, and `m8g.large` and `m8i.large` are both offered.

## Non-Goals

- [ ] Running the fleet from CI; the operator runs the gated `apply` and
  `destroy`
- [ ] Long-lived hosts; the fleet lives for one verification pass
- [ ] Public community Arch AMIs; Arch keeps the signed arch-boxes import
- [ ] Arch on arm64
- [ ] Making Alpine or Arch one-liner (host mode) targets

## Issue Drafts

### `M7b-1` Fleet Terraform root

- [x] Problem: the disposable host stack holds one host per state, so a second
  host name replaces the first
- [x] Scope: add `infra/aws-test-fleet/`, which calls the existing host stack
  as a module with `for_each` over a typed hosts map (name, OS, release,
  architecture, instance type). Move provider configuration out of the reused
  stack if `for_each` on the module requires it, without changing its
  single-host behavior. Default to Spot with the documented on-demand
  fallback shape. The resources moved into `infra/modules/disposable-host/`
  (a module with a provider block cannot take `for_each`), with `moved` blocks
  for applied single hosts. The fleet shares one managed SSH key and detects
  the SSH ingress IP once
- [x] Acceptance: `terraform plan` shows five hosts; `terraform fmt` and
  `terraform validate` pass for both roots. Verified 2026-10-19: without
  `arch`, the plan has 21 resources for four hosts; with it, the plan stops
  with "Build the private Arch AMI with infra/aws-arch-ami first", because
  that AMI is not registered yet

### `M7b-2` Alpine OS profile

- [x] Problem: the OS profile map has `ubuntu` and `arch` only
- [x] Scope: add an `alpine` profile with its cloud-init login user, no SSM
  agent, and an architecture-aware AMI name pattern that excludes the `metal`
  and `uefi` variants. A new optional `ami_name_regex` profile field does the
  excluding, and the AMI lookup moved to `aws_ami_ids` so a missing image
  fails with an actionable message
- [x] Acceptance: the plan resolves the latest Alpine 3.24 AMI for arm64 and
  amd64: `alpine-3.24.2-aarch64-cloudinit-r2` and
  `alpine-3.24.2-x86_64-cloudinit-r2` on 2026-10-19

### `M7b-3` Fleet import into `ft`

- [x] Problem: `ft host import-terraform` and the infra commands assume one
  host
- [x] Scope: import every fleet output as a host target with its managed SSH
  key and known-hosts entry, and remove them on teardown. `ft infra
  aws-test-fleet plan|apply|destroy` forwards to the single-host commands
  with the fleet's directory, seed file, and key name; import already
  handled several `[[targets]]` blocks. Removal on teardown is deferred: the
  next apply overwrites the same names
- [x] Acceptance: `ft host list` shows all five, and `ft host doctor <name>
  --probe` passes for each (`ft host doctor 'dev-fortress-fleet-*' --probe`,
  2026-10-19)

### `M7b-4` First fleet run

- [x] Problem: `M5b` was verified on WSL2 and one arm64 EC2 host only
- [x] Scope: run each target's check from the fleet table, record results and
  findings here, then destroy the fleet
- [x] Acceptance: every row has a recorded result; Alpine host-role gaps found
  on its first real VM become issues or fixes

### `M7b-5` Fleet sets and amd64 mirrors

- [x] Problem: the first fleet had each OS on one architecture only, and every
  run used the whole fleet
- [x] Scope: named `lts` and `full` sets, one instance type per architecture
  as matched shapes, names that carry the architecture, a saved `--set`
  choice, and pruning of fleet targets the fleet no longer has on apply and
  destroy. IAM name prefixes are cut to AWS's 38-character limit for the
  longer names
- [x] Acceptance: `full` creates nine hosts, every check passes on both
  architectures, and `lts` keeps the two Ubuntu 26.04 hosts. The apply from
  the five-host fleet replaced all five with the nine `full` hosts and pruned
  the old names from `hosts.toml`; every check passed after one Arch fix
  (2026-10-19, below). The `lts` names are shared with `full` by design

### `M7b-6` `ft infra aws-test-fleet check`

- [x] Problem: every fleet run needed hand-written shell scripts for SSH,
  parallelism, logs, and judging results, which is exactly the tribal
  knowledge this milestone exists to remove
- [x] Scope: one command that plans each host's check from the fleet outputs
  (the one-liner twice on Ubuntu, `ft host validate` elsewhere), runs them in
  parallel with stdin detached, shows live progress, logs every step under
  `${XDG_STATE_HOME}/dev-container-fortress/fleet-runs/<time>/`, judges each
  step from its exit code and Ansible recaps, and prints a summary and an
  optional markdown table. `--ref` tests a pushed branch, fetched by commit
  SHA. `ft host ssh <target> -- <command>` came with it. The recap parser moved
  to `ft/recap.py` so both paths share it
- [x] Acceptance: one command checks the whole fleet and exits non-zero on any
  failure. Verified 2026-10-19 on the nine live `full` hosts with
  `--ref feat/m0007b-cloud-test-fleet`: all nine passed in 84 s on the
  already-converged hosts, and the Ubuntu hosts checked out the branch head
  `fcb6d01`

## Verification Notes

- [x] Fleet created and destroyed with one command each
- [x] Every target's check recorded

### First fleet run, 2026-10-19

The private Arch AMI was rebuilt first (`dev-fortress-arch-20261015.611680`),
then one apply created all five hosts as Spot instances in `ap-southeast-1`.
`ft host doctor 'dev-fortress-fleet-*' --probe` reached all five with the
shared key. The Ubuntu hosts ran the published `main` one-liner over plain SSH
without a terminal; Arch and Alpine ran `ft host validate` from the operator's
WSL2 host.

| Host | Check | Result |
| --- | --- | --- |
| Ubuntu 24.04, amd64, `m8i.large` | one-liner, then again | ✅ 5 min 25 s, `changed=26`; re-run 32 s, `changed=0` |
| Ubuntu 26.04, arm64, `m8g.large` | one-liner, then again | ✅ 6 min 33 s, `changed=26`; re-run 39 s, `changed=0` |
| Ubuntu 26.10, arm64, `m8g.large` | one-liner, then again | ✅ 5 min 54 s, `changed=26`; re-run 33 s, `changed=0` |
| Arch, amd64, `m8i.large` | `ft host validate` | ✅ 2 min 48 s: check pass, `changed=18`, then `changed=0` |
| Alpine 3.24, arm64, `m8g.large` | `ft host validate` | ❌ then ✅: `sudo: not found`; after the fix, 61 s: check pass, `changed=9`, then `changed=0` |

Every Ubuntu host then had zsh as the login shell, `ft`, Homebrew `7.0.9`,
working Docker, and the uv-managed Python `3.14.8`, including 24.04, whose
system Python is 3.12. Without a terminal, the identity step skipped and
printed the manual commands, as documented. No run showed an interpreter
discovery warning.

Alpine converges the base packages, `shell-config`, and zsh as the login
shell. Docker and Homebrew are skipped there by design: the Docker role covers
Ubuntu and Arch, and Linuxbrew covers Ubuntu.

### Full set run, 2026-10-19

All nine `full` hosts as Spot, checks started together, about 6½ minutes from
the first check to the last log line:

| Host | Check | Result |
| --- | --- | --- |
| Ubuntu 24.04 amd64 / arm64 | one-liner, then again | ✅ 5 min 30 s / 6 min 23 s, `changed=26`; re-run `changed=0` |
| Ubuntu 26.04 amd64 / arm64 | one-liner, then again | ✅ 5 min 24 s / 5 min 45 s, `changed=26`; re-run `changed=0` |
| Ubuntu 26.10 amd64 / arm64 | one-liner, then again | ✅ 5 min 33 s / 5 min 38 s, `changed=26`; re-run `changed=0` |
| Arch amd64 | `ft host validate` | ❌ then ✅: second pass `changed=1`; after the fix, every pass `changed=0` |
| Alpine 3.24 amd64 / arm64 | `ft host validate` | ✅ 50 s / 59 s: `changed=9`, then `changed=0` |

Found and fixed:

- Arch's full-upgrade task reported changed whenever pacman refreshed its sync
  database, and on a rolling release the mirror moves every few minutes, so a
  converged host could not reliably reach `changed=0`; the pacman log showed
  nothing upgraded on that pass. The task now counts only upgraded packages.
  The earlier five-host run passed by luck

### First five-host run, details

Found and fixed:

- Alpine's cloud image ships `doas`, not `sudo`, so every `become` task failed.
  A `host.yml` pre-task now looks for `sudo`, then `doas`, and switches to the
  `community.general.doas` become plugin on hosts with only `doas`, unless an
  explicit `ansible_become_method` is set

Found, not fixed:

- `ft host ssh` opens an interactive session only. Running a command on a
  fleet host needed plain `ssh` with the managed key and known-hosts file;
  a command passthrough would make fleet checks scriptable through `ft`
- two `ft host validate` runs started as background jobs of one shell failed
  with Ansible's "requires blocking IO on stdin". Detaching stdin
  (`< /dev/null`) fixed it; this is how the runs were launched, not a fleet
  problem

## Branch and Merge Plan

- [x] Start after the `M5b` PR is open: `feat/m0007b-cloud-test-fleet`
- [x] Squash-merge once the exit criteria are met (PR #6)
