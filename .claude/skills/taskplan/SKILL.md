---
name: taskplan
description: How to plan and track work with the `tp` CLI — the status → next → start → implement → verify → done loop, the JSON contract, writing verify commands and acceptance criteria, breaking a spec into tasks with `tp add --from-file`, and when to block instead of retrying. Use at the start of every session, after compaction, and whenever you plan, start, finish or get stuck on a task.
---

# Working with `tp`

`tp` is this repo's task and plan store. State lives in `.plan/` and is committed with the code,
so it survives compaction, `/clear` and fresh sessions. Never keep the plan only in context, and
never edit `.plan/*.jsonl` by hand.

## The loop

1. `tp status` — counts, what is `doing`, how many are ready, what is blocked.
2. `tp next` — the single highest-priority ready task. Exit code 3 means nothing is ready.
3. `tp start ID` — claim it. Work on one task at a time.
4. Implement. Record decisions and dead ends as you go: `tp note ID "tried X; failed because Y"`.
   Record files you touch: `tp edit ID --add-file src/x.py`.
5. Run the verify command yourself (`tp verify ID`) until it passes.
6. Commit, then `tp done ID --commit-head`. `done` runs the verify command again and refuses to
   close the task unless it exits 0 (exit code 2, `E_VERIFY_FAILED`, output tail in `details`).
7. Back to step 1.

If a `doing` task is already in `tp status` when you start, resume it rather than taking a new one.

## JSON contract

With `TP_JSON=1` (set in `.claude/settings.json`) or `--json`, every command prints exactly one
object: `{"ok": true, "data": ...}` or `{"ok": false, "error": {"code", "message", "details"}}`.

| Exit | Meaning |
| --- | --- |
| 0 | success |
| 1 | validation or usage error (`E_USAGE`, `E_TRANSITION`, `E_NO_VERIFY`, ...) |
| 2 | verify gate failed (`E_VERIFY_FAILED`) |
| 3 | nothing to return (`tp next` with no ready task) |
| 4 | not found |
| 5 | store locked or corrupt |

## Verify commands

- Fast and specific: `uv run pytest tests/test_auth.py -q`, not the whole suite.
- Deterministic: no network, no sleeps, no dependence on the order tests run in.
- Exit 0 must mean the acceptance criteria hold. A command that always passes is a lie.
- A milestone's verify runs the full gate, e.g. `uv run pytest -q && prek run --all-files`.
  A milestone is never started: once its children are closed, `tp done M-ID` closes it from todo.
- Never weaken a verify command to get a task closed. If it is wrong, fix it with
  `tp edit ID --verify "..."` and say why in a note.

## Acceptance criteria

Each is one checkable statement: "`tp next` exits 3 when no task is ready", not "next works". Add
them with `--accept` (repeatable) on `tp add`, or `tp edit ID --add-accept "..."`.

## Breaking a spec into tasks

Write the spec as a doc (`tp doc new "Auth spec" --kind spec --from-file spec.md`), then create
its tasks in one go from a YAML file. `key` gives a task a name that `parent` and `depends_on`
can refer to before ids exist:

```yaml
tasks:
  - key: auth
    title: Auth
    kind: milestone
    verify: uv run pytest -q
  - key: session
    title: Session model
    parent: auth
    verify: uv run pytest tests/test_session.py -q
    acceptance: ["sessions expire after 24h"]
    docs: [D-0001]
  - title: OAuth callback
    parent: auth
    depends_on: [session]
    verify: uv run pytest tests/test_oauth.py -q
```

`tp add --from-file tasks.yaml` prints the new ids; nothing is created if any item is invalid.

## Block or retry?

- Retry when the failure is yours and you have a new idea: a bug, a missed case, a wrong path.
- After two failed attempts at the same problem, stop:
  `tp block ID --reason "what is missing and who or what could unblock it"`, then `tp next`.
- Block at once on anything outside the repo: missing credentials, a decision only a human can
  make, an external service down.
- `tp done --skip-verify --reason "..."` exists, but only for a task whose verify genuinely cannot
  run here; it tags the task `verify-skipped` for review. Some projects disable it.

## Useful commands

| Command | Purpose |
| --- | --- |
| `tp show ID` | one task in full, with notes and the last verify result |
| `tp list --status todo --ready` | filtered list |
| `tp add "Title" --verify "CMD" --accept "..." --parent M-0001 --dep T-0003` | add a task |
| `tp edit ID --parent M-0002` | move a task to another milestone, keeping its id and history |
| `tp check` | dangling dependencies, cycles, schema errors |
| `tp export plan -o PLAN.md` | regenerate the human-readable plan |
| `tp log --task ID` | audit trail |
