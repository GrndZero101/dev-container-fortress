#!/usr/bin/env zsh

# Dev Fortress local container testing helper.
# Provides a deterministic human and agent-friendly workflow around disposable
# Docker test containers for the repository's Ubuntu and Alpine targets.

emulate -LR zsh
setopt errexit nounset pipefail

typeset -gr SCRIPT_DIR="${${(%):-%N}:A:h}"
typeset -gr REPO_ROOT="${SCRIPT_DIR:h}"
typeset -gr STATE_ROOT="${REPO_ROOT}/.local/test-containers"

# Print command usage.
#
# Arguments:
#   none
# Returns:
#   0 after writing usage text
# Side effects:
#   writes to stdout
usage() {
  cat <<'EOF'
Usage: test-container.zsh <command> [target] [args...]

Commands:
  build <target>              Build the target image
  up <target>                 Start the target container in detached mode
  validate <target>           Validate shell/profile and toolchain state
  status [target]             Show status for one or all managed containers
  logs <target>               Follow container logs
  exec <target> [command...]  Run a command inside the container
  shell <target>              Open an interactive zsh shell in the container
  down <target>               Stop and remove the container
  reset <target>              Remove the container and its image tag
  ssh-key <target>            Ensure the managed Dev Fortress SSH key exists
  ssh <target>                Open SSH for the Ubuntu disposable target
  help                        Show this help text

Targets:
  ubuntu
  alpine
EOF
}

# Print an informational message.
#
# Arguments:
#   $1: message text
# Returns:
#   0 after writing the message
# Side effects:
#   writes to stdout
log_info() {
  print -P -- "%F{81}test-container:%f ${1}"
}

# Print an error and exit.
#
# Arguments:
#   $1: error text
# Returns:
#   does not return
# Side effects:
#   writes to stderr and exits non-zero
die() {
  print -u2 -P -- "%F{203}test-container:%f ${1}"
  exit 1
}

# Ensure a required command exists.
#
# Arguments:
#   $1: command name
# Returns:
#   0 when present, exits non-zero otherwise
# Side effects:
#   may terminate the script
require_command() {
  command -v -- "${1}" >/dev/null 2>&1 || die "required command not found: ${1}"
}

# Validate and normalize a supported target name.
#
# Arguments:
#   $1: target name
# Returns:
#   0 and prints the normalized target
# Side effects:
#   may terminate the script
normalize_target() {
  local target="${1:-}"

  case "${target}" in
    ubuntu|alpine)
      print -- "${target}"
      ;;
    *)
      die "unsupported target: ${target:-<empty>} (expected ubuntu or alpine)"
      ;;
  esac
}

# Return the Dockerfile path for a target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 and prints the Dockerfile path
# Side effects:
#   none
dockerfile_for_target() {
  print -- "${REPO_ROOT}/containers/${1}/Dockerfile"
}

# Return the deterministic image tag for a target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 and prints the image tag
# Side effects:
#   none
image_tag_for_target() {
  print -- "dev-container-fortress:${1}-test"
}

# Return the deterministic container name for a target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 and prints the container name
# Side effects:
#   none
container_name_for_target() {
  print -- "dev-fortress-${1}-test"
}

# Return the managed Dev Fortress SSH key path for a target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 and prints the SSH key path
# Side effects:
#   none
ssh_key_path_for_target() {
  local xdg_state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
  print -- "${xdg_state_home}/dev-container-fortress/ssh/dev-fortress-${1}/id_ed25519"
}

# Ensure local state directories exist.
#
# Arguments:
#   none
# Returns:
#   0 after creating directories
# Side effects:
#   creates repo-local state directories
ensure_state_dirs() {
  mkdir -p -- "${STATE_ROOT}/ssh"
}

# Build the selected target image.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 when the build succeeds
# Side effects:
#   builds a Docker image
build_target() {
  local target="${1}"
  local dockerfile_path="$(dockerfile_for_target "${target}")"
  local image_tag="$(image_tag_for_target "${target}")"

  require_command docker
  [[ -f "${dockerfile_path}" ]] || die "missing Dockerfile: ${dockerfile_path}"

  log_info "building ${target} -> ${image_tag}"
  docker buildx build --load \
    -f "${dockerfile_path}" \
    -t "${image_tag}" \
    "${REPO_ROOT}"
}

# Start or replace the selected target container in detached mode.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 when the container is running
# Side effects:
#   creates or replaces a Docker container
up_target() {
  local target="${1}"
  local image_tag="$(image_tag_for_target "${target}")"
  local container_name="$(container_name_for_target "${target}")"

  require_command docker

  if ! docker image inspect "${image_tag}" >/dev/null 2>&1; then
    build_target "${target}"
  fi

  if docker container inspect "${container_name}" >/dev/null 2>&1; then
    log_info "replacing existing container ${container_name}"
    docker rm -f "${container_name}" >/dev/null
  fi

  log_info "starting ${container_name}"
  docker run --detach \
    --name "${container_name}" \
    --hostname "${container_name}" \
    "${image_tag}" \
    sleep infinity >/dev/null
}

# Render status for one or more managed containers.
#
# Arguments:
#   $@: zero or more normalized targets
# Returns:
#   0 after printing status data
# Side effects:
#   queries Docker
status_targets() {
  local -a targets=("$@")
  local target=""
  local container_name=""
  local image_tag=""
  local status_value=""

  require_command docker

  if (( ${#targets} == 0 )); then
    targets=(ubuntu alpine)
  fi

  printf '%-8s %-28s %-30s %s\n' target container image status
  for target in "${targets[@]}"; do
    container_name="$(container_name_for_target "${target}")"
    image_tag="$(image_tag_for_target "${target}")"
    status_value="$(docker inspect -f '{{.State.Status}}' "${container_name}" 2>/dev/null || print -- missing)"
    printf '%-8s %-28s %-30s %s\n' "${target}" "${container_name}" "${image_tag}" "${status_value}"
  done
}

# Print one validation result line.
#
# Arguments:
#   $1: status label
#   $2: check name
#   $3: detail text
# Returns:
#   0 after printing the line
# Side effects:
#   writes to stdout
print_validation_result() {
  printf '%-4s %-24s %s\n' "${1}" "${2}" "${3}"
}

# Run the core local validation flow for one managed container.
# Arguments:
#   $1: normalized target name
# Returns:
#   0 when all checks pass, otherwise 1
# Side effects:
#   runs commands inside the target container and prints a validation report
validate_target() {
  local target="${1}"
  local container_name="$(container_name_for_target "${target}")"
  local home_dir="/home/vscode"
  local hud_output=""
  local current_value=""
  local expected_value=""
  local check_name=""
  local status_label=""
  local -i failures=0

  require_command docker
  docker container inspect "${container_name}" >/dev/null 2>&1 || die "container not found: ${container_name}"

  log_info "validating ${container_name}"
  printf '%-4s %-24s %s\n' stat check detail

  current_value="$(docker exec "${container_name}" zsh -ilc 'whoami')"
  expected_value="vscode"
  if [[ "${current_value}" == "${expected_value}" ]]; then
    print_validation_result OK runtime_user "${current_value}"
  else
    print_validation_result FAIL runtime_user "expected ${expected_value}, got ${current_value}"
    (( failures++ ))
  fi

  current_value="$(docker exec "${container_name}" zsh -ilc 'print -r -- "${SHELL_CONFIG_PROFILE:-}"')"
  expected_value="zsh-tll-citadel-dev-fortress"
  if [[ "${current_value}" == "${expected_value}" ]]; then
    print_validation_result OK active_profile "${current_value}"
  else
    print_validation_result FAIL active_profile "expected ${expected_value}, got ${current_value}"
    (( failures++ ))
  fi

  current_value="$(docker exec "${container_name}" zsh -ilc 'print -r -- "$PATH"')"
  expected_value="${home_dir}/.local/bin"
  if [[ ":${current_value}:" == *":${expected_value}:"* ]]; then
    print_validation_result OK path_local_bin "${expected_value}"
  else
    print_validation_result FAIL path_local_bin "missing ${expected_value}"
    (( failures++ ))
  fi

  for check_name in starship atuin zoxide fzf fortress-hud csm ft; do
    if current_value="$(docker exec "${container_name}" zsh -ilc "command -v -- '${check_name}'" 2>/dev/null)"; then
      print_validation_result OK "${check_name}" "${current_value}"
    else
      print_validation_result FAIL "${check_name}" "command not found"
      (( failures++ ))
    fi
  done

  if ! hud_output="$(docker exec "${container_name}" zsh -ilc 'fortress-hud' 2>/dev/null)"; then
    print_validation_result FAIL fortress_hud "command failed"
    (( failures++ ))
  else
    print_validation_result OK fortress_hud "command succeeded"

    for current_value in \
      '[settings] prompt_engine_resolved: starship' \
      '[tools] starship: available' \
      '[tools] atuin: available' \
      '[tools] zoxide: available' \
      '[tools] fzf: available'
    do
      if [[ "${hud_output}" == *"${current_value}"* ]]; then
        print_validation_result OK hud_expectation "${current_value}"
      else
        print_validation_result FAIL hud_expectation "missing ${current_value}"
        (( failures++ ))
      fi
    done
  fi

  if (( failures == 0 )); then
    log_info "validation passed for ${container_name}"
    return 0
  fi

  log_info "validation failed for ${container_name} (${failures} checks)"
  return 1
}

# Follow logs for a managed container.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   exits with the docker logs exit code
# Side effects:
#   streams container logs
logs_target() {
  local target="${1}"
  local container_name="$(container_name_for_target "${target}")"

  require_command docker
  docker container inspect "${container_name}" >/dev/null 2>&1 || die "container not found: ${container_name}"

  exec docker logs --follow "${container_name}"
}

# Run a command inside the container.
#
# Arguments:
#   $1: normalized target name
#   $@: command to execute
# Returns:
#   exits with the docker exec exit code
# Side effects:
#   runs a process inside the container
exec_target() {
  local target="${1}"
  shift
  local container_name="$(container_name_for_target "${target}")"

  require_command docker
  docker container inspect "${container_name}" >/dev/null 2>&1 || die "container not found: ${container_name}"

  if (( $# == 0 )); then
    set -- zsh -lc 'whoami && echo $HOME && printenv SHELL_CONFIG_PROFILE'
  fi

  exec docker exec -it "${container_name}" "$@"
}

# Open an interactive shell in the container.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   exits with the docker exec exit code
# Side effects:
#   opens an interactive shell
shell_target() {
  exec_target "${1}" zsh -il
}

# Stop and remove a managed container.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 after cleanup
# Side effects:
#   removes a Docker container when present
down_target() {
  local target="${1}"
  local container_name="$(container_name_for_target "${target}")"

  require_command docker

  if docker container inspect "${container_name}" >/dev/null 2>&1; then
    log_info "removing ${container_name}"
    docker rm -f "${container_name}" >/dev/null
  else
    log_info "container already absent: ${container_name}"
  fi
}

# Remove the managed container and image tag.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 after cleanup
# Side effects:
#   removes Docker container and image when present
reset_target() {
  local target="${1}"
  local image_tag="$(image_tag_for_target "${target}")"

  require_command docker
  down_target "${target}"

  if docker image inspect "${image_tag}" >/dev/null 2>&1; then
    log_info "removing image ${image_tag}"
    docker image rm -f "${image_tag}" >/dev/null
  else
    log_info "image already absent: ${image_tag}"
  fi
}

# Ensure the managed Dev Fortress SSH key exists for the disposable target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   0 after ensuring the key exists through ft
# Side effects:
#   may create XDG-managed SSH key material
ssh_key_target() {
  local target="${1}"
  local host_target_name="dev-fortress-${target}"

  require_command uv
  log_info "ensuring managed SSH key for ${host_target_name}"
  UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" \
    uv run --project "${REPO_ROOT}/ft" ft host ssh-key "${host_target_name}"
}

# Open SSH for one supported disposable test container target.
#
# Arguments:
#   $1: normalized target name
# Returns:
#   exits with the ssh command status
# Side effects:
#   opens an interactive SSH session when supported
ssh_target() {
  local target="${1}"
  local key_path="$(ssh_key_path_for_target "${target}")"

  if [[ "${target}" != 'ubuntu' ]]; then
    cat <<EOF
SSH testing is currently only wired for ubuntu.

Use:
  ${0:t} shell ${target}
or:
  ${0:t} exec ${target} <command>
EOF
    return 0
  fi

  require_command ssh
  [[ -f "${key_path}" ]] || die "missing SSH key: ${key_path} (run '${0:t} ssh-key ${target}')"

  exec ssh \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/known_hosts/dev-fortress-${target}" \
    -i "${key_path}" \
    -p 2222 \
    vscode@127.0.0.1
}

# Entrypoint dispatcher.
#
# Arguments:
#   $1: command name
#   $@: command arguments
# Returns:
#   exits with the selected subcommand status
# Side effects:
#   dispatches to Docker and local helper operations
main() {
  local command="${1:-help}"
  local target=""

  case "${command}" in
    help|-h|--help)
      usage
      ;;
    build)
      shift
      target="$(normalize_target "${1:-}")"
      build_target "${target}"
      ;;
    up)
      shift
      target="$(normalize_target "${1:-}")"
      up_target "${target}"
      ;;
    validate)
      shift
      target="$(normalize_target "${1:-}")"
      validate_target "${target}"
      ;;
    status)
      shift
      if (( $# == 0 )); then
        status_targets
      else
        target="$(normalize_target "${1}")"
        status_targets "${target}"
      fi
      ;;
    logs)
      shift
      target="$(normalize_target "${1:-}")"
      logs_target "${target}"
      ;;
    exec)
      shift
      target="$(normalize_target "${1:-}")"
      shift
      exec_target "${target}" "$@"
      ;;
    shell)
      shift
      target="$(normalize_target "${1:-}")"
      shell_target "${target}"
      ;;
    down)
      shift
      target="$(normalize_target "${1:-}")"
      down_target "${target}"
      ;;
    reset)
      shift
      target="$(normalize_target "${1:-}")"
      reset_target "${target}"
      ;;
    ssh-key)
      shift
      target="$(normalize_target "${1:-}")"
      ssh_key_target "${target}"
      ;;
    ssh)
      shift
      target="$(normalize_target "${1:-}")"
      ssh_target "${target}"
      ;;
    *)
      usage
      die "unknown command: ${command}"
      ;;
  esac
}

main "$@"
