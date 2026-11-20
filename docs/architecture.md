# Architecture

## Layering

`dev-container-fortress` is a provisioning and packaging repository.

It should orchestrate:

- host installation
- container image creation
- VS Code devcontainer wrapping

It should not become the place where shell behavior is defined.

That responsibility belongs to the external `shell-config` repository.

> [!NOTE]
> tmux profiles are the one terminal-UX exception. Dev Fortress installs stock
> tmux and offers opt-in `minimal`, `full`, and `raidboss` profiles, because a
> working multiplexer setup belongs to the provisioned workstation and should
> not depend on the separate `dotfiles` repo. They are pick-one bootstrap
> options (`tmux-*`), installed by the `dev_fortress_tmux` role. Switching
> afterwards belongs to `csm tmux-profile` in `shell-config`; the two repos
> share only the profiles directory and the one `tmux.conf` link. See `M5b`.

## Tooling Split

### Host targets

Use:

- Ansible for orchestration
- Homebrew for preferred packages and userland tools after the host has crossed
  the minimal bootstrap boundary
- `tenv` for Terraform and OpenTofu version selection

Host-side policy should stay explicit:

- Ansible converges and validates host state
- Homebrew is the preferred steady-state source of host userland tools across
  macOS and supported Linux host targets such as Ubuntu, WSL2, and EC2 Ubuntu
- minimal native package-manager usage is allowed for bootstrap-floor
  prerequisites such as Docker Engine or basic transport dependencies
- host-oriented tool decisions should not drift into per-tool ad hoc installer
  logic when a Homebrew-backed steady state exists

> [!NOTE]
> Claude Code is a deliberate exception. Its native installer is the supported
> path that keeps it updating itself between bootstrap runs, so the host role
> runs that installer once and then leaves updates to Claude Code. Containers
> follow the same rule: when the option is selected, `ft workspace up` and the
> devcontainers run the installer through `ft-ensure-claude-code`, and keep its
> versions on a persisted mount so self-updates survive container replacement.

Large extras such as agentic coding tools are optional components rather than
baseline. `ft` owns the selection (`--options`, `DEV_CONTAINER_FORTRESS_OPTIONS`,
the XDG `options.toml`, or the `ft options pick` checkbox list) and renders one
boolean inventory variable per option; each role only reads its variable. The
default selection is empty.

A host converges in one of two modes, which `ft host bootstrap --mode` renders
as one inventory variable. `host`, the default, is the full workstation.
`workspace` stops at the bootstrap floor plus Docker and puts the toolchain in
a daily-driver workspace container instead, so it skips `shell-config`,
Homebrew, and the optional components. Both modes run the same playbook, so a
thin host becomes a full one with a re-run in `host` mode.

> [!NOTE]
> Arch Linux hosts are a deliberate exception. The official Arch repositories
> already ship the steady-state toolchain, so Arch hosts use pacman and skip
> Linuxbrew rather than running two package managers side by side. Arch host
> support is x86_64 only.

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
- keep minimal native bootstrap prerequisites separate from the later
  Homebrew-preferred steady-state toolchain
- validate `shell-config` first on a minimally prepared host so shell-level
  assumptions are visible before richer userland tooling is added

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

Container-side policy should stay separate from the host story:

- the glibc container targets (Ubuntu, Arch) install userland tools from
  Homebrew, using the same tool-pool set as the hosts, so hosts and containers
  share one toolchain
- the Homebrew prefix lives on a per-workspace named Docker volume, which
  `ft-brew-floor` brings up to the tool-pool floor on every start; ad hoc
  `brew install`s survive container replacement
- images are built warm (floor baked in, seeding a fresh volume in seconds) or
  cold (empty prefix, installed on first start); CI publishes cold images
- `uv` and Claude Code stay on their native installers everywhere
- the Alpine target keeps the `ft install` downloader, because Homebrew does
  not support musl; the `M5c` spike found no workable glibc compatibility path
- complex cryptographic substrate such as GnuPG and pinentry may use the base
  image package manager for now when distro integration matters
- that exception should stay narrow, documented, and validated by command
  checks; it should not become a general escape hatch for normal userland tools

Homebrew is the preferred path for steady-state tooling on hosts and on the
glibc container targets. For container targets, the base image package manager
stays acceptable for GPG-class substrate.

See [Container Standards](./container-standards.md) for the current runtime
contract and design rules that Ubuntu, Alpine, and Arch should follow.

### Devcontainer target

Use:

- the Docker target as the base
- VS Code metadata as a thin wrapper
- a bind mount of the host checkout or a named volume for the code, with a
  recommended default per use case in the
  [devcontainer usage guide](devcontainer-usage.md#getting-code-in)
- `gh` and `glab` logins on persisted volumes, with `/etc/gitconfig` routing
  HTTPS pushes through them, since `~/.gitconfig` does not persist
- generated definitions: `ft devcontainer render` writes every
  `devcontainer.json`, and its `--check` runs in pre-commit and CI

### One definition, two runtimes

`ft workspace` and the devcontainers start the same images from one shared
definition in [`ft/src/ft/container_runtime.py`](../ft/src/ft/container_runtime.py):
the persisted mounts and their container paths, which apply to Homebrew
targets only, the start steps (`ft-brew-floor`, `ft-ensure-claude-code`), and
each option's mounts and environment. The renderer adds the build-arg defaults
from the target Dockerfiles. Adding a persisted mount is one edit plus a
render.

The two runtimes stay separate on purpose. Having `ft workspace` drive the
devcontainer CLI was measured in the `M5c-5` spike and rejected:

- `ft workspace` replaces a container in about 1 s and runs a command in about
  0.3 s, against 7.4 s and 0.85 s through the devcontainer CLI, and needs no
  Node toolchain on hosts or the EC2 fleet
- it computes host integrations at start: the browser bridge broker, WSL
  interop mounts, the SSH agent socket, and option-dependent mounts. VS Code
  supplies its own browser, agent, and credential forwarding, and static JSON
  cannot branch on the host
- its state is host-owned bind mounts that `ft workspace auth` and `doctor`
  inspect, while devcontainer state is named volumes keyed per definition

Because a rendered definition cannot see the option selection, it mounts every
option's volumes and runs option-gated steps with `--if-selected`, which reads
`DEV_CONTAINER_FORTRESS_OPTIONS` inside the container.

> [!NOTE]
> The devcontainer CLI cuts a `${localEnv:VAR:default}` default at its first
> `:`. The renderer refuses such a default, leaves build args like
> `SHELL_CONFIG_REPO_URL` to the image's own fallback, and splits the volume
> flow's image into `DEV_FORTRESS_IMAGE_REPO` and `DEV_FORTRESS_IMAGE_TAG`.

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
- `arch` (amd64 only)
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
- keep reusable images separate from disposable hosts: `infra/aws-arch-ami/`
  imports the signed upstream Arch cloud image once as a private AMI, and the
  disposable host stack only looks it up through `os = "arch"`
- define one host once: `infra/modules/disposable-host/` holds the EC2 host,
  with no provider of its own, so the single-host root
  (`infra/aws-disposable-ubuntu/`) and the multi-OS verification fleet
  (`infra/aws-test-fleet/`, one module instance per OS target) share it. Both
  roots emit the same `host_target_toml_fragment` output, so `ft host
  import-terraform` handles one host or a whole fleet the same way

### Operator CLI Direction for Hosts

The long-term CLI should reflect this layering explicitly.
A likely future direction is:

- `ft host ...` for reachability, inventory, and provisioning workflows
- `ft infra ...` for Terraform-backed host creation: `aws-disposable-ubuntu`
  for one host and `aws-test-fleet` for the verification fleet, both wrapping
  the same managed-key and import flow

The infra surface stays a thin wrapper; reachability and convergence remain on
the host surface.
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
