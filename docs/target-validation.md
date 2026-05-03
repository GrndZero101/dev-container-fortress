# Target Validation

This document captures the current end-to-end validation loop across the three
main Dev Fortress SSH targets:

- disposable Ubuntu container
- disposable Alpine container
- disposable Ubuntu EC2 host

It is intentionally procedural for now.
The long-term goal is to collapse more of this into higher-level `ft` commands,
but this runbook reflects the operator loop that exists today.

The preferred validation command is now:

```zsh
uv run ft host validate <target>
```

Or interactively:

```zsh
uv run ft host validate --interactive
```

The same selector is also available on high-touch host commands:

```zsh
uv run ft host doctor --interactive --probe
uv run ft host ssh --interactive
```

That wraps the current standard loop:

- `ft host doctor --probe`
- `ft host bootstrap --check`
- `ft host bootstrap`
- a second `ft host bootstrap` convergence pass

## Prerequisites

- local repo bootstrap already completed
- Docker available for the disposable container targets
- AWS credentials already configured for the disposable EC2 stack
- [`infra/aws-disposable-ubuntu/terraform.tfvars`](/Users/timl/projects/github/GrndZero101/tboss/dev-container-fortress/infra/aws-disposable-ubuntu/terraform.tfvars)
  already populated with the stable values you want to use

All commands below are run from:

```zsh
cd /Users/timl/projects/github/GrndZero101/tboss/dev-container-fortress
```

## 1. Build the Container Targets

```zsh
uv run ft container build ubuntu
uv run ft container build alpine
```

## 2. Provision the Disposable EC2 Ubuntu Host

```zsh
uv run ft infra aws-disposable-ubuntu plan
uv run ft infra aws-disposable-ubuntu apply
```

This wrapper:

- ensures the managed SSH key exists from the stack seed config
- injects the key into Terraform through `TF_VAR_ssh_public_key`
- applies the stack
- imports the emitted EC2 target into
  [`~/.config/dev-container-fortress/hosts.toml`](/Users/timl/.config/dev-container-fortress/hosts.toml)

## 3. Validate All Three Targets

Preferred loop:

```zsh
uv run ft host validate dev-fortress-ubuntu
uv run ft host validate dev-fortress-alpine
uv run ft host validate dev-fortress-ec2-dev
```

Or validate the whole currently configured/default target set:

```zsh
uv run ft host validate all
```

Or open an interactive selector against a narrowed target subset:

```zsh
uv run ft host validate 'dev-fortress-*' --interactive
```

The remaining sections below show the expanded command-by-command version of
the same loop.

## 4. Probe All Three Targets

```zsh
uv run ft host doctor dev-fortress-ubuntu --probe
uv run ft host doctor dev-fortress-alpine --probe
uv run ft host doctor dev-fortress-ec2-dev --probe
```

## 5. Bootstrap All Three Targets

```zsh
uv run ft host bootstrap dev-fortress-ubuntu
uv run ft host bootstrap dev-fortress-alpine
uv run ft host bootstrap dev-fortress-ec2-dev
```

What this currently proves:

- XDG layout convergence
- baseline package convergence on Ubuntu and Alpine
- `shell-config` clone and bootstrap
- login shell convergence to `zsh` for remote SSH targets
- readiness reporting for shell-config activation

## 6. Re-run Bootstrap to Confirm Convergence

Run the same bootstrap commands again:

```zsh
uv run ft host bootstrap dev-fortress-ubuntu
uv run ft host bootstrap dev-fortress-alpine
uv run ft host bootstrap dev-fortress-ec2-dev
```

The expected result on the second run is `changed=0`.
That is now part of the `ft host validate ...` convergence contract rather than
just a manual eyeball check.

That second pass matters because Dev Fortress is aiming for a convergent
level-set model rather than one-shot provisioning.

## 7. Test Managed SSH Access Against Each Target

```zsh
uv run ft host ssh dev-fortress-ubuntu
uv run ft host ssh dev-fortress-alpine
uv run ft host ssh dev-fortress-ec2-dev
```

Current behavior:

- the Docker SSH targets auto-start their matching disposable containers if needed
- the EC2 target uses the imported user config
- all three reuse the Dev Fortress managed SSH key and managed `known_hosts` policy

## 8. Tear Down the Disposable EC2 Host

```zsh
uv run ft infra aws-disposable-ubuntu destroy
```

## Current Limitation

The default host view now layers the built-in example targets underneath the
user host config, which removes most `--config` friction for the Docker targets.

The current interactive selector is intentionally simple:

- type to filter by target name, kind, or tags
- use Up/Down to move
- use Space to toggle selections
- use Enter to confirm

The remaining ergonomic gap is extending the same interactive pattern across
more host and container commands.
