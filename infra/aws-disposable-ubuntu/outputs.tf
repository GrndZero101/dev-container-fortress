output "instance_id" {
  description = "EC2 instance identifier for the disposable host."
  value       = aws_instance.this.id
}

output "public_ip" {
  description = "Public IPv4 address for the disposable host."
  value       = aws_instance.this.public_ip
}

output "public_dns" {
  description = "Public DNS name for the disposable host."
  value       = aws_instance.this.public_dns
}

output "ssh_user" {
  description = "SSH user expected by the Ubuntu cloud image."
  value       = "ubuntu"
}

output "ssh_port" {
  description = "SSH port exposed by the disposable host."
  value       = 22
}

output "ansible_python_interpreter" {
  description = "Interpreter path expected by ft host and Ansible."
  value       = var.ansible_python_interpreter
}

output "aws_region" {
  description = "AWS region where the disposable host was provisioned."
  value       = var.aws_region
}

output "key_pair_name" {
  description = "EC2 key pair name used by the disposable host."
  value       = aws_key_pair.this.key_name
}

output "session_manager_enabled" {
  description = "Whether the disposable host was provisioned with an IAM instance profile for Session Manager."
  value       = var.enable_session_manager
}

output "session_manager_role_name" {
  description = "IAM role name attached for Session Manager access, when enabled."
  value       = var.enable_session_manager ? aws_iam_role.session_manager[0].name : null
}

output "session_manager_instance_profile_name" {
  description = "IAM instance profile attached for Session Manager access, when enabled."
  value       = var.enable_session_manager ? aws_iam_instance_profile.session_manager[0].name : null
}

output "effective_ssh_ingress_cidrs" {
  description = "CIDR blocks actually used to permit SSH access to the disposable host."
  value       = local.effective_ssh_ingress_cidrs
}

output "host_target_toml_fragment" {
  description = "Convenience TOML fragment that can be copied into hosts.toml."
  value       = <<-EOT
    [[targets]]
    name = "${var.name}"
    kind = "cloud"
    connection = "ssh"
    host = "${aws_instance.this.public_dns != "" ? aws_instance.this.public_dns : aws_instance.this.public_ip}"
    port = 22
    user = "ubuntu"
    auth_method = "ssh_key"
    ssh_key_name = "${var.name}"
    ansible_python_interpreter = "${var.ansible_python_interpreter}"
    tags = ["ssh", "ubuntu", "cloud", "disposable"]
  EOT
}
