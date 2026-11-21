#!/usr/bin/env bash
# Regenerate TODO.md from the tp (taskplan) store. Run by pre-commit, which
# fails the commit when the committed TODO.md is out of date.
# tp is a per-user tool (uv tool install), so skip where it is absent, as in CI.
set -euo pipefail
if ! command -v tp >/dev/null 2>&1; then
  echo "tp not installed; skipping TODO.md render" >&2
  exit 0
fi
TP_JSON=0 tp export board --no-notes --no-timestamp -o TODO.md >/dev/null
