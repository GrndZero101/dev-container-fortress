# Architecture

## Layering

`dev-container-fortress` is a provisioning and packaging repository.

It should orchestrate:

- host installation
- container image creation
- VS Code devcontainer wrapping

It should not become the place where shell behavior is defined.

That responsibility belongs to the external `shell-config` repository.

## Tooling Split

### Host targets

Use:

- Ansible for orchestration
- Homebrew for packages and userland tools
- `tenv` for Terraform and OpenTofu version selection

Host automation should be designed as a convergent desired-state system rather
than as a one-shot bootstrap script.

That means repeated runs should safely move a host toward the intended Dev
Fortress baseline whether that host started as:

- a fresh machine
- a previously Dev Fortress-managed machine
- a manually prepared machine that is already broadly aligned

The goal is not to pretend that every workstation can be normalized perfectly.
The goal is to make drift visible, correction routine, and host state
reproducible enough that environments do not decay into bespoke snowflakes.

Recommended host-automation rules:

- prefer idempotent tasks that converge state over imperative setup sequences
- adopt pre-existing compatible host state when it matches policy
- make managed-versus-user-owned boundaries explicit
- keep reruns safe on already-configured hosts
- fail clearly when a host falls outside the supported convergence contract
- document carve-outs rather than hiding them in role logic

When implementing Ansible roles, prefer built-in Ansible modules over shell
commands or wrapper scripts whenever a built-in module can express the desired
state cleanly.

Use shell or command tasks only when:

- no suitable built-in module exists
- the external tool is itself the contract being exercised
- the task remains narrow, inspectable, and clearly justified in comments or docs

Avoid letting host provisioning drift into large opaque shell snippets that are
hard to reason about, hard to diff, and hard to rerun safely.

### Container targets

Use:

- Dockerfiles for image construction
- Python + `uv` for pinned userland tool installation
- `tenv` as the first packaged DevOps tool
- a non-root runtime user for interactive development
- `ft` as the long-term operator CLI for container lifecycle, validation, and future environment automation

See [Container Standards](./container-standards.md) for the current runtime
contract and design rules that Ubuntu and Alpine should follow.

### Devcontainer target

Use:

- the Docker target as the base
- VS Code metadata as a thin wrapper

## Operator CLI Direction

`ft` should evolve from a tool-installer CLI into the main Dev Fortress operator
surface for repeatable environment workflows.

That promotion should now be treated as the intended steady state:

- `ft` is the primary supported operator interface
- `just` remains only as a thin human-friendly shim while usage habits and docs settle
- lifecycle logic should continue moving into `ft`, not back into `just`

Recommended responsibility split:

- `ft`: durable orchestration logic, validation, structured output, and future agentic workflows
- `just`: short aliases and ergonomic entrypoints for humans
- small shell scripts: narrow bootstrap or staging helpers only when a shell script is clearly the lightest fit

Repo-owned shell completion should stay aligned with CLI ownership:

- Typer-based CLIs in this repo should generate their own completion artifacts
- generated artifacts should install into an XDG-managed runtime path such as `${XDG_DATA_HOME:-$HOME/.local/share}/dev-container-fortress/completions/zsh`
- `shell-config` should only discover and load that external completion directory when it exists

This keeps `shell-config` atomic and avoids committing cross-repo generated files.

### Command Structure Sketch

Recommended top-level shape:

- `ft tool ...`
- `ft container ...`
- `ft host ...`
- `ft devcontainer ...`
- `ft doctor ...`

The current `plan` and `install` commands should likely become:

- `ft tool plan`
- `ft tool install`

Short-term compatibility can be preserved while the grouped structure is being introduced.

### Container Command Group

The strongest next step is a dedicated `container` command group that can absorb
the current `just` and `scripts/test-container.zsh` workflow over time.

Recommended v1 commands:

- `ft container build <target>`
- `ft container up <target>`
- `ft container validate <target>`
- `ft container shell <target>`
- `ft container exec <target> -- <command...>`
- `ft container logs <target>`
- `ft container status [target]`
- `ft container down <target>`
- `ft container reset <target>`

Recommended target values:

- `ubuntu`
- `alpine`
- `all`

Target selection should evolve beyond fixed enum-style values and support a
shell-like matching model that feels natural to operators.

Recommended selector model:

- exact target names such as `ubuntu`
- shell-style wildcard patterns such as `alp*` or `*`
- a friendly `all` alias that maps to the full known target set

Implementation guidance:

- use Python's standard-library `fnmatch` style matching rather than regex
- resolve patterns only against the known supported targets
- keep the resolved target order deterministic
- fail clearly when no targets match

The `all` target should therefore be treated as a first-class operator
convenience in `ft`, even though the lighter `just` layer should stay simpler
and more explicit.

Recommended `all` behavior:

- expand to the known supported targets in deterministic order
- render per-target progress clearly
- fail the overall command if any target fails
- remain compatible with future JSON and structured output

Good early candidates for `all` support:

- `ft container build all`
- `ft container up all`
- `ft container validate all`
- `ft container down all`
- `ft container reset all`

Good early examples of wildcard selection:

- `ft container build 'alp*'`
- `ft container validate 'u*'`
- `ft container status '*'`

Short-term recommendation:

- keep `just test-build ubuntu` and similar commands
- have them delegate to `ft container ...` once that command group exists
- avoid adding more orchestration logic to `just`

### Validation and Agentic Use

The `ft` CLI should be designed for both:

- humans running day-to-day validation and lifecycle commands
- agentic operators that need deterministic exit codes and machine-readable data

That means `ft` should gain:

- clear exit codes
- stable target naming
- structured validation output
- optional JSON output for machine consumption
- concise human-readable default output
- multi-target aggregation that still reports per-target results clearly

Recommended future command:

- `ft container validate <target> --json`

### Help UX

The help experience should be intentionally strong because this CLI is meant to
serve both human operators and future AI-driven operators.

Design rules:

- when no arguments are passed, the root CLI should print help rather than erroring
- when no arguments are passed to a subcommand group, that subcommand should also print help
- use Typer's `no_args_is_help=True` behavior at both the root and grouped command levels
- write descriptive help text that explains purpose, not just syntax
- prefer command names that describe intent clearly rather than short abbreviations
- treat help text as operational UX, not boilerplate

Help text should answer:

- what the command is for
- when to use it
- what target names mean
- whether the command is intended for humans, automation, or both
- what side effects to expect

### CLI First, TUI Ready

`ft` should be designed as a first-class CLI first, while leaving room for
future TUI workflows.

That means:

- every core operation must remain usable from the plain CLI
- automation and agentic workflows must not depend on a TUI being present
- TUI capabilities should layer on top of the same underlying command and data model
- rendering should stay separate from execution logic where practical

Future interactive directions may include:

- a higher-level `ft tui` entrypoint
- focused interactive pickers for targets, validation results, or logs
- `fzf`-style lightweight selection flows
- richer Textual-style operator dashboards once the command model is stable

The important design rule is:

- no business-critical workflow should exist only in the TUI layer
- the CLI remains the operational source of truth

### Migration Direction

Recommended phased path:

1. Keep the current shell-script and `just` workflow working.
2. Add the grouped `ft` commands with equivalent behavior.
3. Update `just` to delegate to `ft`.
4. Add JSON output and richer diagnostics where useful.
5. Reassess whether `scripts/test-container.zsh` still needs to exist.

## Remote Target Foundation

The next major Dev Fortress frontier should be a remote-target control plane built
around SSH first, then Ansible, then broader workstation and cloud provisioning.

That ordering matters:

- SSH is the common transport primitive across disposable cloud hosts, SSH-enabled containers, and future workstation-style targets
- Ansible depends on a stable transport and inventory model
- Terraform-backed or workstation-style provisioning should plug into that same target model rather than inventing a second control path

### Target Model

A Dev Fortress target should eventually be treated as a named SSH-reachable unit
of execution rather than as a special-case cloud or workstation concept.

Recommended baseline fields:

- target name
- host or address
- SSH user
- authentication method
- target kind such as `docker`, `cloud`, or `workstation`
- optional tags for grouping and selection

This keeps the operator model simple:

- create or discover a target
- reach it with SSH
- apply configuration with Ansible
- validate it with `ft`

### SSH Contract

Dev Fortress should define a small, explicit SSH contract before investing in
heavier host provisioning.

That contract should cover:

- where Dev Fortress-managed keys live
- how disposable versus long-lived keys differ
- host alias naming conventions
- host key and known-host handling for ephemeral targets
- what parts of the flow are safe for automation versus intended for humans

The practical design goal is:

- a target should become reachable in a deterministic way before Ansible or higher-level provisioning logic tries to touch it

### Ansible Contract

Once SSH reachability is stable, Ansible should layer on top of the same target
model instead of inventing host-specific assumptions.

Recommended first responsibilities:

- base machine bootstrap
- Python and package prerequisites
- userland install prerequisites
- shell-config bootstrap handoff
- validation-oriented facts or outputs where useful

Early Ansible work should stay intentionally thin.
The first goal is not to fully realize workstation provisioning, but to prove
that Dev Fortress can consistently reach and bootstrap a target through the same
operator surface.

### Terraform and Cloud Targets

Terraform should be treated as a future target-creation layer rather than the
first required step.

When cloud targets are introduced, Terraform should output the minimal operator
data needed to join the same SSH and Ansible workflow, for example:

- public IP or DNS name
- SSH user
- instance identifier
- target name or inventory fragment

That keeps Terraform useful without making the whole remote-target model depend
on cloud-specific assumptions.

Recommended early Terraform rules:

- keep Terraform focused on provisioning and teardown, not host bootstrap
- start with the smallest disposable infrastructure that proves the operator loop
- prefer official providers and native resources over wrapper shell glue
- prefer well-maintained `terraform-aws-modules` public registry modules when they clearly reduce boilerplate without obscuring the workflow
- keep spot-selection helpers optional behind a fixed fallback instance shape
- optimize for cheap, replaceable hosts with strong tagging and obvious cleanup
- make state, credentials, and teardown expectations explicit in docs before broadening the infra layer

### Operator CLI Direction for Hosts

The long-term CLI should reflect this layering explicitly.
A likely future direction is:

- `ft host ...` for reachability, inventory, and provisioning workflows
- `ft infra ...` only if Terraform-backed host creation becomes a first-class concern

Recommended early focus is still the host surface, not the infra surface.
That keeps Dev Fortress centered on reachable developer environments rather than
on provider-specific provisioning first.

### Recommended Sequence

The recommended implementation order is:

1. define the target model
2. define the SSH contract and key workflow
3. define the Ansible inventory and bootstrap contract
4. add the thinnest viable remote target path
5. expand into cloud-created or workstation-style targets later

This sequence should apply even if the first serious remote targets are Docker
containers with SSH enabled, because the design value comes from proving the
transport and bootstrap model before the infrastructure story gets broader.

## Rationale

- Ansible gives idempotent machine provisioning.
- SSH is the common transport boundary that should be stabilized before broader provisioning logic.
- Brew reduces maintenance burden on real machines.
- Containers benefit from pinned binary installs more than Brew.
- Running the final container as a non-root user keeps devcontainer behavior closer to a workstation.
- `tenv` keeps Terraform and OpenTofu version management out of the base image design.
- Keeping `shell-config` separate preserves modularity and reuse.
- A Python operator CLI is a better fit than layered shell logic once workflows need validation, portability, and structured machine-readable behavior.
