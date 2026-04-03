#!/usr/bin/env zsh
# Bootstrap the local dev-container-fortress workspace with uv.
# This entrypoint stays small and delegates project behavior to pyproject metadata.

set -euo pipefail

BOOTSTRAP_DIR=${0:A:h}

# Purpose: Print a consistently formatted bootstrap log line.
# Arguments:
#   $1: Message to display.
# Returns:
#   None.
log_step() {
  print -P "%F{33}[bootstrap]%f $1"
}

# Purpose: Select a writable cache root for uv and related tooling.
# Arguments:
#   None.
# Returns:
#   None.
configure_cache_root() {
  local candidate_cache_root

  candidate_cache_root=${XDG_CACHE_HOME:-${HOME}/.cache}
  if [[ ! -d "${candidate_cache_root}" && ! -w "${candidate_cache_root:h}" ]]; then
    candidate_cache_root=/tmp/dev-container-fortress-cache
  elif [[ -d "${candidate_cache_root}" && ! -w "${candidate_cache_root}" ]]; then
    candidate_cache_root=/tmp/dev-container-fortress-cache
  fi

  export XDG_CACHE_HOME="${candidate_cache_root}"
  export UV_CACHE_DIR="${XDG_CACHE_HOME}/uv"
  mkdir -p "${UV_CACHE_DIR}"
}

# Purpose: Select a writable environment directory for uv sync.
# Arguments:
#   None.
# Returns:
#   None.
configure_project_environment() {
  local default_environment

  default_environment=${BOOTSTRAP_DIR}/.venv
  export UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-${default_environment}}

  if [[ ! -d "${UV_PROJECT_ENVIRONMENT}" && ! -w "${UV_PROJECT_ENVIRONMENT:h}" ]]; then
    UV_PROJECT_ENVIRONMENT=/tmp/dev-container-fortress-venv
  elif [[ -d "${UV_PROJECT_ENVIRONMENT}" && ! -w "${UV_PROJECT_ENVIRONMENT}" ]]; then
    UV_PROJECT_ENVIRONMENT=/tmp/dev-container-fortress-venv
  fi

  export UV_PROJECT_ENVIRONMENT
}

# Purpose: Exit early when a required command is unavailable.
# Arguments:
#   $1: Command name to validate.
# Returns:
#   None. Exits with status 1 on failure.
require_command() {
  local command_name=$1

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    print -u2 -- "Missing required command: ${command_name}"
    exit 1
  fi
}

# Purpose: Ensure uv is available before the workspace sync runs.
# Arguments:
#   None.
# Returns:
#   None. Installs uv when possible, otherwise exits with status 1.
ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  log_step "uv not found; installing via the Astral standalone installer"

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    print -u2 -- "uv is required but neither curl nor wget is available."
    exit 1
  fi

  export PATH="${HOME}/.local/bin:${PATH}"
  hash -r

  if ! command -v uv >/dev/null 2>&1; then
    print -u2 -- "uv installation completed, but uv is still not on PATH."
    print -u2 -- "Expected location: ${HOME}/.local/bin/uv"
    exit 1
  fi
}

# Purpose: Synchronize the local workspace environment using uv.
# Arguments:
#   None.
# Returns:
#   None.
sync_workspace() {
  log_step "Syncing workspace dependencies with uv"
  uv sync --all-groups
}

main() {
  require_command python3
  configure_cache_root
  configure_project_environment
  ensure_uv

  cd "${BOOTSTRAP_DIR}"
  sync_workspace
  log_step "Bootstrap complete"
}

main "$@"
