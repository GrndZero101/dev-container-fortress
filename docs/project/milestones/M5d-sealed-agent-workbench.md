# M5d Sealed Agent Workbench

## Status

- [ ] Milestone complete
- [ ] Active milestone

## Objective

Add a `sealed` trust level to the `M5c` workbench, in which the container is a
credential and network boundary as well as a filesystem one. Coding agents can
then run with permission prompts bypassed on untrusted input without reaching
the operator's accounts.

The `M5c` `full` workbench protects the host filesystem but deliberately
carries the operator's credentials. `sealed` is for jobs where that is the
wrong trade. Examples: running an agent against a third-party repo, triaging
public issues, or any task that is mostly reading external content that could
carry prompt injection.

> [!NOTE]
> Build this when a concrete job needs it, not speculatively. An agent with no
> access to anything is far more limited, so `sealed` complements `full`
> rather than replacing it.

## Exit Criteria

- [ ] `workbench.toml` accepts `trust = "sealed"`, and `ft workbench` generates a sealed definition from it
- [ ] The sealed boundary contract (what stays outside) is recorded in `docs/design/container-standards.md` and `docs/design/architecture.md`
- [ ] A sealed workbench passes a start-up boundary check that fails on any forbidden host channel, credential, mount, privilege, or open egress
- [ ] Default-deny egress with a data-driven allowlist is active in sealed workbenches
- [ ] Claude Code runs with permission prompts bypassed in sealed workbenches
- [ ] The red-team checks in the verification notes pass from inside a sealed workbench

## Non-Goals

- [ ] Replacing or weakening the `full` workbench
- [ ] Defending against a container or kernel escape exploit; hardened runtimes such as gVisor, Kata, or Docker Enhanced Container Isolation stay out of scope unless a job needs them
- [ ] Preventing exfiltration of anything placed inside a sealed workbench; the design keeps valuable material out instead

## Design Direction

Drafted on 2026-11-20 as the first version of the `M5c` agent boundary, and
moved here when `M5c` chose the credentialed `full` workbench.

**An agent in bypass mode can do anything the container's user can do with
whatever is mounted, forwarded, or reachable over the network, including
sending it off the machine.** The rule for `sealed` follows from that: keep
anything valuable out of the agent's reach, rather than trying to stop the
agent once it has access.

### What Stays Outside a Sealed Workbench

Credentials:

- No `gnupg` or `password-store` mount, and no GPG agent forwarding. The `pass`
  store holds every secret, and a GPG agent can decrypt it.
- No SSH agent forwarding and no mounted `~/.ssh`. An agent cannot read a
  forwarded key, but it can use it to authenticate to every forge and host
  that trusts the key.
- No host `~/.aws` or `~/.azure`, no 1Password access, and no Docker registry
  credentials or credential helpers.
- No VS Code Git credential sharing or agent forwarding. Turn off each of these
  in the generated definition where a setting exists. Where one cannot be
  turned off, sealed workbenches are supported only through the devcontainer
  CLI.

Host mounts and host channels, in addition to the `M5c` filesystem
guardrails:

- No bind-mounted host checkouts. A writable checkout lets the agent plant code
  that runs on the host: `.git/hooks`, `.git/config` (`core.hooksPath`,
  `core.fsmonitor`, aliases), `.envrc`, `.vscode/tasks.json`, `justfile`,
  pre-commit config, and `.claude/settings.json` hooks. Sealed workbenches
  clone repos into a named volume, the `M5c-4` volume flow, and work leaves
  only by `git push` to a branch and a reviewed PR.
- No host browser bridge.
- An audit of what VS Code itself exposes: the `$BROWSER` helper, automatic
  port forwarding to host `localhost`, and workspace settings that host-side UI
  extensions read.

Network:

- A default-deny egress allowlist, installed when the container starts. It
  follows the pattern of Anthropic's reference Claude Code devcontainer: an
  init script run with `NET_ADMIN`, then dropped. The allowlist is
  data-driven: the Anthropic API, the forge hosts in `workbench.toml`, GHCR,
  Homebrew, PyPI and `uv`, npm, and anything else the user adds explicitly.
- The allowlist always blocks the Docker host gateway (`host.docker.internal`),
  RFC 1918 and link-local ranges, and the cloud metadata endpoint
  (`169.254.169.254`). Fleet hosts already require IMDSv2; keep the hop limit at
  1 so containers cannot reach the instance role.
- The allowlist reduces exfiltration; it does not prevent it. An agent can
  still push to an allowed forge, so forge tokens must be scoped.

Privileges:

- No blanket `NOPASSWD: ALL` sudo for the runtime user, because with it the
  agent can flush the firewall. Sealed images allow only the firewall init
  script. Homebrew owned by `vscode` (`M5c`) makes this workable, because ad
  hoc installs no longer need `sudo`.
- No extra capabilities after the firewall init, and `no-new-privileges` where
  it does not break the image.

### What Is Allowed Inside

Only credentials that are cheap to revoke and narrow in scope:

- a fine-grained GitHub token, or a GitLab project token, limited to the
  workbench's repos, with no admin rights; branch protection on the forge
  keeps `main` safe
- a per-workbench SSH signing key, revocable on its own, or unsigned commits
  that the operator squash-merges
- short-lived credentials for a sandbox cloud account, only when a task needs
  them
- Claude Code's own login; the agent can read its own token, so prefer a login
  or API key with a spend limit

### Boundary Check

`ft workbench doctor` runs at start-up in sealed workbenches and fails, rather
than warning, if any of the following is present:

- `SSH_AUTH_SOCK`, a GPG agent socket, or private keys in `~/.gnupg`
- `~/.password-store`, `~/.aws/credentials`, a host `~/.azure`, or Docker
  credentials
- a Git credential helper that points outside the container
- a container-runtime socket, or a bind mount from the host other than the
  allowed state paths
- unrestricted `sudo`
- egress to a non-allowlisted canary host, to the host gateway, or to
  `169.254.169.254`

The same check runs in CI against the generated sealed definition.

## Issue Drafts

### M5d-1 Sealed definition and boundary contract

- [ ] Problem: a workbench can only be generated with the operator's credentials
- [ ] Scope: `trust = "sealed"`; generated definitions with no credential mounts or forwarding, volume clones, and VS Code credential sharing turned off; an image variant or entrypoint without blanket `sudo`; the contract recorded in the container standards and architecture docs
- [ ] Acceptance: a generated sealed definition contains none of the forbidden mounts or forwarding

### M5d-2 Egress allowlist

- [ ] Problem: an agent with open egress can reach any host, the host gateway, the LAN, and cloud metadata
- [ ] Scope: an init-time firewall script, a data-driven allowlist, and a blocked list that always applies
- [ ] Acceptance: an allowed request succeeds; requests to a canary host, `host.docker.internal`, an RFC 1918 address, and `169.254.169.254` fail; `brew install`, `uv`, and `git push` still work

### M5d-3 Boundary check and VS Code audit

- [ ] Problem: a misconfigured sealed workbench would look the same as a correct one
- [ ] Scope: `ft workbench doctor`, run at start-up and in CI; an audit of the VS Code Dev Containers host channels, with each result recorded as disabled, accepted, or "CLI only"
- [ ] Acceptance: the doctor fails on each forbidden item when it is injected one at a time, and passes on a clean sealed workbench

## Verification Notes

- [ ] Red-team checks from inside a sealed workbench, as the agent would try them:
  - [ ] `ssh-add -l` and `gpg --list-secret-keys` find nothing
  - [ ] `git credential fill` for a non-workbench repo returns nothing
  - [ ] `sudo iptables -F` and `sudo -i` fail
  - [ ] egress to a canary host, the host gateway, the LAN, and IMDS fails
  - [ ] a direct push to a protected `main` is rejected by the forge
- [ ] A real Claude Code task on untrusted input in bypass mode, delivered as a PR

## Branch and Merge Plan

- [ ] Start after `M5c`, when a concrete job needs it
- [ ] Branch from `main` as `feat/m0005d-sealed-agent-workbench`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Progress Notes

Drafted on 2026-11-20 from the first version of the `M5c` agent boundary
design. Nothing is built yet.
