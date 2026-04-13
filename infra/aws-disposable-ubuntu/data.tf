data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/${var.ubuntu_release}/stable/current/${local.ubuntu_arch[var.architecture]}/hvm/ebs-gp3/ami-id"
}

data "http" "current_public_ip" {
  count = length(var.ssh_ingress_cidrs) == 0 && var.auto_detect_ssh_ingress_cidr ? 1 : 0

  url = var.public_ip_check_url
}
