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
INSTALL_OPTIONS="${DEV_CONTAINER_FORTRESS_OPTIONS:-}"
INSTALL_INTERACTIVE="${DEV_CONTAINER_FORTRESS_INTERACTIVE:-0}"
WORKSPACE_IMAGE="${DEV_CONTAINER_FORTRESS_WORKSPACE_IMAGE:-local}"
UV_WAS_INSTALLED=0

# The daily-driver workspace profile that workspace mode prepares.
WORKSPACE_PROFILE="ubuntu-full"

# Ubuntu releases the one-liner supports: the current LTS, the newest interim
# release, and the previous LTS. Other Ubuntu releases continue with a warning.
SUPPORTED_UBUNTU_VERSIONS="26.04 26.10 24.04"
# Native packages needed before bootstrap.zsh and the localhost Ansible run.
# python3-apt backs Ansible's apt module, and sudo backs become for root users.
UBUNTU_PREREQ_PACKAGES="ca-certificates curl git zsh python3 python3-apt sudo"

PLATFORM_SUPPORTED=0
PLATFORM_IS_WSL=0
PLATFORM_LABEL=""
SUDO_KEEPALIVE_PID=""
USE_SUDO=0
DOCKER_GROUP_PENDING=0

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
Usage: install.sh [--mode host|cli|workspace] [--options LIST] [--interactive]
                  [--workspace-image local|published]
                  [--dir PATH] [--ref REF] [--repo URL]

Pass flags through curl with: curl -fsSL .../install.sh | sh -s -- --mode cli

Modes:
  host       Default. Install prerequisites, ft, and converge this machine
             with the localhost host bootstrap (Ubuntu and WSL2 Ubuntu).
  cli        Install only the checkout, uv, ft, and Ansible.
  workspace  Thin host: prerequisites, Docker, and ft, plus the ubuntu-full
             daily-driver workspace image. Enter it with
             `ft workspace enter ubuntu-full`.

Workspace image (workspace mode only):
  --workspace-image local      Default. Build the image on this machine.
  --workspace-image published  Pull the CI-published image (amd64 only) instead.

Optional components are installed only when selected, and only in host mode:
claude-code, and at most one tmux profile (tmux-minimal, tmux-full, or
tmux-raidboss; without one, tmux keeps its stock settings):
  --options LIST   Comma-separated options for this run, or none.
  --interactive    Pick options in a checkbox list and save the choice
                   (needs a terminal; run `ft options` later to review).

Every flag has an environment variable: DEV_CONTAINER_FORTRESS_MODE,
DEV_CONTAINER_FORTRESS_OPTIONS, DEV_CONTAINER_FORTRESS_INTERACTIVE=1,
DEV_CONTAINER_FORTRESS_WORKSPACE_IMAGE, DEV_CONTAINER_FORTRESS_DIR,
DEV_CONTAINER_FORTRESS_REF, and DEV_CONTAINER_FORTRESS_REPO. Host mode makes
zsh the login shell; set DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL=0 to keep
the current shell.

Git identity: DEV_CONTAINER_FORTRESS_GIT_NAME and DEV_CONTAINER_FORTRESS_GIT_EMAIL
set it without a prompt; otherwise a terminal is asked for a missing identity.
DEV_CONTAINER_FORTRESS_FORGE_LOGIN=github or gitlab also starts a forge login.
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
      --mode | --options | --workspace-image | --dir | --ref | --repo)
        [ "$#" -ge 2 ] || die "$1 needs a value"
        case "$1" in
          --mode) INSTALL_MODE=$2 ;;
          --options) INSTALL_OPTIONS=$2 ;;
          --workspace-image) WORKSPACE_IMAGE=$2 ;;
          --dir) INSTALL_DIR_OVERRIDE=$2 ;;
          --ref) REPO_REF=$2 ;;
          --repo) REPO_URL=$2 ;;
        esac
        shift 2
        ;;
      -i | --interactive)
        INSTALL_INTERACTIVE=1
        shift
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
    host | cli | workspace) ;;
    *) die "unknown mode: $INSTALL_MODE (expected host, cli, or workspace)" ;;
  esac
  case "$WORKSPACE_IMAGE" in
    local | published) ;;
    *) die "unknown workspace image source: $WORKSPACE_IMAGE (expected local or published)" ;;
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

  case " $SUPPORTED_UBUNTU_VERSIONS " in
    *" $os_version "*) ;;
    *) warn_step "Ubuntu $os_version is not a supported release ($SUPPORTED_UBUNTU_VERSIONS); continuing" ;;
  esac
}

# Purpose: Fail before any changes when host or workspace mode cannot converge
#   this machine.
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
    die "$INSTALL_MODE mode needs systemd, which is off in this WSL2 distro. Add '[boot]' and 'systemd=true' to /etc/wsl.conf, run 'wsl --shutdown' from Windows, then rerun the installer"
  fi
  die "$INSTALL_MODE mode needs systemd as the init system; inside a container, use --mode cli"
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

  # Probe with a real command, not `sudo -n -v`: -v checks every sudoers entry
  # the user has, so EC2's ubuntu user (NOPASSWD plus the password-only %sudo
  # group rule) fails it even though every command runs without a password.
  if ! sudo -n true 2>/dev/null; then
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

  # In host mode shell-config owns PATH, so keep uv's installer out of the
  # user's existing ~/.profile, ~/.bashrc, and ~/.zshrc.
  uv_modify_path=
  if [ "$INSTALL_MODE" = "host" ]; then
    uv_modify_path=1
  fi

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | UV_NO_MODIFY_PATH=$uv_modify_path sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | UV_NO_MODIFY_PATH=$uv_modify_path sh
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
    # A branch ref must fast-forward on re-runs too; tags and commits stay put.
    if git -C "$destination" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
      git -C "$destination" pull --ff-only
    fi
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
#   Runs the Ansible host roles against localhost, in host or workspace mode.
#   localhost comes from the example manifest, so no hosts.toml is needed.
#   Ansible's sudo become passes -n and reuses the timestamp from
#   acquire_privilege.
run_host_bootstrap() {
  destination=$1
  log_step "Converging this machine with the localhost host bootstrap ($INSTALL_MODE mode)"
  # Running the one-liner in host mode asks for a Dev Fortress workstation, so
  # make zsh the login shell unless the operator opted out. Workspace mode
  # skips the login-shell role.
  DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL="${DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL:-1}"
  export DEV_CONTAINER_FORTRESS_MANAGE_LOGIN_SHELL
  if ! (cd "$destination" && uv run ft host bootstrap localhost --mode "$INSTALL_MODE"); then
    printf '%s\n' "[install] the host bootstrap failed; rerunning the installer is safe, or run:" >&2
    printf '%s\n' "  cd $destination && uv run ft host bootstrap localhost --mode $INSTALL_MODE -K" >&2
    exit 1
  fi
}

# Purpose: Quote one value for safe reuse inside a shell command string.
# Arguments:
#   $1: Value to quote.
# Returns:
#   Prints the value in single quotes, with embedded single quotes escaped.
shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

# Purpose: Run one command string with access to the Docker daemon.
# Arguments:
#   $1: Command string, run by a shell in the current directory.
# Returns:
#   The command's exit status.
# Side effects:
#   The host bootstrap has just added this user to the docker group, which this
#   process does not hold yet. When the daemon socket is not usable directly,
#   root runs su for this user, which starts a fresh login with the new group
#   and needs no password. sg would avoid root, but Ubuntu 26.04 no longer
#   ships it. sudo resets PATH, so the command restores ours. Sets
#   DOCKER_GROUP_PENDING so the summary can ask for a new terminal.
run_with_docker_access() {
  if docker info >/dev/null 2>&1; then
    sh -c "$1"
    return
  fi
  DOCKER_GROUP_PENDING=1
  run_root su "$(id -un)" -c "PATH=$(shell_quote "$PATH"); export PATH; $1"
}

# Purpose: Prepare the daily-driver workspace image for workspace mode.
# Arguments:
#   $1: Repository directory.
# Returns:
#   None. Exits on failure with a retry hint.
# Side effects:
#   Builds the workspace image locally by default, because corporate networks
#   may block or distrust public registries. With --workspace-image published,
#   pulls the CI-published image and tags it as the local workspace image.
#   Either way, `ft workspace enter` then starts without a build.
run_workspace_image_step() {
  destination=$1
  if [ "$WORKSPACE_IMAGE" = "published" ]; then
    log_step "Pulling the published $WORKSPACE_PROFILE workspace image"
    workspace_command="uv run ft workspace pull $WORKSPACE_PROFILE"
  else
    log_step "Building the $WORKSPACE_PROFILE workspace image locally; this takes a while on first run"
    workspace_command="uv run ft workspace build $WORKSPACE_PROFILE"
  fi
  # No subshell here: run_with_docker_access records DOCKER_GROUP_PENDING for
  # the summary, so the directory change travels inside the command instead.
  if ! run_with_docker_access "cd $(shell_quote "$destination") && $workspace_command"; then
    printf '%s\n' "[install] preparing the workspace image failed; rerunning the installer is safe, or run:" >&2
    printf '%s\n' "  cd $destination && $workspace_command" >&2
    exit 1
  fi
}

# Purpose: Settle which optional components the host bootstrap installs.
# Arguments:
#   $1: Repository directory.
# Returns:
#   None.
# Side effects:
#   Exports DEV_CONTAINER_FORTRESS_OPTIONS for ft when --options was given.
#   With --interactive and a terminal, runs `ft options pick`, which saves the
#   choice to options.toml, and then unsets the variable so the saved choice
#   applies. A missing terminal or a cancelled picker never fails the install.
run_options_step() {
  destination=$1
  if [ -n "$INSTALL_OPTIONS" ]; then
    DEV_CONTAINER_FORTRESS_OPTIONS=$INSTALL_OPTIONS
    export DEV_CONTAINER_FORTRESS_OPTIONS
  fi
  [ "$INSTALL_INTERACTIVE" = "1" ] || return 0

  log_step "Choosing optional components"
  # Under curl | sh, stdin is this script, so the picker must read the terminal.
  if ! (: </dev/tty) 2>/dev/null; then
    warn_step "--interactive needs a terminal; continuing with the non-interactive selection"
    return 0
  fi
  if (cd "$destination" && uv run ft options pick </dev/tty >/dev/tty); then
    unset DEV_CONTAINER_FORTRESS_OPTIONS
  else
    warn_step "no options were saved; continuing with the non-interactive selection"
  fi
}

# Purpose: Set the Git identity without ever failing the install.
# Arguments:
#   $1: Repository directory.
# Returns:
#   None.
# Side effects:
#   Runs `ft identity`, which reads DEV_CONTAINER_FORTRESS_GIT_NAME,
#   DEV_CONTAINER_FORTRESS_GIT_EMAIL, and DEV_CONTAINER_FORTRESS_FORGE_LOGIN,
#   keeps an existing identity, and may write the global Git config.
run_identity_step() {
  destination=$1
  log_step "Checking the Git identity"
  # Under curl | sh, stdin is this script, so prompts must read the terminal.
  # Without a usable terminal, stdin is /dev/null and ft skips with a hint.
  if (: </dev/tty) 2>/dev/null; then
    identity_input=/dev/tty
  else
    identity_input=/dev/null
  fi
  if ! (cd "$destination" && uv run ft identity <"$identity_input"); then
    warn_step "the Git identity step failed; run 'uv run ft identity' in $destination later"
  fi
}

main() {
  parse_args "$@"
  detect_platform
  log_step "Platform: ${PLATFORM_LABEL}; mode: ${INSTALL_MODE}"

  if [ "$PLATFORM_SUPPORTED" = "1" ]; then
    if [ "$INSTALL_MODE" != "cli" ]; then
      require_systemd
    fi
    missing_packages=$(missing_ubuntu_prereqs)
    if [ -n "$missing_packages" ] || [ "$INSTALL_MODE" != "cli" ]; then
      acquire_privilege
    fi
    if [ -n "$missing_packages" ]; then
      install_ubuntu_prereqs "$missing_packages"
    else
      log_step "Native prerequisites already installed"
    fi
  elif [ "$INSTALL_MODE" != "cli" ]; then
    die "$INSTALL_MODE mode supports Ubuntu and WSL2 Ubuntu, not ${PLATFORM_LABEL}; macOS is the next planned platform. Use --mode cli to install only the ft CLI"
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
  run_options_step "$install_dir"

  if [ "$INSTALL_MODE" != "cli" ]; then
    run_host_bootstrap "$install_dir"
  fi
  if [ "$INSTALL_MODE" = "workspace" ]; then
    run_workspace_image_step "$install_dir"
  fi
  run_identity_step "$install_dir"

  log_step "Install complete"
  printf '%s\n' "Repo location: $install_dir"
  if [ "$INSTALL_MODE" = "host" ]; then
    printf '%s\n' "Open a new terminal to start the managed zsh login shell."
  elif [ "$INSTALL_MODE" = "workspace" ]; then
    if [ "$DOCKER_GROUP_PENDING" = "1" ]; then
      printf '%s\n' "Open a new terminal (or reconnect over SSH) so your user picks up the docker group, then run:"
    else
      printf '%s\n' "Start the workspace with:"
    fi
    printf '%s\n' "  ft workspace enter $WORKSPACE_PROFILE"
  fi
  print_path_refresh_hint
}

main "$@"
