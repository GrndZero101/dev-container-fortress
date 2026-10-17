output "ami_id" {
  description = "Private Arch Linux AMI identifier."
  value       = aws_ami.arch.id
}

output "ami_name" {
  description = "Private Arch Linux AMI name; the disposable host stack looks it up by the name prefix."
  value       = aws_ami.arch.name
}

output "snapshot_id" {
  description = "EBS snapshot backing the AMI."
  value       = aws_ebs_snapshot_import.image.id
}

output "image_bucket" {
  description = "Private S3 staging bucket holding the uploaded image."
  value       = aws_s3_bucket.image.id
}
