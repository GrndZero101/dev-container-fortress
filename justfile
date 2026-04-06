set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

default:
	@just --list

test-build target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container build "{{target}}"

test-up target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container up "{{target}}"

test-validate target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container validate "{{target}}"

test-status target="":
	if [[ -n "{{target}}" ]]; then env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container status "{{target}}"; else env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container status; fi

test-logs target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container logs "{{target}}"

test-exec target="ubuntu" *args:
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container exec "{{target}}" {{args}}

test-shell target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container shell "{{target}}"

test-down target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container down "{{target}}"

test-reset target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft container reset "{{target}}"

test-ssh-key target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft host ssh-key "dev-fortress-{{target}}"

test-ssh target="ubuntu":
	ssh \
	  -o BatchMode=yes \
	  -o StrictHostKeyChecking=yes \
	  -o UserKnownHostsFile="${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/known_hosts/dev-fortress-{{target}}" \
	  -i "${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/ssh/dev-fortress-{{target}}/id_ed25519" \
	  -p 2222 \
	  vscode@127.0.0.1

test-ssh-probe target="ubuntu":
	env UV_CACHE_DIR="${TMPDIR:-/tmp}/dev-container-fortress-uv-cache" uv run --project ./ft ft host doctor "dev-fortress-{{target}}" --probe
