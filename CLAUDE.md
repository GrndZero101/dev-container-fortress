# Claude Code Instructions

Repo-wide agent rules live in [`AGENTS.md`](AGENTS.md); read it before changing code.

<!-- taskplan:begin -->
## Task tracking

This repo tracks work with `tp` (see .claude/skills/taskplan). Never keep plans only in context.

- Start of session / after compaction: `tp status`, then `tp next`.
- Work one task at a time: `tp start ID` → implement → `tp done ID --commit-head`.
- Record decisions and dead ends with `tp note ID "..."`.
- If stuck after 2 attempts: `tp block ID --reason "..."` and move to `tp next`.
- Never edit .plan/*.jsonl by hand.
<!-- taskplan:end -->

## Repo rules for tp

- Get tasks from `tp` (`tp next`, `tp show ID`, `tp list`), never by reading `TODO.md` or the
  milestone files. `TODO.md` is a generated view for people; a pre-commit hook re-renders it.
- Never work tasks on `main`: use the milestone branch (see AGENTS.md, Planning Workflow).
- Tasks blocked as operator tasks or decisions are the user's; do not unblock them yourself.
