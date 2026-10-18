# Same output names as before the module split, because ft reads them.

output "instance_id" {
  description = "EC2 instance identifier for the disposable host."
  value       = module.host.instance_id
}

output "public_ip" {
  description = "Public IPv4 address for the disposable host."
  value       = module.host.public_ip
}

output "public_dns" {
  description = "Public DNS name for the disposable host."
  value       = module.host.public_dns
}

output "subnet_id" {
  description = "Subnet where the disposable host was provisioned."
  value       = module.host.subnet_id
}

output "availability_zone" {
  description = "Availability Zone where the disposable host was provisioned."
  value       = module.host.availability_zone
}

output "capacity_market" {
  description = "Capacity market used by the disposable host."
  value       = module.host.capacity_market
}

output "ssh_user" {
  description = "SSH user created by the cloud image."
  value       = module.host.ssh_user
}

output "ssh_port" {
  description = "SSH port exposed by the disposable host."
  value       = module.host.ssh_port
}

output "ansible_python_interpreter" {
  description = "Interpreter path expected by ft host and Ansible."
  value       = module.host.ansible_python_interpreter
}

output "key_pair_name" {
  description = "EC2 key pair name used by the disposable host."
  value       = module.host.key_pair_name
}

output "session_manager_enabled" {
  description = "Whether the disposable host was provisioned with an IAM instance profile for Session Manager."
  value       = module.host.session_manager_enabled
}

output "session_manager_role_name" {
  description = "IAM role name attached for Session Manager access, when enabled."
  value       = module.host.session_manager_role_name
}

output "session_manager_instance_profile_name" {
  description = "IAM instance profile attached for Session Manager access, when enabled."
  value       = module.host.session_manager_instance_profile_name
}

output "effective_ssh_ingress_cidrs" {
  description = "CIDR blocks actually used to permit SSH access to the disposable host."
  value       = module.host.effective_ssh_ingress_cidrs
}

output "host_target_toml_fragment" {
  description = "Convenience TOML fragment that can be copied into hosts.toml."
  value       = module.host.host_target_toml_fragment
}

output "aws_region" {
  description = "AWS region where the disposable host was provisioned."
  value       = var.aws_region
}
