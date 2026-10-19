#!/usr/bin/env bash

# Bring a container's Homebrew prefix up to the Dev Fortress floor.
#
# The floor is the tool-pool Homebrew set for Linux, which the image writes to
# ${XDG_DATA_HOME}/dev-container-fortress/brew-floor.txt at build time. A warm
# image already holds the floor in its prefix, and Docker copies it into a
# fresh named volume; a cold image ships an empty prefix, so the first start
# installs Homebrew and the floor into the volume. Every later start only
# installs what is missing, which takes well under a second when nothing is.
# It never upgrades installed formulae; that stays with `brew upgrade`.
#
# Usage: ft-brew-floor

set -euo pipefail

prefix="${HOMEBREW_PREFIX:-/home/linuxbrew/.linuxbrew}"
floor_file="${DEV_FORTRESS_BREW_FLOOR_FILE:-${XDG_DATA_HOME:-${HOME}/.local/share}/dev-container-fortress/brew-floor.txt}"
brew_remote="${HOMEBREW_BREW_GIT_REMOTE:-https://github.com/Homebrew/brew}"
brew="${prefix}/bin/brew"

export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_ENV_HINTS=1

# Print one message prefixed with the script's name.
# Arguments: the message.
log() {
  printf 'brew floor: %s\n' "$1"
}

# Install Homebrew into the prefix at its newest X.Y.Z release tag, the same
# version rule the host linuxbrew role uses.
# Arguments: none.
# Side effects: clones Homebrew into ${prefix}/Homebrew and links bin/brew.
install_homebrew() {
  local tag
  tag="$(git ls-remote --tags --refs "${brew_remote}" \
    | sed 's#.*refs/tags/##' \
    | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -V \
    | tail -n 1)"
  [[ -n "${tag}" ]] || { log "no X.Y.Z release tag found in ${brew_remote}" >&2; exit 1; }
  log "installing Homebrew ${tag} into ${prefix}; a cold image's first start takes a few minutes"
  git clone --quiet --depth 1 --branch "${tag}" "${brew_remote}" "${prefix}/Homebrew"
  mkdir -p "${prefix}/bin"
  ln -sfn ../Homebrew/bin/brew "${brew}"
}

[[ -r "${floor_file}" ]] || { log "missing floor list ${floor_file}" >&2; exit 1; }
[[ -w "${prefix}" ]] || { log "${prefix} is not writable by $(id -un)" >&2; exit 1; }

if [[ ! -x "${brew}" ]]; then
  install_homebrew
fi

mapfile -t missing < <(comm -23 \
  <(grep -Ev '^[[:space:]]*(#|$)' "${floor_file}" | sort -u) \
  <("${brew}" list --formula -1 | sort -u))

if (( ${#missing[@]} == 0 )); then
  log "all $(grep -Evc '^[[:space:]]*(#|$)' "${floor_file}") formulae present"
  exit 0
fi

log "installing ${#missing[@]} missing: ${missing[*]}"
"${brew}" install --formula "${missing[@]}"
