# Infrastructure Layer

This directory is the Terraform-owned infrastructure boundary for Dev Fortress.

Its purpose is intentionally narrow:

- create and destroy disposable or repeatable host targets
- output the minimal operator data needed to join the existing `ft host ...`
  and Ansible workflow
- keep cloud-specific provisioning separate from host bootstrap and shell setup

It should not become the place where host convergence logic, shell bootstrap,
or application-specific provisioning lives.

## Responsibility Split

Use this boundary:

- Terraform in `infra/`: provision and destroy infrastructure, then output the
  facts needed to reach it
- `ft host ...`: manage host target shape, SSH keys, trust state, probe, and
  bootstrap handoff
- Ansible in `ansible/`: converge the target once it is reachable
- `shell-config`: own shell UX and profile behavior outside this repository

That means Terraform should stop at "reachable host target," not continue into
"fully configured developer environment."

## Early Scope

The first intended target under this directory is a disposable Ubuntu host,
likely EC2 Spot first.

The first pass should stay deliberately small:

- one Ubuntu VM
- one security boundary for SSH reachability
- one public address or DNS output
- one explicit SSH user contract
- one clear destroy path

Avoid broad AWS scaffolding in the first pass such as:

- bespoke VPC topologies
- Route53 automation
- VPN or hybrid networking
- app-specific infrastructure concerns

## Expected Handoff Contract

Terraform code in this directory should output only the data that the Dev
Fortress operator flow needs, for example:

- target name
- public IP or public DNS
- SSH user
- SSH port
- instance identifier
- region
- `ansible_python_interpreter` when it is known

That output can later be translated into a `hosts.toml` entry or a generated
host-target fragment.

## Directory Layout

Recommended shape:

- `infra/README.md`: repository-wide infra boundary and rules
- `infra/aws-disposable-ubuntu/`: first disposable Ubuntu cloud target

Keep each target directory self-contained and obvious to inspect.
Do not introduce a shared abstraction layer until at least two real target
implementations need the same contract.

## Tooling Expectations

Terraform work here should follow the repo guidance in:

- [AGENTS.md](/Users/timl/projects/github/GrndZero101/tboss/dev-container-fortress/AGENTS.md)
- [docs/architecture.md](/Users/timl/projects/github/GrndZero101/tboss/dev-container-fortress/docs/architecture.md)
- [docs/milestones/M4a-disposable-cloud-ubuntu-host-loop.md](/Users/timl/projects/github/GrndZero101/tboss/dev-container-fortress/docs/milestones/M4a-disposable-cloud-ubuntu-host-loop.md)

Minimum checks for meaningful Terraform changes:

- `terraform fmt`
- `terraform validate`

Add stronger tooling such as `tflint` later once the infra layer is stable
enough to justify the extra surface area.
