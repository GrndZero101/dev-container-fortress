locals {
  key_pair_name = coalesce(var.aws_key_pair_name, "${var.name}-ssh")

  ubuntu_arch = {
    amd64 = "amd64"
    arm64 = "arm64"
  }

  default_tags = merge(
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
