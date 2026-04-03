#!/bin/sh

# Install shell-config into the current user's XDG config tree.
# Supports cloning from GitHub or copying a repo-local source from the Docker build context.

set -eu

SOURCE_ROOT=${1:-/tmp/build-context}
SHELL_CONFIG_SOURCE=${SHELL_CONFIG_SOURCE:-github}
SHELL_CONFIG_REPO_URL=${SHELL_CONFIG_REPO_URL:-https://github.com/GrndZero101/shell-config.git}
SHELL_CONFIG_BRANCH=${SHELL_CONFIG_BRANCH:-main}
SHELL_CONFIG_LOCAL_DIR=${SHELL_CONFIG_LOCAL_DIR:-}
SHELL_CONFIG_INSTALL_DIR=${SHELL_CONFIG_INSTALL_DIR:-${XDG_CONFIG_HOME:-${HOME}/.config}/shell-config}
SHELL_CONFIG_PROFILE_DEFAULT=${SHELL_CONFIG_PROFILE_DEFAULT:-zsh-tll-citadel-dev-fortress}
SHELL_CONFIG_INSTALL_ZINIT=${SHELL_CONFIG_INSTALL_ZINIT:-1}
SHELL_CONFIG_STATE_DIR=${XDG_CONFIG_HOME:-${HOME}/.config}/shell-config
SHELL_CONFIG_STATE_FILE=${SHELL_CONFIG_STATE_DIR}/active-profile
SHELL_CONFIG_ZDOTDIR_SANDBOX=${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/dev-container-fortress-shell-config-zdotdir

log_info() {
  printf '%s
' "shell-config: $1"
}

die() {
  printf '%s
' "shell-config: $1" >&2
  exit 1
}

resolve_path() {
  case "$1" in
    /*)
      printf '%s
' "$1"
      ;;
    *)
      printf '%s
' "${SOURCE_ROOT}/$1"
      ;;
  esac
}

validate_profile() {
  case "${SHELL_CONFIG_PROFILE_DEFAULT}" in
    zsh-zero|zsh-clean|zsh-ref-atuin|zsh-ref-fzftab|zsh-tll-citadel-dev-fortress|zsh-tll-test)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

run_csm() {
  mkdir -p "${SHELL_CONFIG_ZDOTDIR_SANDBOX}"
  : > "${SHELL_CONFIG_ZDOTDIR_SANDBOX}/.zshenv"
  env ZDOTDIR="${SHELL_CONFIG_ZDOTDIR_SANDBOX}" "${SHELL_CONFIG_INSTALL_DIR}/scripts/csm" "$@"
}

install_from_github() {
  mkdir -p "${SHELL_CONFIG_INSTALL_DIR%/*}"
  git clone --depth 1 --branch "${SHELL_CONFIG_BRANCH}" "${SHELL_CONFIG_REPO_URL}" "${SHELL_CONFIG_INSTALL_DIR}"
}

install_from_local() {
  [ -n "${SHELL_CONFIG_LOCAL_DIR}" ] || die 'SHELL_CONFIG_LOCAL_DIR is required when SHELL_CONFIG_SOURCE=local'
  resolved_local_dir=$(resolve_path "${SHELL_CONFIG_LOCAL_DIR}")
  [ -d "${resolved_local_dir}" ] || die "local shell-config source not found: ${SHELL_CONFIG_LOCAL_DIR}"
  [ -x "${resolved_local_dir}/scripts/csm" ] || die "local shell-config source is missing scripts/csm: ${SHELL_CONFIG_LOCAL_DIR}"

  mkdir -p "${SHELL_CONFIG_INSTALL_DIR}"
  cp -R "${resolved_local_dir}/." "${SHELL_CONFIG_INSTALL_DIR}/"
}

validate_profile || die "unsupported shell profile default: ${SHELL_CONFIG_PROFILE_DEFAULT}"

rm -rf "${SHELL_CONFIG_INSTALL_DIR}"

case "${SHELL_CONFIG_SOURCE}" in
  github)
    log_info "cloning ${SHELL_CONFIG_REPO_URL} at branch ${SHELL_CONFIG_BRANCH}"
    install_from_github
    ;;
  local)
    log_info "copying local source from ${SHELL_CONFIG_LOCAL_DIR}"
    install_from_local
    ;;
  *)
    die "unsupported shell-config source: ${SHELL_CONFIG_SOURCE}"
    ;;
esac

[ -x "${SHELL_CONFIG_INSTALL_DIR}/scripts/csm" ] || die 'installed shell-config is missing scripts/csm'

log_info 'running csm bootstrap'
run_csm bootstrap

mkdir -p "${SHELL_CONFIG_STATE_DIR}"
printf '%s
' "${SHELL_CONFIG_PROFILE_DEFAULT}" > "${SHELL_CONFIG_STATE_FILE}"
log_info "set default profile to ${SHELL_CONFIG_PROFILE_DEFAULT}"

if [ "${SHELL_CONFIG_INSTALL_ZINIT}" = "1" ]; then
  log_info 'installing fortress zinit plugin manager'
  run_csm install-zinit
fi

log_info 'shell-config installation complete'
