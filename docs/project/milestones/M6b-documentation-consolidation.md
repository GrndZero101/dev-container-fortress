# M6b Documentation Consolidation

## Status

- [x] Milestone complete
- [x] Active milestone

Branch: `docs/m0006b-docs-consolidation` (PR #8), then
`feat/m0006b-documentation-consolidation` for the command examples

## Objective

Give every fact one home, organise `docs/` by reader, and make the `ft` CLI
document itself, so that a documentation site can later be placed over the
result without publishing duplication.

A review on 2026-11-21 found the one-line installer in three files, the manual
bootstrap in three, five status matrices, and several contradictions that the
duplication had caused, plus no `ft` CLI reference and no `ft workspace` guide.

## Exit Criteria

- [x] Install and bootstrap steps live only in `docs/quickstart.md`; `README.md` shows the one-liner once and links there
- [x] One support matrix, in `README.md`
- [x] `DEVELOPMENT.md` is contributor-only and links to the guides instead of repeating them
- [x] `docs/` is grouped into `guides/`, `reference/`, `design/`, and `project/`, with every relative link rewritten
- [x] `docs/reference/cli.md` is generated from the Typer app, and a pre-commit hook fails when it is stale
- [x] A test fails when a command, argument, or option has no help text
- [x] `ft workspace` has a user guide
- [x] The workbench security caveat lives in the workbench guide, not only in a milestone file
- [x] The contradictions found in the review are fixed against the code: macOS support, Arch status, container tool installation, installer modes, the Markdown linter, and the pre-commit hook list
- [x] Markdown lint runs through `rumdl`, configured in `pyproject.toml`, including a relative-link check
- [x] The main commands carry a short paragraph and an example in their docstrings
- [ ] A new user can go from `README.md` through the quickstart to a working install without being sent back, checked on a fresh host (moved to [`M5e`](M5e-developer-workstation.md))

## Non-Goals

- [ ] A documentation site. That is planned with the `v0.1.0` release: Zensical over `docs/`, published to GitHub Pages
- [ ] A Python API reference
- [ ] Versioned documentation
- [ ] Rewriting the milestone files, which stay as historical records

## Issue Drafts

### Richer command descriptions

- [x] Problem: most command docstrings are one line, so the generated reference lists flags but shows no worked example
- [x] Scope: extend the docstrings of the main `ft host`, `ft workspace`, `ft container`, and `ft workbench` commands with a short paragraph and an example
- [x] Acceptance: `ft <command> --help` and `docs/reference/cli.md` show the example, and the help-coverage tests still pass

### Fresh-host walk-through

- [ ] Problem: the consolidated path has been checked by link and lint, not by a person following it
- [ ] Scope: follow `README.md` and the quickstart on a fresh Ubuntu host, and the developer path in `DEVELOPMENT.md`; this can share the `M5e` baseline run
- [ ] Acceptance: no step sends the reader back to an earlier document, and every snag is fixed or recorded
- Moved to [`M5e`](M5e-developer-workstation.md), whose cold bare-metal Ubuntu baseline run follows the same path

### Documentation site

- [ ] Problem: there is no search or navigation across the docs
- [ ] Scope: at `v0.1.0`, add Zensical over `docs/`, enable GitHub callouts through `pymdownx.quotes`, and publish to GitHub Pages from CI
- [ ] Acceptance: a strict build passes in CI, and the site renders the callouts and the CLI reference
- Known work: links from `docs/` into source files need GitHub URLs, and anchors that depend on emoji heading slugs need checking

## Verification Notes

- [x] `uv run pre-commit run --all-files` passes
- [x] `uv run pytest ft/tests` passes
- [x] `rumdl` reports no broken relative links
- [ ] Fresh-host walk-through, as above (moved to `M5e`)

## Branch and Merge Guidance

Squash-merge once the two open exit criteria are met, or move them to the
milestones that will cover them and merge the consolidation on its own.

## Progress Notes

The consolidation merged in PR #8. On 2026-11-21 the main commands gained a
paragraph and a worked example, pinned by the `help_example` tests, and the
fresh-host walk-through moved to `M5e`: it needs a person on a fresh machine,
and the `M5e` baseline run already walks the same path, so it no longer holds
this milestone open.
