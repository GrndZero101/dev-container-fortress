#!/bin/sh
# Install Dev Container Fortress from GitHub and converge this machine.
# This script is intended to support curl-to-sh style onboarding and a repeatable
# clone-and-bootstrap flow for fresh and already converged machines.
#
# It stays POSIX sh because it runs before zsh exists. It only detects the
# platform, installs native prerequisites, prepares the checkout, and hands off
# to bootstrap.zsh and ft; host convergence stays in Ansible.

set -eu

REPO_URL="${DEV_CONTAINER_FORTRESS_REPO:-https://github.com/GrndZero101/dev-container-fortress.git}"
REPO_REF="${DEV_CONTAINER_FORTRESS_REF:-}"
INSTALL_MODE="${DEV_CONTAINER_FORTRESS_MODE:-host}"
INSTALL_DIR_OVERRIDE="${DEV_CONTAINER_FORTRESS_DIR:-}"
UV_WAS_INSTALLED=0

# Ubuntu releases the one-liner has been verified on. Other Ubuntu releases
# continue with a warning.
TESTED_UBUNTU_VERSIONS="24.04"
# Native packages needed before bootstrap.zsh and the localhost Ansible run.
# python3-apt backs Ansible's apt module, and sudo backs become for root users.
UBUNTU_PREREQ_PACKAGES="ca-certificates curl git zsh python3 python3-apt sudo"

PLATFORM_SUPPORTED=0
PLATFORM_IS_WSL=0
PLATFORM_LABEL=""
SUDO_KEEPALIVE_PID=""
USE_SUDO=0

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

# Purpose: Print an installer error and exit.
# Arguments:
#   $1: Error message to display.
# Returns:
#   None. Exits with status 1.
die() {
  printf '%s\n' "[install] error: $1" >&2
  exit 1
}

# Purpose: Print installer usage.
# Arguments:
#   None.
# Returns:
#   None.
print_usage() {
  cat <<'USAGE'
Usage: install.sh [--mode host|cli|workspace] [--dir PATH] [--ref REF] [--repo URL]

Pass flags through curl with: curl -fsSL .../install.sh | sh -s -- --mode cli

Modes:
  host       Default. Install prerequisites, ft, and converge this machine
             with the localhost host bootstrap (Ubuntu and WSL2 Ubuntu).
  cli        Install only the checkout, uv, ft, and Ansible.
  workspace  Thin host plus a daily-driver workspace (not available yet).

Every flag has an environment variable: DEV_CONTAINER_FORTRESS_MODE,
DEV_CONTAINER_FORTRESS_DIR, DEV_CONTAINER_FORTRESS_REF, and
DEV_CONTAINER_FORTRESS_REPO.
USAGE
}

# Purpose: Apply command-line flags over the environment-variable settings.
# Arguments:
#   $@: Installer arguments.
# Returns:
#   None. Exits on unknown or incomplete flags.
parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --mode | --dir | --ref | --repo)
        [ "$#" -ge 2 ] || die "$1 needs a value"
        case "$1" in
          --mode) INSTALL_MODE=$2 ;;
          --dir) INSTALL_DIR_OVERRIDE=$2 ;;
          --ref) REPO_REF=$2 ;;
          --repo) REPO_URL=$2 ;;
        esac
        shift 2
        ;;
      -h | --help)
        print_usage
        exit 0
        ;;
      *)
        print_usage >&2
        die "unknown argument: $1"
        ;;
    esac
  done

  case "$INSTALL_MODE" in
    host | cli) ;;
    workspace) die "workspace mode is not available yet; use --mode host or --mode cli" ;;
    *) die "unknown mode: $INSTALL_MODE (expected host, cli, or workspace)" ;;
  esac
}

# Purpose: Detect whether this machine is a platform the installer can converge.
# Arguments:
#   None.
# Returns:
#   None. Sets PLATFORM_SUPPORTED and PLATFORM_LABEL.
detect_platform() {
  kernel=$(uname -s)
  case "$kernel" in
    Linux) ;;
    Darwin)
      PLATFORM_LABEL="macOS"
      return
      ;;
    *)
      PLATFORM_LABEL="$kernel"
      return
      ;;
  esac

  if [ ! -r /etc/os-release ]; then
    PLATFORM_LABEL="Linux (unknown distribution)"
    return
  fi
  # Read os-release in a subshell so its variables do not leak into ours.
  # shellcheck source=/dev/null
  os_id=$(. /etc/os-release && printf '%s' "${ID:-}")
  # shellcheck source=/dev/null
  os_version=$(. /etc/os-release && printf '%s' "${VERSION_ID:-}")
  PLATFORM_LABEL="${os_id:-linux} ${os_version}"

  # Containers on a WSL2 host share its kernel, so also require a WSL marker.
  if grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null &&
    { [ -d /run/WSL ] || [ -n "${WSL_DISTRO_NAME:-}" ]; }; then
    PLATFORM_IS_WSL=1
    PLATFORM_LABEL="${PLATFORM_LABEL} (WSL2)"
  fi

  if [ "$os_id" != "ubuntu" ]; then
    return
  fi
  PLATFORM_SUPPORTED=1

  case " $TESTED_UBUNTU_VERSIONS " in
    *" $os_version "*) ;;
    *) warn_step "Ubuntu $os_version is not a tested release ($TESTED_UBUNTU_VERSIONS); continuing" ;;
  esac
}

# Purpose: Fail before any changes when host mode cannot converge this machine.
# Arguments:
#   None.
# Returns:
#   None. Exits when systemd is not the running init system.
# Side effects:
#   None. The Docker host role manages the docker service through systemd, so
#   without this check the install would stop partway through Ansible.
require_systemd() {
  if [ -d /run/systemd/system ]; then
    return
  fi
  if [ "$PLATFORM_IS_WSL" = "1" ]; then
    die "host mode needs systemd, which is off in this WSL2 distro. Add '[boot]' and 'systemd=true' to /etc/wsl.conf, run 'wsl --shutdown' from Windows, then rerun the installer"
  fi
  die "host mode needs systemd as the init system; inside a container, use --mode cli"
}

# Purpose: Exit early when a required command is unavailable.
# Arguments:
#   $1: Command name to validate.
# Returns:
#   None. Exits with status 1 on failure.
require_command() {
  command_name=$1
  if ! command -v "$command_name" >/dev/null 2>&1; then
    die "missing required command: $command_name"
  fi
}

# Purpose: Run one command as root, through sudo unless already root.
# Arguments:
#   $@: Command and arguments.
# Returns:
#   The command's exit status.
run_root() {
  if [ "$USE_SUDO" = "1" ]; then
    sudo "$@"
  else
    "$@"
  fi
}

# Purpose: Stop the background sudo keepalive loop when it is running.
# Arguments:
#   None.
# Returns:
#   None.
stop_sudo_keepalive() {
  if [ -n "$SUDO_KEEPALIVE_PID" ]; then
    kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    SUDO_KEEPALIVE_PID=""
  fi
}

# Purpose: Get root access once for the whole install.
# Arguments:
#   None.
# Returns:
#   None. Exits when sudo is unavailable or authentication fails.
# Side effects:
#   May prompt for the sudo password once. Starts a background loop that keeps
#   the sudo timestamp fresh, so the later Ansible run can use become without
#   -K. Ubuntu ties that timestamp to the terminal, so nothing after this may
#   start a new session.
acquire_privilege() {
  if [ "$(id -u)" = "0" ]; then
    return
  fi
  require_command sudo
  USE_SUDO=1

  if ! sudo -n -v 2>/dev/null; then
    # sudo reads the password from /dev/tty, so this works under curl | sh as
    # long as a terminal exists.
    if ! (: </dev/tty) 2>/dev/null; then
      die "sudo needs a password, but there is no terminal to ask on; rerun from an interactive shell or configure passwordless sudo"
    fi
    log_step "Root access is needed for native packages and the host bootstrap"
    sudo -v || die "sudo authentication failed"
  fi

  (
    while kill -0 "$$" 2>/dev/null; do
      sudo -n -v 2>/dev/null || exit 0
      sleep 45
    done
  ) >/dev/null 2>&1 &
  SUDO_KEEPALIVE_PID=$!
  trap stop_sudo_keepalive EXIT
  trap 'stop_sudo_keepalive; exit 130' INT TERM
}

# Purpose: List the Ubuntu prerequisite packages that are not installed yet.
# Arguments:
#   None.
# Returns:
#   Prints a space-separated package list, empty when nothing is missing.
missing_ubuntu_prereqs() {
  missing=""
  for package in $UBUNTU_PREREQ_PACKAGES; do
    if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q "install ok installed"; then
      missing="$missing $package"
    fi
  done
  printf '%s\n' "${missing# }"
}

# Purpose: Install the given Ubuntu prerequisite packages with apt.
# Arguments:
#   $1: Space-separated package list.
# Returns:
#   None.
install_ubuntu_prereqs() {
  packages=$1
  log_step "Installing native prerequisites: $packages"
  run_root env DEBIAN_FRONTEND=noninteractive apt-get update -qq
  # The package list is intentionally word-split into separate arguments.
  # shellcheck disable=SC2086
  run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends $packages
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
  if [ -n "$INSTALL_DIR_OVERRIDE" ]; then
    printf '%s\n' "$INSTALL_DIR_OVERRIDE"
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
  # A fresh shell may not have ~/.local/bin on PATH yet; reuse an earlier install.
  if [ -x "${HOME}/.local/bin/uv" ]; then
    export PATH="${HOME}/.local/bin:${PATH}"
    return
  fi

  log_step "uv not found; installing via the Astral standalone installer"
  UV_WAS_INSTALLED=1

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    die "uv is required but neither curl nor wget is available"
  fi

  export PATH="${HOME}/.local/bin:${PATH}"
  hash -r

  if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' "uv installation completed, but uv is still not on PATH." >&2
    die "expected location: ${HOME}/.local/bin/uv"
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
  # The literal $HOME is intended for the user to copy.
  # shellcheck disable=SC2016
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
    die "install destination exists but is not a git checkout: $destination"
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

# Purpose: Converge this machine with the localhost host bootstrap.
# Arguments:
#   $1: Repository directory.
# Returns:
#   None. Exits with the bootstrap's status on failure.
# Side effects:
#   Runs the Ansible host roles against localhost. localhost comes from the
#   example manifest, so no hosts.toml is needed. Ansible's sudo become passes
#   -n and reuses the timestamp from acquire_privilege.
run_host_bootstrap() {
  destination=$1
  log_step "Converging this machine with the localhost host bootstrap"
  if ! (cd "$destination" && uv run ft host bootstrap localhost); then
    printf '%s\n' "[install] the host bootstrap failed; rerunning the installer is safe, or run:" >&2
    printf '%s\n' "  cd $destination && uv run ft host bootstrap localhost -K" >&2
    exit 1
  fi
}

main() {
  parse_args "$@"
  detect_platform
  log_step "Platform: ${PLATFORM_LABEL}; mode: ${INSTALL_MODE}"

  if [ "$PLATFORM_SUPPORTED" = "1" ]; then
    if [ "$INSTALL_MODE" = "host" ]; then
      require_systemd
    fi
    missing_packages=$(missing_ubuntu_prereqs)
    if [ -n "$missing_packages" ] || [ "$INSTALL_MODE" = "host" ]; then
      acquire_privilege
    fi
    if [ -n "$missing_packages" ]; then
      install_ubuntu_prereqs "$missing_packages"
    else
      log_step "Native prerequisites already installed"
    fi
  elif [ "$INSTALL_MODE" = "host" ]; then
    die "host mode supports Ubuntu and WSL2 Ubuntu, not ${PLATFORM_LABEL}; macOS is the next planned platform. Use --mode cli to install only the ft CLI"
  else
    log_step "Checking required prerequisites"
    require_command git
    require_command zsh
  fi

  if [ "$INSTALL_MODE" = "cli" ]; then
    check_optional_container_prereqs
  fi

  install_dir=$(resolve_install_dir)
  sync_repo_checkout "$install_dir"
  ensure_uv
  run_repo_bootstrap "$install_dir"

  if [ "$INSTALL_MODE" = "host" ]; then
    run_host_bootstrap "$install_dir"
  fi

  log_step "Install complete"
  printf '%s\n' "Repo location: $install_dir"
  if [ "$INSTALL_MODE" = "host" ]; then
    printf '%s\n' "Open a new terminal to start the managed zsh login shell."
  fi
  print_path_refresh_hint
}

main "$@"
