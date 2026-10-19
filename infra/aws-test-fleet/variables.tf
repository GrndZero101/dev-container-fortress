# Inputs for the short-lived verification fleet. Each selected host becomes one
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

variable "fleet_set" {
  description = "Named host set from local.fleet_sets: lts (default) spot-checks the current Ubuntu LTS on amd64 and arm64; full covers every OS target on both architectures, for major milestones. ft infra aws-test-fleet --set saves the choice."
  type        = string
  default     = "lts"

  validation {
    condition     = contains(keys(local.fleet_sets), var.fleet_set)
    error_message = "fleet_set must be one of: ${join(", ", keys(local.fleet_sets))}."
  }
}

variable "hosts" {
  description = "Optional custom host map that replaces fleet_set, keyed by a short suffix. release defaults per OS, and instance_type defaults from instance_types by architecture."
  type = map(object({
    os            = string
    architecture  = string
    release       = optional(string)
    instance_type = optional(string)
  }))
  default = null
}

variable "instance_types" {
  description = "Instance type per architecture. The defaults are matched shapes (2 vCPU, 8 GiB), so amd64 and arm64 hosts mirror each other."
  type        = map(string)
  default = {
    amd64 = "m8i.large"
    arm64 = "m8g.large"
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
