data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Exactly one of the two OS AMI lookups runs, chosen by the active OS profile.
data "aws_ssm_parameter" "os_ami" {
  count = local.os_profile.ami_ssm_parameter != null ? 1 : 0

  name = format(local.os_profile.ami_ssm_parameter, var.architecture)
}

# aws_ami_ids returns an empty list instead of failing, so the postcondition
# can say how to fix a missing image. The ids come newest first.
data "aws_ami_ids" "os_ami" {
  count = local.os_profile.ami_ssm_parameter == null ? 1 : 0

  owners     = local.os_profile.ami_owners
  name_regex = local.os_profile.ami_name_regex

  filter {
    name   = "name"
    values = [local.os_profile.ami_name_pattern]
  }

  filter {
    name   = "architecture"
    values = [local.ec2_architecture[var.architecture]]
  }

  lifecycle {
    postcondition {
      condition     = length(self.ids) > 0
      error_message = "No ${var.os} AMI matches ${local.os_profile.ami_name_pattern} for ${var.architecture}.${var.os == "arch" ? " Build the private Arch AMI with infra/aws-arch-ami first, or drop arch from the hosts." : ""}"
    }
  }
}

data "http" "current_public_ip" {
  count = length(var.ssh_ingress_cidrs) == 0 && var.auto_detect_ssh_ingress_cidr ? 1 : 0

  url = var.public_ip_check_url
}
