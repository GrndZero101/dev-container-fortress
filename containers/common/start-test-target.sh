#!/bin/sh

# Dev Fortress disposable test target entrypoint.
# Supports a plain sleep loop and an SSH-enabled foreground mode for the
# Ubuntu disposable test target.

set -eu

mode="${1:-sleep}"
authorized_key_source="${2:-}"
runtime_user="${DEV_FORTRESS_RUNTIME_USER:-vscode}"
runtime_home="${DEV_FORTRESS_RUNTIME_HOME:-/home/${runtime_user}}"

append_authorized_key() {
  key_file="${1}"
  ssh_dir="${runtime_home}/.ssh"
  authorized_keys_file="${ssh_dir}/authorized_keys"

  [ -r "${key_file}" ] || return 0
  key_line="$(tr -d '\r' < "${key_file}")"
  [ -n "${key_line}" ] || return 0

  install -d -m 700 -o "${runtime_user}" -g "${runtime_user}" "${ssh_dir}"
  touch "${authorized_keys_file}"
  chown "${runtime_user}:${runtime_user}" "${authorized_keys_file}"
  chmod 600 "${authorized_keys_file}"

  if ! grep -qxF "${key_line}" "${authorized_keys_file}" 2>/dev/null; then
    printf '%s\n' "${key_line}" >> "${authorized_keys_file}"
  fi
}

start_sshd() {
  append_authorized_key "${authorized_key_source}"
  passwd -d "${runtime_user}" >/dev/null 2>&1 || true
  mkdir -p /run/sshd
  ssh-keygen -A >/dev/null 2>&1

  cat > /tmp/dev-fortress-sshd_config <<EOF
Port 2222
ListenAddress 0.0.0.0
PidFile /run/sshd.pid
AuthorizedKeysFile .ssh/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
UsePAM no
PermitRootLogin no
PubkeyAuthentication yes
PrintMotd no
LogLevel VERBOSE
AllowUsers ${runtime_user}
Subsystem sftp internal-sftp
EOF

  exec /usr/sbin/sshd -D -e -f /tmp/dev-fortress-sshd_config
}

case "${mode}" in
  sshd)
    start_sshd
    ;;
  sleep)
    exec sleep infinity
    ;;
  *)
    printf '%s\n' "unsupported mode: ${mode}" >&2
    exit 1
    ;;
esac
