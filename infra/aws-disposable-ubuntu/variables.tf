# Operator-facing inputs for the single-host root. They pass straight through to
# ../modules/disposable-host, which owns the OS-profile validations.
variable "aws_region" {
  description = "AWS region where the disposable host should be created."
  type        = string
  default     = "ap-southeast-1"
}

variable "name" {
  description = "Stable basename for the disposable host and related resources."
  type        = string
  default     = "dev-fortress-ubuntu-disposable"
}

variable "instance_type" {
  description = "EC2 instance type to use when launching the host."
  type        = string
  default     = "t4g.small"
}

variable "subnet_id" {
  description = "Optional subnet ID to launch into. When null, the first default VPC subnet is used."
  type        = string
  default     = null
}

variable "os" {
  description = "Host operating system; one key of local.os_profiles. ubuntu uses the Canonical SSM-published AMI, arch the private AMI from infra/aws-arch-ami, and alpine the official Alpine cloud-init AMI."
  type        = string
  default     = "ubuntu"
}

variable "arch_ami_name_prefix" {
  description = "Name prefix of the self-owned Arch AMIs registered by infra/aws-arch-ami; the most recent match is used."
  type        = string
  default     = "dev-fortress-arch-"
}

variable "architecture" {
  description = "Instance architecture used to choose the AMI. Each OS profile lists the architectures it supports; arch is amd64 only."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["amd64", "arm64"], var.architecture)
    error_message = "architecture must be either amd64 or arm64."
  }
}

variable "ubuntu_release" {
  description = "Ubuntu release for the SSM-published AMI path, as a version such as 26.04 or 26.10, or a codename. Defaults to the current LTS."
  type        = string
  default     = "26.04"
}

variable "alpine_release" {
  description = "Alpine release series for the official cloud-init AMI, such as 3.24; the newest patch release is used."
  type        = string
  default     = "3.24"
}

variable "root_volume_size_gib" {
  description = "Root volume size in GiB for the disposable host."
  type        = number
  default     = 20
}

variable "ssh_public_key" {
  description = "Public SSH key material to register as an EC2 key pair."
  type        = string
  sensitive   = true
}

variable "aws_key_pair_name" {
  description = "Optional EC2 key pair name. Defaults to a name derived from the target."
  type        = string
  default     = null
}

variable "ssh_ingress_cidrs" {
  description = "Explicit CIDR blocks allowed to reach SSH on the disposable host. When empty, the current public IP can be auto-detected."
  type        = list(string)
  default     = []
}

variable "auto_detect_ssh_ingress_cidr" {
  description = "When true and ssh_ingress_cidrs is empty, detect the caller public IP and allow SSH from that /32."
  type        = bool
  default     = true
}

variable "public_ip_check_url" {
  description = "HTTP endpoint used to detect the caller public IP address when auto_detect_ssh_ingress_cidr is enabled."
  type        = string
  default     = "https://checkip.amazonaws.com/"
}

variable "enable_spot" {
  description = "When true, request the instance as a one-time EC2 Spot instance."
  type        = bool
  default     = true
}

variable "spot_max_price" {
  description = "Optional maximum Spot price in USD per hour."
  type        = string
  default     = null
}

variable "assign_public_ip" {
  description = "Whether to associate a public IP address to the instance."
  type        = bool
  default     = true
}

variable "enable_session_manager" {
  description = "When true, attach the standard IAM role and instance profile needed for AWS Systems Manager Session Manager. Ignored for OS profiles whose image has no SSM agent."
  type        = bool
  default     = true
}

variable "ansible_python_interpreter" {
  description = "Interpreter path that should be exported for ft host handoff."
  type        = string
  default     = "/usr/bin/python3"
}

variable "tags" {
  description = "Additional tags to apply to created resources."
  type        = map(string)
  default     = {}
}
