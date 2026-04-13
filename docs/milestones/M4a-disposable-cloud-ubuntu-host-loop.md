# M4a Disposable Cloud Ubuntu Host Loop

## Status

- [ ] Milestone complete
- [x] Side-quest milestone in active validation

## Objective

Create the first Terraform-backed disposable Ubuntu host loop so Dev Fortress
can validate its SSH and Ansible convergence model against a real cloud VM.
The first pass should prioritize low-cost, low-friction testing, likely EC2
Spot first, while keeping the cloud layer narrow and disposable rather than
trying to become a full infrastructure control plane.

## Why This Exists

Disposable Docker SSH targets have now proven the convergent bootstrap model
locally. The next highest-value risk to burn down is real-host behavior:

- real host keys and managed trust state
- real SSH transport over the network
- real Ubuntu package convergence on a VM
- safe reruns against a host that is not a container artifact

This milestone exists to make that real-host loop cheap and repeatable enough
to use regularly.

## Design Principles

- [ ] Prefer a narrow disposable-host workflow over a broad general-purpose cloud framework
- [ ] Prefer cheap, replaceable Ubuntu hosts over long-lived snowflake test machines
- [ ] Keep Terraform responsible for infrastructure lifecycle
- [ ] Keep `ft host ...` responsible for SSH, inventory, probe, and bootstrap
- [ ] Keep the cloud target generated or templated into the existing host-target model instead of inventing a separate host contract
- [ ] Prefer convergent desired-state host automation over one-shot bootstrap scripts
- [ ] Prefer official providers and native Terraform resources over wrapper shell scripts
- [ ] Make teardown and cost visibility first-class so testing stays safe

## Lessons Reused from `minecraft-docker`

Useful ideas worth reusing:

- [ ] a cheapest-spot discovery step that exports machine-readable Terraform input
- [ ] Terraform-managed spot-host creation with an explicit SSH public key
- [ ] a clear operator flow of create host -> verify SSH -> run Ansible
- [ ] explicit handling for disposable-host SSH known-host churn

Things to improve this time:

- [ ] avoid project-specific AWS assumptions such as Route53, Minecraft naming, or bespoke VPC layout
- [ ] avoid large standalone Python scripts without tests or a stable CLI contract
- [ ] avoid shell-wrapper-heavy orchestration when Terraform, `ft`, or Ansible can own the behavior directly
- [ ] avoid coupling infrastructure creation with app-specific bootstrap concerns

## Exit Criteria

- [ ] Terraform code can create one disposable Ubuntu VM suitable for `ft host ...` testing
- [ ] The first target is cost-conscious and supports Spot where practical
- [ ] The operator can tear the target down cleanly after testing
- [ ] The disposable host can be represented in the Dev Fortress host target model without manual reinvention each run
- [ ] The documented workflow covers provision, target registration, managed SSH key usage, probe, bootstrap, verification, and teardown
- [ ] The workflow is validated end to end against at least one real Ubuntu VM
- [ ] Cost, interruption, and trust-state caveats are documented clearly

## Non-Goals

- [ ] Full multi-cloud support
- [ ] Complex VPC topologies, VPNs, or Route53 automation in the first pass
- [ ] Full workstation fleet management
- [ ] Auto-healing spot interruption recovery in the first pass
- [ ] Broad cloud CRUD inside `ft` before the Terraform boundary is clear

## Issue Drafts

### M4a-1 Define infra boundary and directory layout

- [x] Problem: Dev Fortress has host automation, but no repo-owned infra layer for disposable real VMs yet
- [x] Scope: decide where Terraform lives, how it is invoked, and how it hands off to the host-target model
- [x] Acceptance: infra layout is documented
- [x] Acceptance: `ft host ...` versus Terraform responsibilities are explicit
- [x] Acceptance: the first cloud loop does not require app-specific glue

### M4a-2 Create first disposable Ubuntu Spot host plan

- [x] Problem: there is no repeatable cheap real-host target to test against
- [x] Scope: add Terraform for one Ubuntu VM, likely EC2 Spot first
- [x] Acceptance: one command sequence can provision the host
- [ ] Acceptance: one command sequence can destroy the host
- [x] Acceptance: tags and naming make disposable test hosts easy to identify
- [x] Acceptance: SSH access uses a Dev Fortress-managed or operator-supplied public key cleanly

### M4a-3 Add spot-selection helper with a stable contract

- [ ] Problem: cheapest-instance logic is useful, but it should not live as an unstructured one-off script
- [ ] Scope: define a small machine-readable contract for spot selection inputs and outputs
- [ ] Acceptance: the chosen instance type and AZ can be exported into Terraform variables cleanly
- [ ] Acceptance: pricing selection is constrained by minimum CPU, memory, architecture, and max price
- [ ] Acceptance: the helper is documented and testable
- [ ] Acceptance: the first pass still supports a fixed fallback instance type when spot analysis is skipped

### M4a-4 Generate or template host-target registration

- [x] Problem: a cloud VM is not useful until it can flow into `ft host doctor` and `ft host bootstrap`
- [x] Scope: generate or template a host-target entry from Terraform outputs
- [x] Acceptance: the operator does not need to handcraft the entire host definition after each provision
- [x] Acceptance: generated data aligns with the existing `hosts.toml` schema
- [x] Acceptance: the Ubuntu cloud target can run through probe and bootstrap with minimal manual translation

### M4a-5 Document the disposable cloud host loop

- [x] Problem: real-host testing becomes brittle if the operator sequence is tribal knowledge
- [x] Scope: document provision, target registration, SSH trust handling, probe, bootstrap, rerun, and teardown
- [x] Acceptance: one operator-facing doc covers the full lifecycle
- [x] Acceptance: teardown and cost hygiene are called out explicitly
- [x] Acceptance: the path is clearly framed as disposable host validation, not full workstation automation

## Verification Notes

- [x] Terraform formatting and validation pass
- [x] The chosen cloud target can be provisioned successfully
- [x] `uv run ft host doctor <target> --probe` passes against the real VM
- [x] `uv run ft host bootstrap <target> --check` passes against the real VM
- [x] `uv run ft host bootstrap <target>` passes against the real VM
- [x] A rerun converges with little or no change
- [ ] The host can be destroyed cleanly afterward

## Captured Outcome

What is now proven:

- Terraform can provision a disposable Ubuntu EC2 target using the repo-owned
  `infra/aws-disposable-ubuntu/` stack
- Terraform outputs can be copied directly into the existing `hosts.toml`
  target model without inventing a second contract
- `ft host doctor --probe` and `ft host bootstrap` work against a real Ubuntu
  VM, not only disposable Docker SSH targets
- the managed known-hosts flow now covers `kind = "cloud"` targets as well as
  disposable Docker targets
- AWS Systems Manager Session Manager access works for the disposable host using
  an IAM role and instance profile with `AmazonSSMManagedInstanceCore`

What remains before this milestone can be closed cleanly:

- validate `terraform destroy` on the currently live AWS account after the host
  is no longer needed
- decide whether cheapest-instance or Spot-selection logic belongs in this
  milestone or should remain a follow-on helper milestone

## Branch and Merge Plan

- [ ] Branch from `main` as `feat/m0004a-disposable-cloud-ubuntu-host-loop`
- [ ] Commit freely at verified checkpoints
- [ ] Open one PR for the side-quest once the exit criteria are met
- [ ] Squash merge into `main`
