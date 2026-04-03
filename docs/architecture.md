# Architecture

## Layering

`dev-container-fortress` is a provisioning and packaging repository.

It should orchestrate:

- host installation
- container image creation
- VS Code devcontainer wrapping

It should not become the place where shell behavior is defined.

That responsibility belongs to the external `shell-config` repository.

## Tooling Split

### Host targets

Use:

- Ansible for orchestration
- Homebrew for packages and userland tools
- `tenv` for Terraform and OpenTofu version selection

### Container targets

Use:

- Dockerfiles for image construction
- Python + `uv` for pinned userland tool installation
- `tenv` as the first packaged DevOps tool

### Devcontainer target

Use:

- the Docker target as the base
- VS Code metadata as a thin wrapper

## Rationale

- Ansible gives idempotent machine provisioning.
- Brew reduces maintenance burden on real machines.
- Containers benefit from pinned binary installs more than Brew.
- `tenv` keeps Terraform and OpenTofu version management out of the base image design.
- Keeping `shell-config` separate preserves modularity and reuse.
