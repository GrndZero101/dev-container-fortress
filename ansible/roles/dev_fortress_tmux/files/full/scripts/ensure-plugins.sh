#!/bin/sh
# ensure-plugins.sh CONF PLUGINS_DIR: clone the tpm plugins CONF declares
# that PLUGINS_DIR lacks.
#
# Dev Fortress tmux profiles run this at startup, before they load any
# plugin, so a profile chosen later with `csm tmux-profile` works on its first
# start. The host bootstrap runs it once too, so plugins are there before
# that. Plugins already present are left alone: prefix + U (tpm) updates
# them. Prints one line per clone, and nothing when everything is present. A
# failed clone, such as on a box without internet, warns and carries on, so
# tmux still starts.
set -eu

conf=${1:?usage: ensure-plugins.sh CONF PLUGINS_DIR}
plugins=${2:?usage: ensure-plugins.sh CONF PLUGINS_DIR}

# The profiles declare plugins one per line as: set -g @plugin 'owner/repo'.
# tpm installs each into a directory named after the repo, so this does too
sed -n "s/^set -g @plugin '\([^']*\)'.*/\1/p" "$conf" | while IFS= read -r repo; do
  dest=$plugins/${repo##*/}
  [ -d "$dest" ] && continue
  printf 'dev-fortress tmux: cloning %s\n' "$repo"
  mkdir -p "$plugins"
  GIT_TERMINAL_PROMPT=0 git clone -q --depth 1 "https://github.com/$repo" "$dest" ||
    printf 'dev-fortress tmux: could not clone %s; tmux starts without it\n' "$repo" >&2
done
