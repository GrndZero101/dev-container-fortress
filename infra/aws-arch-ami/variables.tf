variable "aws_region" {
  description = "AWS region where the Arch AMI should be registered."
  type        = string
  default     = "ap-southeast-1"
}

variable "name" {
  description = "Stable basename for the AMI and related resources. The disposable host stack looks AMIs up by this prefix."
  type        = string
  default     = "dev-fortress-arch"
}

variable "image_version" {
  description = "Arch cloud image version prepared by prepare-image.zsh, for example 20261015.611680."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{8}\\.[0-9]+$", var.image_version))
    error_message = "image_version must look like YYYYMMDD.BUILD, matching the arch-boxes release naming."
  }
}

variable "image_path" {
  description = "Local path to the verified stream-optimized VMDK printed by prepare-image.zsh."
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to created resources."
  type        = map(string)
  default     = {}
}
