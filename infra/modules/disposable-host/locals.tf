locals {
  key_pair_name = coalesce(var.aws_key_pair_name, "${var.name}-ssh")

  # One entry per supported host OS. Add a target by adding an entry here, not
  # by branching on var.os elsewhere. Each entry resolves its AMI one of two
  # ways: a public SSM parameter path (ami_ssm_parameter, a format() template
  # whose %s becomes var.architecture), or the most recent AMI matching
  # ami_owners and ami_name_pattern, narrowed by ami_name_regex when the
  # publisher ships variants a glob cannot exclude. Set the unused fields to
  # null. Profiles must
  # not reference var.os or var.architecture: their validations read this map.
  # ssh_user is the login user the cloud image creates through cloud-init, and
  # ssm_agent says whether the image ships the Session Manager agent.
  os_profiles = {
    ubuntu = {
      ssh_user          = "ubuntu"
      ssm_agent         = true
      architectures     = ["amd64", "arm64"]
      ami_ssm_parameter = "/aws/service/canonical/ubuntu/server/${var.ubuntu_release}/stable/current/%s/hvm/ebs-gp3/ami-id"
      ami_owners        = null
      ami_name_pattern  = null
      ami_name_regex    = null
    }
    arch = {
      ssh_user          = "arch"
      ssm_agent         = false
      architectures     = ["amd64"]
      ami_ssm_parameter = null
      ami_owners        = ["self"]
      ami_name_pattern  = "${var.arch_ami_name_prefix}*"
      ami_name_regex    = null
    }
    # Alpine's own publisher account. The regex keeps the standard cloud-init
    # image and drops the metal and the separate x86_64 UEFI variants.
    alpine = {
      ssh_user          = "alpine"
      ssm_agent         = false
      architectures     = ["amd64", "arm64"]
      ami_ssm_parameter = null
      ami_owners        = ["538276064493"]
      ami_name_pattern  = "alpine-${var.alpine_release}.*-cloudinit-r*"
      ami_name_regex    = "^alpine-${replace(var.alpine_release, ".", "\\.")}\\.[0-9]+-(aarch64|x86_64)-cloudinit-r[0-9]+$"
    }
  }

  # EC2 AMI architecture names for the repo-wide amd64/arm64 vocabulary.
  ec2_architecture = {
    amd64 = "x86_64"
    arm64 = "arm64"
  }

  os_profile = local.os_profiles[var.os]
  ssh_user   = local.os_profile.ssh_user
  ami_id     = one(concat(data.aws_ssm_parameter.os_ami[*].value, [for lookup in data.aws_ami_ids.os_ami : lookup.ids[0]]))

  # Skip the Session Manager role for images without the agent; it cannot work.
  session_manager_enabled = var.enable_session_manager && local.os_profile.ssm_agent

  # Set on each resource rather than through provider default_tags, so several
  # hosts can share one provider in a fleet root.
  resource_tags = merge(
    {
      Name        = var.name
      Project     = "dev-container-fortress"
      Environment = "disposable"
      ManagedBy   = "terraform"
    },
    var.tags,
  )

  effective_ssh_ingress_cidrs = (
    length(var.ssh_ingress_cidrs) > 0
    ? var.ssh_ingress_cidrs
    : (
      var.auto_detect_ssh_ingress_cidr
      ? ["${trimspace(data.http.current_public_ip[0].response_body)}/32"]
      : []
    )
  )
}
