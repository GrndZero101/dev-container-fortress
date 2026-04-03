#!/usr/bin/env zsh

# Stage a local shell-config checkout into the dev-container-fortress build context.
# This makes Docker local-source builds work with any absolute host path.

emulate -LR zsh
setopt errexit nounset pipefail

typeset -gr SCRIPT_DIR="${${(%):-%N}:A:h}"
typeset -gr REPO_ROOT="${SCRIPT_DIR:h}"
typeset -gr DEFAULT_DEST="${REPO_ROOT}/.local/sources/shell-config"

usage() {
  cat <<'EOF'
Usage: stage-shell-config.zsh <absolute-source-path> [destination]

Arguments:
  absolute-source-path  Existing shell-config checkout on the host filesystem
  destination           Repo-local staging path
                        Default: .local/sources/shell-config
EOF
}

log_info() {
  print -P -- "%F{81}stage-shell-config:%f ${1}"
}

die() {
  print -u2 -P -- "%F{203}stage-shell-config:%f ${1}"
  exit 1
}

main() {
  local source_path="${1:-}"
  local destination_path="${2:-${DEFAULT_DEST}}"

  [[ -n "${source_path}" ]] || {
    usage
    return 1
  }

  [[ "${source_path}" == /* ]] || die 'source path must be absolute'
  [[ -d "${source_path}" ]] || die "source path does not exist: ${source_path}"
  [[ -x "${source_path}/scripts/csm" ]] || die "source path does not look like shell-config: ${source_path}"

  mkdir -p -- "${destination_path:h}"
  rm -rf -- "${destination_path}"
  cp -R -- "${source_path}/." "${destination_path}"

  log_info "staged ${source_path} -> ${destination_path}"
}

main "$@"
