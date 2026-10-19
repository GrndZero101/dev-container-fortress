# Detected once for the whole fleet instead of once per host.
data "http" "current_public_ip" {
  count = length(var.ssh_ingress_cidrs) == 0 ? 1 : 0

  url = var.public_ip_check_url
}

locals {
  ssh_ingress_cidrs = (
    length(var.ssh_ingress_cidrs) > 0
    ? var.ssh_ingress_cidrs
    : ["${trimspace(data.http.current_public_ip[0].response_body)}/32"]
  )
}

module "host" {
  source   = "../modules/disposable-host"
  for_each = local.selected_hosts

  name          = "${var.name}-${each.key}"
  os            = each.value.os
  architecture  = each.value.architecture
  instance_type = each.value.instance_type
  # Each OS profile reads only its own release input.
  ubuntu_release = each.value.release
  alpine_release = each.value.release

  ssh_public_key               = var.ssh_public_key
  ssh_key_name                 = var.name
  ssh_ingress_cidrs            = local.ssh_ingress_cidrs
  auto_detect_ssh_ingress_cidr = false
  enable_spot                  = var.enable_spot
  root_volume_size_gib         = var.root_volume_size_gib
  tags                         = merge({ Fleet = var.name }, var.tags)
}
