provider "aws" {
  region = var.aws_region

  # Each host module tags its own resources; these defaults cover anything the
  # provider creates on their behalf.
  default_tags {
    tags = merge(
      {
        Project     = "dev-container-fortress"
        Environment = "disposable"
        ManagedBy   = "terraform"
        Fleet       = var.name
      },
      var.tags,
    )
  }
}
