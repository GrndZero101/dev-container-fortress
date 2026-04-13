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

variable "architecture" {
  description = "Instance architecture used to choose the Ubuntu AMI."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["amd64", "arm64"], var.architecture)
    error_message = "architecture must be either amd64 or arm64."
  }
}

variable "ubuntu_release" {
  description = "Ubuntu release codename used for the SSM-published AMI path."
  type        = string
  default     = "noble"
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
  description = "When true, attach the standard IAM role and instance profile needed for AWS Systems Manager Session Manager."
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
