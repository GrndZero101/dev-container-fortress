# M5c Composable Container Workspaces

## Status

- [ ] Milestone complete
- [ ] Active milestone

## Objective

Make the container targets long-lived, composable development environments
that work like a traditional workstation, rather than tightly pinned build
artifacts. Standardize their userland on Homebrew, the same toolchain the host
targets use, and make the VS Code devcontainer and the devcontainer CLI
genuinely useful for daily development.

These environments may be disposable, but they are expected to last days,
months, or years. They need to be quick to compose and safe to grow at will.
They do not need to be byte-for-byte deterministic.

## Target Use Cases

Dev Fortress serves four use cases. `M5b` owns the first two and this
milestone owns the last two:

1. a new or existing Ubuntu install on a direct host, whether physical, virtual,
   or cloud (`M5b`)
2. a new or existing WSL2 Ubuntu install on a Windows host (`M5b`)
3. a VS Code devcontainer, or the devcontainer CLI driven by an editor, with a
   clear answer for how the code gets in (`M5c`)
4. a devcontainer CLI "terminal mode" in which the container itself is the dev
   environment, with no editor attached (`M5c`)

## Exit Criteria

- [ ] The container images install their userland tools through Homebrew, with the same bundle model as the host targets, and the decision is recorded in `docs/architecture.md` and `docs/container-standards.md`
- [ ] Tools added inside a running container with `brew install` persist across container replacement where that is intended, or the docs state clearly that they do not
- [ ] Claude Code is installed by default in every container target through its native installer and can update itself in place
- [ ] The devcontainer documents and supports one recommended way to get code in, either a bind mount of the host checkout or a clone into a volume, and the other way works as a documented variant
- [ ] A devcontainer CLI terminal mode works end to end: `up`, enter a shell, develop, commit, push, and come back later to the same state
- [ ] `ft workspace` and the devcontainer CLI either share one definition or have a documented reason to differ, so there are no two overlapping container paths

## Non-Goals

- [ ] Byte-for-byte reproducible image builds
- [ ] Dropping the distro package manager for low-level system prerequisites
- [ ] New container distros

## Design Direction

### Homebrew in Containers

Recorded on 2026-10-18: standardize on Homebrew in the container targets too.
This reverses the earlier guidance that kept Homebrew out of the images in
favour of pinned `uv` and binary installs. The reason is that the goal is a
rapid, composable development environment, and running one toolchain on hosts
and containers is simpler than maintaining two. A similar setup is already
proven in a work environment.

Keep from the current design:

- distro packages for the system substrate (`git`, `curl`, build tools, GPG)
- the non-root `vscode` user, who owns the Homebrew prefix so `brew install`
  works without `sudo`
- `shell-config` as the owner of shell behavior

To work out:

- Homebrew does not support musl, so the Alpine target needs a decision:
  keep its current installers, use glibc compatibility, or retire it
- arm64 Linux bottle coverage, and the build time and image size cost
- whether the Homebrew prefix lives in the image, in a volume, or in the image
  with a volume overlay, which decides how persistent ad hoc installs are
- whether the bundle should be shared with the host roles' Brewfile or layered
  on top of it

### Claude Code

Install Claude Code with its native installer rather than a package manager,
so it can keep itself up to date between rebuilds. `M5b` covers the host
targets and this milestone covers the containers. Its config and login state
need a persisted mount, like the other CLI auth paths.

### Getting Code Into a Devcontainer

- **Bind mount** the host checkout: edits are shared with the host and nothing
  is cloned twice, but the checkout must already exist, and performance
  depends on the host filesystem (fine on WSL2's ext4, slow from `/mnt/c`)
- **Clone into a volume**: this works from a bare host or the VS Code "Clone
  Repository in Container Volume" flow and is fast everywhere, but the code
  lives only in the volume, so pushing becomes the backup

Today's devcontainers bind-mount the workspace folder. The milestone should
choose a recommended default per use case.

### Terminal Mode

`ft workspace` already starts a long-lived container with bind mounts and
persisted state, and the devcontainer CLI can do the same from
`devcontainer.json`. Prefer one definition: either `ft workspace` drives the
devcontainer CLI, or the devcontainer files are generated from the workspace
profiles. Spike this before building more.

## Issue Drafts

### M5c-1 Spike Homebrew in the container images

- [ ] Problem: the images and hosts use different userland toolchains
- [ ] Scope: install Homebrew as the `vscode` user in `ubuntu`, measure build time and size on amd64 and arm64, and decide on Alpine
- [ ] Acceptance: a recorded go or no-go with numbers, plus the Alpine decision

### M5c-2 Move container userland tools to Homebrew

- [ ] Problem: the `uv` and binary installers duplicate what the host Brewfile already declares
- [ ] Scope: replace them with a Homebrew bundle and update the container standards and architecture docs
- [ ] Acceptance: `ft workspace validate` passes on the Homebrew-based images

### M5c-3 Install Claude Code in every container target

- [ ] Problem: Claude Code is installed by hand today
- [ ] Scope: native installer during the image build, a persisted config mount, and a validation check
- [ ] Acceptance: `claude --version` passes in every workspace and the CLI updates itself without a rebuild

### M5c-4 Choose how code gets into a devcontainer

- [ ] Problem: bind mounts need a host checkout and can be slow, while volume clones hide the code from the host
- [ ] Scope: support and document both, with a recommended default per use case
- [ ] Acceptance: both flows work from VS Code and the devcontainer CLI

### M5c-5 Unify the workspace and devcontainer definitions

- [ ] Problem: `ft workspace` profiles and `.devcontainer/` describe overlapping container setups
- [ ] Scope: spike `ft workspace` driving the devcontainer CLI, compared with generating the devcontainer files from profiles
- [ ] Acceptance: one source of truth, or a documented reason for two

## Verification Notes

- [ ] VS Code devcontainer, bind-mount flow, on WSL2
- [ ] VS Code devcontainer, volume-clone flow
- [ ] Devcontainer CLI terminal mode, used for a real change and pushed
- [ ] A container replaced after `brew install` of an ad hoc tool behaves as documented
- [ ] amd64 and arm64 builds

## Branch and Merge Plan

- [ ] Start after `M5b`, or alongside it if the Homebrew spike is independent
- [ ] Branch from `main` as `feat/m0005c-composable-container-workspaces`
- [ ] Commit freely at verified checkpoints
- [ ] Squash merge into `main` once the exit criteria are met

## Progress Notes

Drafted on 2026-10-18 when closing `M5a`, from the target use cases and the
Homebrew decision above.
