# Inputs for the short-lived verification fleet. Each hosts entry becomes one
# ../modules/disposable-host instance named "<name>-<key>".
variable "aws_region" {
  description = "AWS region where the fleet should be created."
  type        = string
  default     = "ap-southeast-1"
}

variable "name" {
  description = "Fleet name: the prefix of every host name and the name of the one managed ft SSH key the fleet shares. ft sets it through TF_VAR_name."
  type        = string
  default     = "dev-fortress-fleet"
}

variable "hosts" {
  description = "Fleet hosts keyed by a short suffix. Drop an entry to skip that target, for example arch before infra/aws-arch-ami has registered an AMI."
  type = map(object({
    os             = string
    architecture   = string
    instance_type  = string
    ubuntu_release = optional(string, "26.04")
    alpine_release = optional(string, "3.24")
  }))
  default = {
    ubuntu-2404 = { os = "ubuntu", ubuntu_release = "24.04", architecture = "amd64", instance_type = "m8i.large" }
    ubuntu-2604 = { os = "ubuntu", ubuntu_release = "26.04", architecture = "arm64", instance_type = "m8g.large" }
    ubuntu-2610 = { os = "ubuntu", ubuntu_release = "26.10", architecture = "arm64", instance_type = "m8g.large" }
    arch        = { os = "arch", architecture = "amd64", instance_type = "m8i.large" }
    alpine      = { os = "alpine", alpine_release = "3.24", architecture = "arm64", instance_type = "m8g.large" }
  }
}

variable "ssh_public_key" {
  description = "Public key of the fleet's shared managed ft SSH key, registered as each host's EC2 key pair."
  type        = string
  sensitive   = true
}

variable "ssh_ingress_cidrs" {
  description = "Explicit CIDR blocks allowed to reach SSH on every fleet host. When empty, the current public IP is detected once."
  type        = list(string)
  default     = []
}

variable "public_ip_check_url" {
  description = "HTTP endpoint used to detect the caller public IP address when ssh_ingress_cidrs is empty."
  type        = string
  default     = "https://checkip.amazonaws.com/"
}

variable "enable_spot" {
  description = "When true, request every host as a one-time EC2 Spot instance; set false for the on-demand fallback."
  type        = bool
  default     = true
}

variable "root_volume_size_gib" {
  description = "Root volume size in GiB for each fleet host."
  type        = number
  default     = 20
}

variable "tags" {
  description = "Additional tags to apply to every fleet resource."
  type        = map(string)
  default     = {}
}
