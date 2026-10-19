provider "aws" {
  region = var.aws_region

  # The module tags each resource itself; these defaults also cover anything
  # the provider creates on its behalf.
  default_tags {
    tags = merge(
      {
        Project     = "dev-container-fortress"
        Environment = "disposable"
        ManagedBy   = "terraform"
      },
      var.tags,
    )
  }
}
