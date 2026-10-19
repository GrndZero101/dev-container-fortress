output "hosts" {
  description = "Connection facts for each fleet host, keyed by host name."
  value = {
    for key, host in module.host : "${var.name}-${key}" => {
      os              = local.selected_hosts[key].os
      architecture    = local.selected_hosts[key].architecture
      instance_type   = local.selected_hosts[key].instance_type
      capacity_market = host.capacity_market
      instance_id     = host.instance_id
      public_dns      = host.public_dns
      public_ip       = host.public_ip
      ssh_user        = host.ssh_user
    }
  }
}

# ft host import-terraform reads this one output, so the fleet emits every
# host's [[targets]] block in a single TOML document.
output "host_target_toml_fragment" {
  description = "TOML [[targets]] blocks for every fleet host, ready for ft host import-terraform."
  value       = join("\n", [for key in sort(keys(module.host)) : module.host[key].host_target_toml_fragment])
}

output "fleet_set" {
  description = "Named host set this fleet was created from, or custom for a hosts map."
  value       = var.hosts != null ? "custom" : var.fleet_set
}

output "ssh_key_name" {
  description = "Managed ft SSH key name that every fleet host trusts."
  value       = var.name
}

output "aws_region" {
  description = "AWS region where the fleet was provisioned."
  value       = var.aws_region
}
