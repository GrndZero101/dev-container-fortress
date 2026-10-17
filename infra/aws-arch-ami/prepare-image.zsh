#!/usr/bin/env zsh
# Download, verify, and convert the official Arch Linux cloud image for EC2 import.
# Runs on the operator machine before `terraform apply` in this stack. Needs curl,
# gpg, and sha256sum, plus either qemu-img or Docker for the qcow2 -> VMDK step.
# Prints the path of the prepared VMDK on stdout as its last line.

if [ -z "${ZSH_VERSION:-}" ]; then
  printf '%s\n' "prepare-image.zsh must be executed with zsh." >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR=${0:A:h}
# Bump this deliberately, the same way ARCH_ARCHIVE_DATE is bumped for images.
ARCH_CLOUDIMG_VERSION=${ARCH_CLOUDIMG_VERSION:-20261015.611680}
ARCH_CLOUDIMG_BASE_URL=${ARCH_CLOUDIMG_BASE_URL:-https://geo.mirror.pkgbuild.com/images}
# Primary key of the arch-boxes release CI, published in the arch-boxes README
# on gitlab.archlinux.org. The committed arch-boxes.asc must carry this key.
ARCH_BOXES_KEY_FINGERPRINT=1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F
OUTPUT_DIR=${1:-${XDG_CACHE_HOME:-${HOME}/.cache}/dev-container-fortress/arch-ami}

# Purpose: Print a consistently formatted log line on stderr.
# Arguments:
#   $1: Message to display.
# Returns:
#   None.
log_step() {
  print -u2 -P "%F{33}[arch-ami]%f $1"
}

# Purpose: Stop with an actionable error message.
# Arguments:
#   $1: Message to display.
# Returns:
#   Never returns; exits 1.
fail() {
  print -u2 -P "%F{red}[arch-ami]%f $1"
  exit 1
}

# Purpose: Fail early when a required command is missing.
# Arguments:
#   $@: Command names to check.
# Returns:
#   None.
require_commands() {
  local name
  for name in "$@"; do
    command -v "${name}" >/dev/null 2>&1 || fail "required command not found: ${name}"
  done
}

# Purpose: Download the image, detached signature, and checksum file once.
# Arguments:
#   $1: Image file name.
# Returns:
#   None.
# Side effects:
#   Writes the three files into OUTPUT_DIR.
download_image() {
  local image_name=$1 suffix
  for suffix in "" .sig .SHA256; do
    if [[ ! -s "${OUTPUT_DIR}/${image_name}${suffix}" ]]; then
      log_step "downloading ${image_name}${suffix}"
      curl -fsSL --retry 3 -o "${OUTPUT_DIR}/${image_name}${suffix}.part" \
        "${ARCH_CLOUDIMG_BASE_URL}/v${ARCH_CLOUDIMG_VERSION}/${image_name}${suffix}"
      mv "${OUTPUT_DIR}/${image_name}${suffix}.part" "${OUTPUT_DIR}/${image_name}${suffix}"
    fi
  done
}

# Purpose: Verify the checksum and the arch-boxes signature against the pinned key.
# Arguments:
#   $1: Image file name.
# Returns:
#   None; exits on any verification failure.
# Side effects:
#   Uses a throwaway GNUPGHOME so the operator keyring is never touched.
verify_image() {
  local image_name=$1 gnupg_home gpg_status
  log_step "verifying checksum"
  (cd "${OUTPUT_DIR}" && sha256sum --quiet -c "${image_name}.SHA256") ||
    fail "checksum mismatch for ${image_name}"

  gnupg_home=$(mktemp -d)
  trap "rm -rf '${gnupg_home}'" EXIT
  gpg --homedir "${gnupg_home}" --batch --quiet --import "${SCRIPT_DIR}/arch-boxes.asc" 2>/dev/null
  log_step "verifying signature"
  gpg_status=$(gpg --homedir "${gnupg_home}" --batch --status-fd 1 \
    --verify "${OUTPUT_DIR}/${image_name}.sig" "${OUTPUT_DIR}/${image_name}" 2>/dev/null) ||
    fail "signature verification failed for ${image_name}"
  # VALIDSIG column 12 is the primary key fingerprint, even for subkey signatures.
  print -r -- "${gpg_status}" | awk '$2 == "VALIDSIG" { print $12 }' |
    grep -qx "${ARCH_BOXES_KEY_FINGERPRINT}" ||
    fail "image is not signed by the pinned arch-boxes key ${ARCH_BOXES_KEY_FINGERPRINT}"
}

# Purpose: Convert the verified qcow2 into a stream-optimized VMDK for EC2 import.
# Arguments:
#   $1: Source qcow2 file name.
#   $2: Destination VMDK file name.
# Returns:
#   None.
# Side effects:
#   Uses local qemu-img when present, otherwise a throwaway archlinux container.
convert_image() {
  local source_name=$1 target_name=$2
  if [[ -s "${OUTPUT_DIR}/${target_name}" ]]; then
    log_step "reusing ${target_name}"
    return
  fi
  log_step "converting to stream-optimized VMDK"
  if command -v qemu-img >/dev/null 2>&1; then
    qemu-img convert -O vmdk -o subformat=streamOptimized \
      "${OUTPUT_DIR}/${source_name}" "${OUTPUT_DIR}/${target_name}.part"
  else
    require_commands docker
    # A full -Syu avoids an unsupported partial upgrade inside the container.
    docker run --rm -v "${OUTPUT_DIR}:/work" archlinux:base sh -c "
      pacman -Syu --noconfirm --needed qemu-img >/dev/null &&
      qemu-img convert -O vmdk -o subformat=streamOptimized \
        '/work/${source_name}' '/work/${target_name}.part' &&
      chown $(id -u):$(id -g) '/work/${target_name}.part'"
  fi
  mv "${OUTPUT_DIR}/${target_name}.part" "${OUTPUT_DIR}/${target_name}"
}

# Purpose: Run the prepare flow end to end.
# Arguments:
#   None.
# Returns:
#   None; prints the prepared VMDK path on stdout.
main() {
  local image_name="Arch-Linux-x86_64-cloudimg-${ARCH_CLOUDIMG_VERSION}.qcow2"
  local vmdk_name="Arch-Linux-x86_64-cloudimg-${ARCH_CLOUDIMG_VERSION}.vmdk"

  require_commands curl gpg sha256sum awk
  mkdir -p "${OUTPUT_DIR}"
  download_image "${image_name}"
  verify_image "${image_name}"
  convert_image "${image_name}" "${vmdk_name}"
  log_step "prepared Arch cloud image ${ARCH_CLOUDIMG_VERSION}"
  print -r -- "${OUTPUT_DIR}/${vmdk_name}"
}

main
