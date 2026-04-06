#!/bin/sh
# Install Dev Container Fortress from GitHub and run the local bootstrap.
# This script is intended to support curl-to-sh style onboarding and a repeatable
# clone-and-bootstrap flow for fresh machines.

set -eu

REPO_URL="${DEV_CONTAINER_FORTRESS_REPO:-https://github.com/GrndZero101/dev-container-fortress.git}"
REPO_REF="${DEV_CONTAINER_FORTRESS_REF:-}"
UV_WAS_INSTALLED=0

# Purpose: Print a consistently formatted installer log line.
# Arguments:
#   $1: Message to display.
# Returns:
#   None.
log_step() {
  printf '%s\n' "[install] $1"
}

# Purpose: Print a consistently formatted installer warning line.
# Arguments:
#   $1: Warning message to display.
# Returns:
#   None.
warn_step() {
  printf '%s\n' "[install] warning: $1" >&2
}

# Purpose: Exit early when a required command is unavailable.
# Arguments:
#   $1: Command name to validate.
# Returns:
#   None. Exits with status 1 on failure.
require_command() {
  command_name=$1
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '%s\n' "Missing required command: $command_name" >&2
    exit 1
  fi
}

# Purpose: Check optional tooling needed for the first container validation loop.
# Arguments:
#   None.
# Returns:
#   None. Emits warnings only.
check_optional_container_prereqs() {
  if ! command -v docker >/dev/null 2>&1; then
    warn_step "docker is not installed; the first container validation loop will not work yet"
    return
  fi

  if ! docker buildx version >/dev/null 2>&1; then
    warn_step "docker buildx is not available; container build and validation flows may fail"
  fi
}

# Purpose: Choose the local installation directory for the repo checkout.
# Arguments:
#   None.
# Returns:
#   Prints the chosen absolute or relative path to stdout.
resolve_install_dir() {
  if [ -n "${DEV_CONTAINER_FORTRESS_DIR:-}" ]; then
    printf '%s\n' "${DEV_CONTAINER_FORTRESS_DIR}"
    return
  fi

  if [ -w "." ]; then
    printf '%s\n' "./dev-container-fortress"
    return
  fi

  printf '%s\n' "${HOME}/dev-container-fortress"
}

# Purpose: Ensure uv is available before the repo bootstrap runs.
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
    printf '%s\n' "uv is required but neither curl nor wget is available." >&2
    exit 1
  fi

  export PATH="${HOME}/.local/bin:${PATH}"
  hash -r

  if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' "uv installation completed, but uv is still not on PATH." >&2
    printf '%s\n' "Expected location: ${HOME}/.local/bin/uv" >&2
    exit 1
  fi
}

# Purpose: Print a next-step hint when uv was just installed into a user-local path.
# Arguments:
#   None.
# Returns:
#   None.
print_path_refresh_hint() {
  if [ "${UV_WAS_INSTALLED}" != "1" ]; then
    return
  fi

  printf '%s\n' "[install] next step: if this shell does not yet see uv, open a new shell or run:" >&2
  printf '%s\n' 'export PATH="$HOME/.local/bin:$PATH"' >&2
}

# Purpose: Clone or refresh the local repository checkout.
# Arguments:
#   $1: Destination directory.
# Returns:
#   None.
sync_repo_checkout() {
  destination=$1

  if [ -d "$destination/.git" ]; then
    log_step "Refreshing existing checkout at $destination"
    git -C "$destination" fetch --tags origin
  elif [ -e "$destination" ]; then
    printf '%s\n' "Install destination exists but is not a git checkout: $destination" >&2
    exit 1
  else
    log_step "Cloning repository into $destination"
    git clone "$REPO_URL" "$destination"
  fi

  if [ -n "$REPO_REF" ]; then
    log_step "Checking out ref $REPO_REF"
    git -C "$destination" checkout "$REPO_REF"
  else
    log_step "Checking out origin/HEAD"
    current_branch=$(git -C "$destination" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
    if [ -n "$current_branch" ]; then
      default_branch=${current_branch#origin/}
      git -C "$destination" checkout "$default_branch"
      git -C "$destination" pull --ff-only origin "$default_branch"
    fi
  fi
}

# Purpose: Run the repo bootstrap entrypoint after the checkout is ready.
# Arguments:
#   $1: Repository directory.
# Returns:
#   None.
run_repo_bootstrap() {
  destination=$1
  log_step "Handing off to bootstrap.zsh"
  (
    cd "$destination"
    zsh ./bootstrap.zsh
  )
}

main() {
  log_step "Checking required prerequisites"
  require_command git
  require_command zsh
  check_optional_container_prereqs

  install_dir=$(resolve_install_dir)
  sync_repo_checkout "$install_dir"
  ensure_uv
  run_repo_bootstrap "$install_dir"

  log_step "Install complete"
  printf '%s\n' "Repo location: $install_dir"
  print_path_refresh_hint
}

main "$@"
