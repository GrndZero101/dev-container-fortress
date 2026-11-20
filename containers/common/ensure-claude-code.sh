#!/usr/bin/env bash

# Ensure Claude Code is installed for the runtime user of a Dev Fortress
# container, through its native installer, when the claude-code option is on.
#
# Workspaces persist ${XDG_DATA_HOME}/claude, where the installer keeps each
# version and where Claude Code's self-updates land, while the launcher in
# ~/.local/bin belongs to the image. A replaced container therefore keeps its
# versions but loses the launcher, so this relinks the newest version rather
# than downloading it again, and runs the installer only when none is present.
#
# Usage: ft-ensure-claude-code [--if-selected]
#   --if-selected  do nothing unless DEV_CONTAINER_FORTRESS_OPTIONS names
#                  claude-code; for devcontainer hooks, which cannot read the
#                  host's saved option selection

set -euo pipefail

launcher="${HOME}/.local/bin/claude"
versions_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/claude/versions"
installer_url="${CLAUDE_CODE_INSTALLER_URL:-https://claude.ai/install.sh}"

# Report whether DEV_CONTAINER_FORTRESS_OPTIONS selects claude-code.
# Arguments: none.
# Returns: 0 when selected, 1 otherwise.
claude_code_selected() {
  local options
  options="$(printf '%s' "${DEV_CONTAINER_FORTRESS_OPTIONS:-}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
  case ",${options}," in
    *,claude-code,*) return 0 ;;
    *) return 1 ;;
  esac
}

# Point the launcher at the newest persisted version, when one exists.
# Arguments: none.
# Returns: 0 when relinked, 1 when no persisted version exists.
# Side effects: replaces ~/.local/bin/claude.
relink_newest_version() {
  local newest
  # Order by version, not modification time: `claude update` to a version that
  # is already on disk relinks without rewriting it, so the newest file need
  # not be the newest version. Only plain version names count, which skips
  # partial downloads.
  newest="$(ls -1 "${versions_dir}" 2>/dev/null | grep -E '^[0-9]+(\.[0-9]+)*$' | sort -V | tail -n 1 || true)"
  if [[ -z "${newest}" || ! -x "${versions_dir}/${newest}" ]]; then
    return 1
  fi
  mkdir -p "$(dirname "${launcher}")"
  ln -sfn "${versions_dir}/${newest}" "${launcher}"
  printf 'claude-code: relinked persisted version %s\n' "${newest}"
}

if [[ "${1:-}" == "--if-selected" ]] && ! claude_code_selected; then
  exit 0
fi

if [[ ! -x "${launcher}" ]] && ! relink_newest_version; then
  printf 'claude-code: installing with the native installer from %s\n' "${installer_url}"
  curl -fsSL "${installer_url}" | bash
fi

"${launcher}" --version
