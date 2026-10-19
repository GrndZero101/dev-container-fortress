# One disposable host. The resources live in the shared module so the fleet
# root in ../aws-test-fleet can create several hosts from the same definition.
module "host" {
  source = "../modules/disposable-host"

  name                         = var.name
  instance_type                = var.instance_type
  subnet_id                    = var.subnet_id
  os                           = var.os
  arch_ami_name_prefix         = var.arch_ami_name_prefix
  architecture                 = var.architecture
  ubuntu_release               = var.ubuntu_release
  alpine_release               = var.alpine_release
  root_volume_size_gib         = var.root_volume_size_gib
  ssh_public_key               = var.ssh_public_key
  aws_key_pair_name            = var.aws_key_pair_name
  ssh_ingress_cidrs            = var.ssh_ingress_cidrs
  auto_detect_ssh_ingress_cidr = var.auto_detect_ssh_ingress_cidr
  public_ip_check_url          = var.public_ip_check_url
  enable_spot                  = var.enable_spot
  spot_max_price               = var.spot_max_price
  assign_public_ip             = var.assign_public_ip
  enable_session_manager       = var.enable_session_manager
  ansible_python_interpreter   = var.ansible_python_interpreter
  tags                         = var.tags
}
