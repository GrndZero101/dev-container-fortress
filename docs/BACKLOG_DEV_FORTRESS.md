# Dev Fortress Backlog

## Overview

Working backlog for the Dev Fortress environment.
This file is for ideas, follow-up items, and implementation notes that are not yet fully sorted into formal design or usage docs.

> [!NOTE]
> Keep this file backlog-oriented.
> Move operational truth into the proper usage or design documents once work is implemented.

## Current Direction

- Build a shell and terminal environment that feels intentional, high-signal, and developer-heavy without becoming opaque.
- Prefer Catppuccin Mocha where the underlying tool supports it cleanly.
- Prefer explicit, debuggable configuration over clever hidden behavior.
- Keep features understandable across shell startup, container startup, and workstation login flows.

## Tools Backlog

| Tool         | Purpose                              | Notes                                                                         |
| ------------ | ------------------------------------ | ----------------------------------------------------------------------------- |
| `bat`        | better `cat` and richer file viewing | consider using it as the man page viewer as well                              |
| `delta`      | improved git diff rendering          | good candidate for richer git ergonomics                                      |
| `eza`        | richer directory listing             | now integrated with icons, headers, and git-aware long view in fortress shell |
| `fastfetch`  | fast system summary                  | candidate for a fortress welcome or diagnostics view                          |
| `fd`         | faster file finding                  | already useful for shell aliases and workflows                                |
| `fzf`        | fuzzy finder                         | core fortress interaction primitive                                           |
| `lazygit`    | TUI git workflow                     | worth evaluating as an optional companion tool                                |
| `rg`         | faster grep                          | already a core shell tool                                                     |
| `television` | fuzzy data browser                   | possible future exploration item                                              |
| `tmux`       | terminal multiplexing                | likely needs plugin manager and Catppuccin-compatible theme strategy          |
| `yazi`       | TUI file manager                     | worth evaluating as a vim-like file workflow layer                            |

## Tool Configuration Backlog

### `bat`

- [ ] Use `bat` as the man page viewer through a clean shell-native pattern.
- [ ] Decide whether that can replace any existing OMZ snippet or overlap.

### `eza`

- [x] Use native fortress aliases rather than adding the OMZ `eza` plugin.
- [x] Enable icons by default.
- [x] Enable a richer long view with headers and git status.
- [ ] Consider whether `tree` should gain additional fortress defaults beyond icons.
- [ ] Consider whether extra `eza` aliases such as a git-aware tree view are worth adding.

## Prompt Backlog

### Prompt Engine Strategy

- [x] Support `oh-my-posh`, `starship`, and native zsh fallback.
- [x] Add a configurable prompt engine setting with env override support.
- [x] Support `auto`, `oh-my-posh`, `starship`, and `native` modes.
- [x] Default `auto` to prefer `oh-my-posh`, then `starship`, then native fallback.
- [ ] Add a small validation or test helper so the resolved prompt engine can be checked before opening a new shell.
- [ ] Consider a `csm` helper such as `describe-prompt` or `test-prompt-engine`.

### Prompt Structure

- [x] Move fortress to a two-line richer prompt layout when using `oh-my-posh`.
- [x] Keep path and prompt status as the stable prompt backbone.
- [x] Keep git contextual rather than always-on outside repositories.
- [x] Hide cloud, container, and language status when not in use.
- [x] Add a right-aligned date and time block to the first line.
- [ ] Keep evaluating whether the always-on versus contextual split still feels balanced during daily use.

### Prompt Themes

- [x] Use `powerlevel10k_modern` as the structural base for the fortress `oh-my-posh` theme.
- [x] Recolor that theme to Catppuccin Mocha.
- [ ] Explore additional `oh-my-posh` themes via `csm` at a later date.
- [ ] Decide whether prompt themes should become a first-class fortress setting.
- [ ] Consider repo-owned prompt theme variants and a theme selector workflow.

### Prompt Elements

Always-on or near-always-on prompt elements:

- abbreviated CWD
- prompt character / status
- git context when inside a repository
- date and time on the right-hand side of the first line

Contextual prompt elements:

- AWS profile and region
- Docker context
- Kubernetes context and namespace
- Python virtual environment

## Shell UX and Debugging Backlog

### HUD and Debug Surfaces

- [x] Add a fortress HUD with standard and pretty renderers.
- [x] Add env mapping details for exact variable and settings-file debugging.
- [x] Keep source attribution visible for resolved settings.
- [ ] Add a small prompt-engine validation section or helper to the HUD or `csm` surface.
- [ ] Keep reviewing the pretty HUD for table readability and consistency.
- [ ] Consider whether additional sections should be added for completions, aliases, or prompt-engine diagnostics.

### Settings Workflow

- [x] Add persistent fortress settings file support.
- [x] Keep the settings file user-owned and XDG-aligned.
- [x] Add `csm init-settings` and `csm edit-settings` workflows.
- [ ] Consider whether settings validation should be added later.
- [ ] Consider whether prompt engine and theme selection should surface more directly in `csm`.

## Local Human Testing Workflow

- [ ] Explore a local developer testing workflow for Dev Fortress that is optimized for human verification, not just CI.
- [ ] Evaluate whether this should be a helper script, a `just`-based task runner, or another lightweight orchestration approach.
- [ ] Cover the common manual test loop: build Docker images, start containers, generate or provision SSH keys, SSH into running containers, inspect `docker logs`, and tear environments down cleanly.
- [ ] Prefer a workflow that makes repeat testing fast and obvious for day-to-day iteration.
- [ ] Decide whether the workflow should live in the Dev Fortress repo, `shell-config`, or shared repo-owned tooling.

## Toolchain and Onboarding Backlog

- [ ] Document the recommended fortress toolchain for the best experience.
- [ ] Document installation guidance for `oh-my-posh`, `starship`, `eza`, `fzf`, `atuin`, `zoxide`, and `direnv`.
- [ ] Consider whether `csm` should grow a light-weight “recommended tools” diagnostic command.

## Future Evaluation Items

- [ ] `tmux` integration strategy.
- [ ] `lazygit` integration and alias strategy.
- [ ] `yazi` integration and workflow fit.
- [ ] `fastfetch` for a fortress welcome or host summary view.
- [ ] Additional shell UX improvements that reinforce the Dev Fortress identity without making startup opaque.
