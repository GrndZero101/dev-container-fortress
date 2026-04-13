# AWS Disposable Ubuntu

This directory is reserved for the first real-cloud Dev Fortress host target.

The intended use is:

- provision one cheap disposable Ubuntu VM, likely EC2 Spot first
- output the minimal connection facts needed to join the existing
  `ft host ...` workflow
- destroy the VM cleanly after validation

The first pass should favor:

- simple public reachability over complex networking
- explicit SSH user and AMI assumptions
- low-cost disposable testing over broad cloud abstraction
- a fixed documented instance-shape fallback even if spot-selection helpers are added

The target is not meant to become a generic AWS platform module on day one.
It exists to prove the Dev Fortress host loop against a real VM.

## Validation Status

This stack has now been exercised against a real Ubuntu EC2 instance in
`ap-southeast-1`:

- Terraform provisioned the host successfully
- the generated target flowed into `ft host doctor --probe`
- `ft host bootstrap --check` and normal bootstrap both succeeded
- Session Manager console access worked after the instance profile was attached

Final `terraform destroy` validation on the currently live host is still the
remaining closeout step before the side quest can be marked fully complete.

## Current Shape

The first Terraform pass here is intentionally small:

- default-VPC-first networking
- one SSH security group
- one Ubuntu EC2 instance
- one EC2 IAM role and instance profile for AWS Systems Manager Session Manager
- optional Spot market request with a fixed fallback instance shape
- one EC2 key pair created from operator-supplied public key material
- dynamic SSH ingress detection from the current public IP when explicit CIDRs are not supplied
- outputs that can be copied into `hosts.toml`

This is intentionally not a full AWS platform layer.

## Files

- `versions.tf`: Terraform and provider requirements
- `providers.tf`: AWS provider setup
- `variables.tf`: operator-facing inputs
- `data.tf`: default VPC and Ubuntu AMI lookup
- `iam.tf`: Session Manager role, policy attachment, and instance profile
- `main.tf`: key pair, security group, and instance resources
- `outputs.tf`: connection facts and a convenience TOML fragment
- `terraform.tfvars.example`: example local input file

## Expected Operator Flow

1. Create a managed SSH key for the future host target name.
2. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in real values.
3. Run `terraform init`, `terraform plan`, and `terraform apply`.
4. Copy the `host_target_toml_fragment` output into `hosts.toml`.
5. Run `uv run ft host doctor <target> --probe`.
6. Run `uv run ft host bootstrap <target> --check`.
7. Run `uv run ft host bootstrap <target>`.
8. Destroy the host when validation is complete.

Example bootstrap of the managed SSH key:

```zsh
uv run ft host ssh-key dev-fortress-ec2-dev --config hosts.seed.toml
cat "${XDG_STATE_HOME:-$HOME/.local/state}/dev-container-fortress/ssh/dev-fortress-ec2-dev/dev_fortress_ed25519.pub"
```

Example Terraform loop:

```zsh
cd infra/aws-disposable-ubuntu
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
terraform output host_target_toml_fragment
```

When `enable_session_manager = true` (the default), the instance is also given
an IAM role and instance profile with the AWS-managed
`AmazonSSMManagedInstanceCore` policy. That is the main requirement for opening
an AWS Systems Manager Session Manager shell from the EC2 console. For standard
Ubuntu AWS images, we currently assume the SSM Agent is already present.

By default the plan can detect your current public IP using
`https://checkip.amazonaws.com/` and turn it into a `/32` SSH ingress rule.
If you prefer explicit access rules, set `ssh_ingress_cidrs` yourself and
disable `auto_detect_ssh_ingress_cidr`.

Destroy when done:

```zsh
terraform destroy
```

## Current Assumptions

- AWS credentials are available through the normal Terraform AWS provider chain
- the AWS account has a default VPC and default subnets in the chosen region
- Ubuntu cloud images use the `ubuntu` SSH user
- standard Ubuntu AWS images already include the SSM Agent for Session Manager
- the operator supplies a trusted CIDR for SSH ingress
- ARM64 is the default cost-conscious path, with a fixed instance-type fallback

These assumptions are deliberate for the first real-cloud pass and can be
broadened later if the workflow proves valuable.
