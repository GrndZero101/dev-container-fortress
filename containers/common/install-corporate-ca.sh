#!/bin/sh

# Optional corporate CA installer for container builds.
# Expects a directory of PEM-formatted .crt files relative to the Docker build context.

set -eu

SOURCE_ROOT=${1:-/tmp/build-context}
CERT_DIR=${2:-}
INSTALL_DIR=/usr/local/share/ca-certificates

# Print a short status line for CA installation work.
# Arguments:
#   $1 - Message to display.
# Returns:
#   0 after writing the message to stdout.
log_info() {
  printf '%s\n' "corporate-ca: $1"
}

# Print an error line and terminate the installer.
# Arguments:
#   $1 - Error message to display.
# Returns:
#   Does not return.
# Side effects:
#   Writes to stderr and exits with status 1.
die() {
  printf '%s\n' "corporate-ca: $1" >&2
  exit 1
}

# Resolve the requested certificate directory path.
# Arguments:
#   None. Uses SOURCE_ROOT and CERT_DIR from the current environment.
# Returns:
#   0 after writing the resolved path to stdout.
resolve_cert_dir() {
  case "${CERT_DIR}" in
    /*)
      printf '%s\n' "${CERT_DIR}"
      ;;
    *)
      printf '%s\n' "${SOURCE_ROOT}/${CERT_DIR}"
      ;;
  esac
}

if [ -z "${CERT_DIR}" ]; then
  log_info 'disabled'
  exit 0
fi

RESOLVED_CERT_DIR=$(resolve_cert_dir)

[ -d "${RESOLVED_CERT_DIR}" ] || die "requested certificate directory not found: ${CERT_DIR}"

set -- "${RESOLVED_CERT_DIR}"/*.crt
[ -e "$1" ] || die "no .crt files found in certificate directory: ${CERT_DIR}"

validated_count=0
for cert_file in "$@"; do
  [ -f "${cert_file}" ] || continue
  openssl x509 -in "${cert_file}" -noout >/dev/null 2>&1 || die "invalid PEM certificate: ${cert_file##*/}"
  validated_count=$((validated_count + 1))
done

[ "${validated_count}" -gt 0 ] || die "no installable .crt files found in certificate directory: ${CERT_DIR}"

install -d "${INSTALL_DIR}"

installed_count=0
for cert_file in "$@"; do
  [ -f "${cert_file}" ] || continue
  cp "${cert_file}" "${INSTALL_DIR}/${cert_file##*/}"
  chmod 0644 "${INSTALL_DIR}/${cert_file##*/}"
  installed_count=$((installed_count + 1))
done

update-ca-certificates
log_info "installed ${installed_count} certificate(s) from ${CERT_DIR}"
