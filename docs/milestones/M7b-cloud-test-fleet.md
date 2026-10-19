# M7b Cloud Test Fleet

## Status

- [ ] Milestone complete
- [x] Active milestone, on `feat/m0007b-cloud-test-fleet` (started 2026-10-19, after `M5b` merged)

## Objective

Verify Dev Fortress on several fresh supported OS targets at once with one
cheap, short-lived EC2 fleet: one apply to create it, one destroy to remove it.

> [!NOTE]
> From 2026-10-19, routine verification runs on the operator's `dev-fortress`
> WSL2 host (the brownfield case) and on disposable EC2 hosts (fresh hosts).
> Throwaway WSL2 distros are retired: they load the workstation, and stopping
> one wipes `WSLInterop` for every distro.

## Exit Criteria

- [ ] One `terraform apply` creates the five-host fleet below, and one
  `terraform destroy` removes all of it (the apply created all five on
  2026-10-19; the destroy is still to run)
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

| Target | AMI source | Instance | Check |
| --- | --- | --- | --- |
| Ubuntu 24.04 | Canonical SSM parameter | `m8i.large` (amd64) | the one-liner on the box, then a re-run |
| Ubuntu 26.04 | Canonical SSM parameter | `m8g.large` (arm64) | the one-liner on the box, then a re-run |
| Ubuntu 26.10 | Canonical SSM parameter | `m8g.large` (arm64) | the one-liner on the box, then a re-run |
| Arch Linux | private AMI from `infra/aws-arch-ami/` | `m8i.large` (amd64 only) | `ft host bootstrap` over SSH, then a re-run |
| Alpine 3.24 | official Alpine cloud-init AMI (owner `538276064493`) | `m8g.large` (arm64) | `ft host bootstrap` over SSH, then a re-run |

The mix covers both CPU architectures. Arch and Alpine use the SSH path
because the one-liner's host mode supports Ubuntu only; checking that it fails
clearly there is part of the run.

Checked on 2026-10-19 in `ap-southeast-1`: Canonical publishes 24.04, 26.04,
and 26.10 for both architectures, Alpine publishes 3.24.2 cloud-init AMIs for
both, `m8g.large` and `m8i.large` are offered, and no private Arch AMI exists
any more, so the importer stack has to run again first.

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
- [ ] Scope: run each target's check from the fleet table, record results and
  findings here, then destroy the fleet (results recorded below; the destroy
  waits for the operator)
- [x] Acceptance: every row has a recorded result; Alpine host-role gaps found
  on its first real VM become issues or fixes

## Verification Notes

- [ ] Fleet created and destroyed with one command each
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

- [ ] Start after the `M5b` PR is open: `feat/m0007b-cloud-test-fleet`
- [ ] Squash-merge once the exit criteria are met
