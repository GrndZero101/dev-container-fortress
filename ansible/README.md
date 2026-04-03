# Ansible

This directory contains host-install automation for:

- macOS
- Linux
- WSL

The intent is to keep host provisioning idempotent and high level while leaving
component-specific behavior inside the relevant component repositories.

Examples:

- `shell-config` owns shell behavior
- tmux config should own tmux behavior
- this layer installs and wires those components together

