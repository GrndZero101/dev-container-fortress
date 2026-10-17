locals {
  ami_name = "${var.name}-${var.image_version}"

  default_tags = merge(
    {
      Project     = "dev-container-fortress"
      Environment = "image"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

# Private staging bucket for the image upload. EC2 snapshot import only reads
# disk images from S3.
resource "aws_s3_bucket" "image" {
  bucket_prefix = "${var.name}-image-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "image" {
  bucket = aws_s3_bucket.image.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "image" {
  bucket      = aws_s3_bucket.image.id
  key         = basename(var.image_path)
  source      = var.image_path
  source_hash = filemd5(var.image_path)
}

# VM Import service role. AWS requires the vmie principal and the fixed
# "vmimport" external ID.
data "aws_iam_policy_document" "vmimport_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["vmie.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:Externalid"
      values   = ["vmimport"]
    }
  }
}

data "aws_iam_policy_document" "vmimport" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.image.arn, "${aws_s3_bucket.image.arn}/*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ec2:CopySnapshot",
      "ec2:Describe*",
      "ec2:ModifySnapshotAttribute",
      "ec2:RegisterImage",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "vmimport" {
  name_prefix        = "${var.name}-vmimport-"
  description        = "VM Import service role for the Dev Fortress Arch AMI"
  assume_role_policy = data.aws_iam_policy_document.vmimport_assume_role.json
}

resource "aws_iam_role_policy" "vmimport" {
  name   = "vmimport"
  role   = aws_iam_role.vmimport.id
  policy = data.aws_iam_policy_document.vmimport.json
}

# IAM is eventually consistent; VM Import rejects a role whose policy has not
# propagated yet, so give a freshly created policy time to settle.
resource "time_sleep" "vmimport_policy_propagation" {
  create_duration = "20s"

  triggers = {
    policy = aws_iam_role_policy.vmimport.policy
  }
}

resource "aws_ebs_snapshot_import" "image" {
  description = "Arch Linux official cloud image ${var.image_version}"
  role_name   = aws_iam_role.vmimport.name

  disk_container {
    format = "VMDK"

    user_bucket {
      s3_bucket = aws_s3_bucket.image.id
      s3_key    = aws_s3_object.image.key
    }
  }

  timeouts {
    create = "60m"
  }

  tags = {
    Name = local.ami_name
  }

  depends_on = [time_sleep.vmimport_policy_propagation]
}

# The image is GPT with both a BIOS boot partition and an EFI system
# partition, so uefi-preferred boots on every current x86_64 instance family.
resource "aws_ami" "arch" {
  name                = local.ami_name
  description         = "Arch Linux official cloud image ${var.image_version} (arch-boxes), imported by Dev Fortress"
  virtualization_type = "hvm"
  architecture        = "x86_64"
  boot_mode           = "uefi-preferred"
  ena_support         = true
  imds_support        = "v2.0"
  root_device_name    = "/dev/xvda"

  ebs_block_device {
    device_name           = "/dev/xvda"
    snapshot_id           = aws_ebs_snapshot_import.image.id
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name = local.ami_name
  }
}
