#!/usr/bin/env zsh
# Bootstrap the local dev-container-fortress workspace with uv.
# This entrypoint stays small and delegates project behavior to pyproject metadata.

if [ -z "${ZSH_VERSION:-}" ]; then
  printf '%s\n' "bootstrap.zsh must be executed with zsh." >&2
  printf '%s\n' "Use: zsh ./bootstrap.zsh" >&2
  exit 1
fi

set -euo pipefail

BOOTSTRAP_DIR=${0:A:h}
FORTRESS_PYTHON_VERSION=${DEV_CONTAINER_FORTRESS_PYTHON_VERSION:-3.14}
UV_WAS_INSTALLED=0

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
  UV_WAS_INSTALLED=1

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

# Purpose: Print a next-step hint when uv was just installed into a user-local path.
# Arguments:
#   None.
# Returns:
#   None.
print_path_refresh_hint() {
  if [[ "${UV_WAS_INSTALLED}" != "1" ]]; then
    return
  fi

  print -u2 -- "[bootstrap] next step: if this shell does not yet see uv, open a new shell or run:"
  print -u2 -- 'export PATH="$HOME/.local/bin:$PATH"'
}

# Purpose: Ensure the project uses a uv-managed Python runtime.
# Arguments:
#   None.
# Returns:
#   None.
ensure_managed_python() {
  log_step "Ensuring uv-managed Python ${FORTRESS_PYTHON_VERSION}"
  uv python install "${FORTRESS_PYTHON_VERSION}"
  export UV_MANAGED_PYTHON=1
  export UV_PYTHON="${FORTRESS_PYTHON_VERSION}"
}

# Purpose: Synchronize the local workspace environment using uv.
# Arguments:
#   None.
# Returns:
#   None.
sync_workspace() {
  log_step "Syncing workspace dependencies with uv-managed Python ${FORTRESS_PYTHON_VERSION}"
  uv sync --all-groups --managed-python --python "${FORTRESS_PYTHON_VERSION}"
}

# Purpose: Install the ft zsh completion artifact into the user's XDG data tree.
# Arguments:
#   None.
# Returns:
#   None.
install_ft_completion() {
  log_step "Installing ft zsh completion into the XDG data tree"
  uv run ft completion install zsh
}

main() {
  configure_cache_root
  configure_project_environment
  ensure_uv
  ensure_managed_python

  cd "${BOOTSTRAP_DIR}"
  sync_workspace
  install_ft_completion
  log_step "Bootstrap complete"
  print_path_refresh_hint
}

main "$@"
