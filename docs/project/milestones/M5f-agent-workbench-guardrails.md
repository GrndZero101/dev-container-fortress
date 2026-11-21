# M5f Agent Workbench Guardrails

## Status

- [ ] Milestone complete
- [ ] Active milestone

## Objective

Make the `M5c` workbench safe and convenient for coding agents at the `full`
trust level: the container keeps the host filesystem out of an agent's reach,
credentials arrive through forwarded agents rather than key files, and Claude
Code runs with permission prompts bypassed behind a deny-list hook.

`M5c` shipped the workbench itself. These slices were planned there as
`M5c-8` and `M5c-9` and moved here on 2026-11-20 so `M5c` could merge. The
design, including what a `full` workbench protects and what it does not, is
recorded under "Agents in a Full Workbench" in the
[M5c file](M5c-composable-container-workspaces.md#agents-in-a-full-workbench).

## Exit Criteria

- [ ] What a `full` workbench protects, and what it does not, is recorded in `docs/design/container-standards.md` and `docs/design/architecture.md`
- [ ] Rendered definitions meet the filesystem guardrails, and `--check` enforces them: no container-runtime socket, no host home or `/mnt/c` mount, no `--privileged`, and no host network
- [ ] SSH works inside a workbench through a forwarded agent, including the 1Password SSH agent on the host, with no private key files mounted, from VS Code and from CLI terminal mode
- [ ] Claude Code starts with permission prompts bypassed in a workbench where it is selected, and a deny-list hook blocks the listed catastrophic commands

## Non-Goals

- [ ] Protecting the accounts that a workbench's credentials can reach; that is the `sealed` level in [`M5d`](M5d-sealed-agent-workbench.md)
- [ ] Defending against a container or kernel escape exploit; the boundary is standard Docker isolation

## Issue Drafts

### M5f-1 Filesystem guardrails and credential model (was `M5c-8`)

- [ ] Problem: nothing guarantees that a workbench keeps the host filesystem out of an agent's reach, and SSH and 1Password access inside containers is ad hoc
- [ ] Scope: the filesystem guardrails, enforced by the renderer and `--check`; `http`/`https`-only validation in `ft.browser_bridge`, then the bridge in the devcontainers for CLI terminal mode; SSH through a forwarded agent in VS Code and CLI terminal mode, including the 1Password agent on Linux and WSL2 hosts; SSH commit signing; `op` through a service-account token; a non-production default `AWS_PROFILE`; and the "what it protects" table recorded in `docs/design/container-standards.md` and `docs/design/architecture.md`
- [ ] Acceptance: `--check` fails on a definition with any forbidden mount, socket, privilege, or host network; inside a workbench, `ssh -T git@github.com`, a signed commit, and an `op read` work with no key files present; the browser bridge rejects a non-URL payload

### M5f-2 Claude Code bypass mode and deny list (was `M5c-9`)

- [ ] Problem: running Claude Code with bypassed permissions is a per-session flag today, with no backstop
- [ ] Scope: confirm the managed settings path and keys and that hooks apply in bypass mode; ship the bypass default for workbenches and the `PreToolUse` deny-list hook in the image, with the list kept as data
- [ ] Acceptance: `claude` starts in bypass mode without a flag in a workbench and keeps prompting in `ft workspace`; each deny-listed command is blocked

## Verification Notes

- [ ] Filesystem checks from inside a workbench, as an agent would try them:
  - [ ] no container-runtime socket exists, and `docker ps` against the host fails
  - [ ] the host home directory, `/mnt/c`, and host checkouts outside `repos/` are not reachable
  - [ ] `ls ~/.ssh` shows no private keys, while `ssh-add -l` lists the forwarded keys
  - [ ] a non-URL payload sent to the browser bridge is rejected
- [ ] A real multi-hour Claude Code task in bypass mode in a workbench, delivered as a PR

## Open Questions

- [ ] Does a workbench need Docker inside it, and if so, which option: Docker-in-Docker, rootless, or Sysbox?
- [ ] Which stable SSH agent socket path should CLI terminal mode mount on Linux and on WSL2 hosts?

## Branch and Merge Plan

- [ ] Start after `M5c` merges
- [ ] Branch from `main` as `feat/m0005f-agent-workbench-guardrails`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Progress Notes

Split out of `M5c` on 2026-11-20 at the operator's request, so the workbench
could merge and the bare-metal developer run could use published images.
