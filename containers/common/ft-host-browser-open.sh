#!/bin/sh

# Open URLs in the host browser from inside a Dev Fortress workspace container.
# On WSL-backed hosts this bridges to Windows PowerShell when the host mounts
# are available; otherwise it falls back to xdg-open.

set -eu

if [ "$#" -lt 1 ]; then
  printf '%s\n' "usage: ft-host-browser-open <url>" >&2
  exit 2
fi

url="$1"
powershell_path="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
browser_socket="${DEV_FORTRESS_HOST_BROWSER_SOCKET:-}"

if [ -n "${browser_socket}" ] && [ -S "${browser_socket}" ]; then
  if python3 - "$browser_socket" "$url" <<'PY'
import socket
import sys

socket_path = sys.argv[1]
url = sys.argv[2]

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(socket_path)
client.sendall(f"{url}\n".encode("utf-8"))
response = client.recv(1024).decode("utf-8").strip()
client.close()
raise SystemExit(0 if response == "OK" else 1)
PY
  then
    exit 0
  fi
fi

if [ -x "${powershell_path}" ]; then
  escaped_url="$(printf '%s' "${url}" | sed "s/'/''/g")"
  exec "${powershell_path}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Start-Process '${escaped_url}'"
fi

if command -v xdg-open >/dev/null 2>&1; then
  exec xdg-open "$@"
fi

printf '%s\n' "no usable browser opener found" >&2
exit 1
