#!/usr/bin/env bash
# Session picker: an fzf popup over sesh, bound to prefix + T in tmux.conf.
#
# Lists running tmux sessions, sesh configs and zoxide directories; picking a
# directory creates (or switches to) a session for it. Based on the binding in
# the sesh README: https://github.com/joshmedeski/sesh
#
# Requires: sesh, fzf (fzf-tmux), fd. Esc/cancel is a no-op: `sesh connect ""`
# exits quietly.

# Catppuccin colours, read from the catppuccin tmux plugin's @thm_* palette so
# the picker follows @catppuccin_flavor. The role -> colour mapping is the
# official catppuccin/fzf theme; the fallbacks are its Mocha values.
IFS=' ' read -r bg fg surface0 surface1 overlay0 rosewater red mauve lavender < <(
  tmux display -p '#{@thm_bg} #{@thm_fg} #{@thm_surface_0} #{@thm_surface_1} #{@thm_overlay_0} #{@thm_rosewater} #{@thm_red} #{@thm_mauve} #{@thm_lavender}'
)
colors=(
  --color="bg+:${surface0:-#313244},bg:${bg:-#1e1e2e},spinner:${rosewater:-#f5e0dc},hl:${red:-#f38ba8}"
  --color="fg:${fg:-#cdd6f4},header:${red:-#f38ba8},info:${mauve:-#cba6f7},pointer:${rosewater:-#f5e0dc}"
  --color="marker:${lavender:-#b4befe},fg+:${fg:-#cdd6f4},prompt:${mauve:-#cba6f7},hl+:${red:-#f38ba8}"
  --color="selected-bg:${surface1:-#45475a}"
  --color="border:${overlay0:-#6c7086},label:${fg:-#cdd6f4}"
)

selection=$(
  sesh list --icons | fzf-tmux -p 80%,70% \
    "${colors[@]}" \
    --no-sort --ansi --border-label ' sesh ' --prompt '⚡  ' \
    --header '  ^a all ^t tmux ^g configs ^x zoxide ^d tmux kill ^f find' \
    --bind 'tab:down,btab:up' \
    --bind 'ctrl-a:change-prompt(⚡  )+reload(sesh list --icons)' \
    --bind 'ctrl-t:change-prompt(🪟  )+reload(sesh list -t --icons)' \
    --bind 'ctrl-g:change-prompt(⚙️  )+reload(sesh list -c --icons)' \
    --bind 'ctrl-x:change-prompt(📁  )+reload(sesh list -z --icons)' \
    --bind 'ctrl-f:change-prompt(🔎  )+reload(fd -H -d 2 -t d -E .Trash . ~)' \
    --bind 'ctrl-d:execute(tmux kill-session -t {2..})+change-prompt(⚡  )+reload(sesh list --icons)' \
    --preview-window 'right:55%' \
    --preview 'sesh preview {}'
)

sesh connect "$selection"
