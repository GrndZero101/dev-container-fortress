# General Implementation Guidance

* Use KISS, DRY, and YAGNI principles.
* Keep code clean, well-documented, and maintainable.
* Prefer small, composable changes over broad framework-heavy abstractions.
* Follow XDG standards for user-facing configuration where that applies.
* Review and update `README.md` whenever repository behavior, bootstrap flow, or supported targets change.

# Repository Intent

* This repository is for provisioning and packaging developer environments.
* Keep shell UX and shell behavior in the external `shell-config` repository rather than reimplementing them here.
* Prefer the thinnest layer that fits the job:
  * Ansible for host orchestration
  * Homebrew for host package bundles
  * Dockerfiles for container image construction
  * Python plus `uv` for pinned container-side userland tool installation
  * VS Code devcontainer metadata as a light wrapper around the container target
* Avoid introducing overlapping bootstrap paths unless there is a clear target-specific need.

# Python Guidance

* Use Python 3.14+.
* Prefer the standard library unless a dependency clearly reduces maintenance or improves correctness.
* Use `uv` for Python environment and dependency management.
* Keep Python utilities small, explicit, and oriented around provisioning tasks rather than general application architecture.
* Prefer simple typed data structures and straightforward parsing over framework-driven designs.
* If introducing a new Python dependency, document why it is needed in the relevant README or architecture docs when the reason is not obvious.
* all functions/classes/modules should have docstrings as we may want to document with Sphinx in the future. Should be in **google** style.

# Python Packages

* Prefer the following Python packages for the purposes outlined.

| Purpose         | Package        |
| --------------- | -------------- |
| API             | FastAPI        |
| CLI             | Typer, Rich    |
| data structures | Pydantic       |
| date/time       | pendulum       |
| logging         | loguru         |
| natural output  | humanize       |
| TUI             | Textual, Rich |
| SQL             | sqlmodel       |

# Python Tooling

* Use `UV` for Python project bootstrapping, package management and anything it can handle natively.
* Use `ruff` for linting. Configuration should be defined in `pyproject.toml`
* Use `rumdl` for markdown linting and formatting. Configuration should be defined in `pyproject.toml`

# Markdown Documents

* Use GitHub or GitLab admonition callouts where they improve clarity, especially for caveats, platform differences, and carve-outs.
* Use supported emoticons sparingly when they improve scanability without adding noise.
* Keep top-level documentation high-level and architectural.
* Keep component documentation operational and close to the relevant directory when practical.
* Update `docs/architecture.md` whenever layering, orchestration boundaries, or tool-selection strategy materially changes.
* Update `docs/container-standards.md` whenever significant container design choices change. Examples: XDG layout, runtime user model, bootstrap strategy, privilege model, or container tool-install contract.
* Update component README files when setup steps, supported targets, inputs, or outputs change.
* Update user-facing usage docs under `docs/` whenever features, supported flows, setup steps, or caveats change. Keep workstation, container, and devcontainer instructions in sync with the real implementation.

# Shell Script Guidance

* Shell code in this repository may use Zsh when it is clearly repo-owned bootstrap or helper logic intended for the managed developer environment.
* Do not assume every shell entrypoint in this repository can be Zsh-only if it may run under Docker, devcontainer hooks, CI, or other non-interactive execution contexts.
* When choosing shell for a script, prefer the narrowest compatible option required by where that script executes.
* For Zsh scripts, use a lightweight shell docblock style instead of Python-style docstrings.
* Add a short file header describing purpose and constraints.
* Add a concise comment block above each function covering:
  * purpose
  * arguments
  * returns
  * side effects when relevant
* Keep inline comments rare and focused on non-obvious shell behavior, safety checks, parser quirks, or important invariants.
* Review and update comments when the script behavior changes.
* Assume terminals may support Nerd Fonts and richer themes, but keep output concise and functional first.

# Ansible Guidance

* Keep playbooks and roles idempotent.
* Prefer declarative Ansible modules over shell commands when practical.
* Use shell or command tasks only when there is no clean module-based alternative.
* Keep host-specific behavior explicit and easy to audit.
* Document required variables, defaults, and assumptions near the relevant role or inventory files.
* Avoid embedding large amounts of business logic in YAML when a small helper script would be clearer and easier to test.

# Terraform Guidance

* Use Terraform for infrastructure lifecycle only, not as a substitute for host bootstrap or application configuration.
* Keep Terraform outputs focused on the minimal data needed to join the existing `ft host ...` and Ansible workflow.
* Prefer official providers, native resources, and clear module boundaries over wrapper scripts or over-abstracted local modules.
* Prefer well-maintained public registry modules from the `terraform-aws-modules` namespace when they fit the problem cleanly, but do not force a module when a few native resources would be simpler and easier to audit.
* Start with the smallest disposable infrastructure that proves the workflow. Avoid broad VPC, DNS, or multi-service sprawl in the first pass.
* Treat disposable cloud hosts as cattle, not pets. Optimize for cheap creation, clear tagging, and clean teardown.
* Keep cloud-specific assumptions explicit in variables and docs. Do not hide region, AMI, instance-shape, or SSH-user assumptions in opaque defaults.
* Prefer a fixed, documented fallback instance shape even if spot-selection helpers exist.
* Keep Terraform code readable and auditable: small files, clear locals, explicit variable types, and minimal magic.
* Run `terraform fmt` and `terraform validate` for every meaningful Terraform change. Add `tflint` later when the infra layer is stable enough to justify it.
* Document how Terraform state, credentials, and teardown are expected to work before expanding the infra surface.

# Container Guidance

* Keep Dockerfiles focused on reproducible builds and a clear layer structure.
* Use distro packages for low-level system prerequisites inside containers.
* Use Python plus `uv` tooling for pinned userland tool installation inside containers.
* Avoid introducing Homebrew into container targets unless explicitly requested.
* Prefer deterministic downloads, pinned versions, and checksum verification for externally fetched tools.
* Keep image size and build complexity in mind, but do not sacrifice auditability for minor optimizations.
* Treat `docs/container-standards.md` as the operational contract for container targets and keep it in sync with significant design changes.

# Devcontainer Guidance

* Treat `devcontainer/` as a thin VS Code integration layer over the container target.
* Keep devcontainer-specific customization scoped to editor integration, mounts, extensions, and post-create behavior.
* Do not duplicate core environment provisioning logic in `devcontainer.json` when it can live in the underlying container or bootstrap flow.

# Multi-Platform and Architecture Support

* Build explicit detection logic for:
  * macOS
  * Ubuntu
  * Alpine Linux
  * WSL where relevant
  * Intel and ARM architectures
* Keep platform branching centralized and easy to inspect.
* Prefer data-driven mappings for platform-specific package names, URLs, checksums, and installation rules.
* If a target is unsupported or partially supported, fail clearly and document the limitation.

# Bootstrapping

* Bootstrap flows must be idempotent or safely retryable.
* Bootstrap flows should support non-interactive execution by default.
* Keep bootstrap entrypoints small and delegate target-specific work to the appropriate layer:
  * host provisioning to Ansible and Brew
  * container provisioning to Dockerfiles and Python tooling
  * shell setup to `shell-config`
* For real hosts, treat native OS packages as the bootstrap substrate and Homebrew as the later preferred steady-state toolchain.
* Validate `shell-config` first on minimally prepared supported hosts before relying on Homebrew-managed tools to provide the richer operator experience.
* Allow the install location of `shell-config` to be user-configurable, but keep the default aligned with XDG conventions when possible.
* Validate prerequisites early and fail with actionable error messages.
* Do not silently continue after partial bootstrap failures that would leave the environment in an ambiguous state.
* Prefer explicit logging for major bootstrap phases so failures are easy to diagnose.
* Document bootstrap assumptions, required inputs, and side effects in the relevant README files.

# Change Management

* Keep changes scoped to the relevant layer instead of solving problems in multiple places.
* If a change affects architecture, bootstrap flow, supported targets, or directory responsibilities, update the corresponding documentation in the same change.
* When adding a new helper, script, or installer path, document why it belongs in this repository instead of `shell-config`.

# Dogfooding

* Prefer using Dev Fortress itself to develop and validate Dev Fortress whenever the capability already exists.
* Prefer `ft`, the documented bootstrap flow, and the documented verification loops over ad hoc manual commands when the operator surface is ready.
* If a workflow is painful when using the repo's own tools, treat that pain as product feedback instead of normalizing the workaround.
* If a capability does not exist and the manual path is noticeably taxing, suggest that gap as an opportunity to create or extend a milestone in `docs/ROADMAP.md`.

# Planning Workflow

* Treat `docs/ROADMAP.md` as the strategic roadmap and milestone ordering document.
* Treat `docs/milestones/` as the working planning surface for milestone drafts, issue slices, and checkbox progress.
* Keep one markdown file per milestone under `docs/milestones/`, and update it as work advances.
* Use milestone files as the copy/paste source for later GitHub milestones and issues.
* Name milestone branches after a zero-padded sortable milestone ID and outcome, for example `feat/m0003a-installer-onramp` or `feat/m0004-first-real-host-roles`.
* Keep the sortable branch ID mapped directly from the roadmap milestone ID, for example `M3a` -> `m0003a` and `M7a` -> `m0007a`.
* Prefer one feature branch per active milestone unless parallel human work requires smaller branches.
* Commit freely on the milestone branch at verified checkpoints.
* Squash-merge milestone branches once exit criteria in the milestone file are satisfied.
