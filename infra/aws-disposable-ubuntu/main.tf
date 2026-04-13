resource "aws_key_pair" "this" {
  key_name   = local.key_pair_name
  public_key = trimspace(var.ssh_public_key)
}

resource "aws_security_group" "ssh" {
  name_prefix = "${var.name}-ssh-"
  description = "SSH access for the Dev Fortress disposable Ubuntu host"
  vpc_id      = data.aws_vpc.default.id

  lifecycle {
    precondition {
      condition     = length(local.effective_ssh_ingress_cidrs) > 0
      error_message = "At least one SSH ingress CIDR must be supplied explicitly or detected automatically."
    }
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = local.effective_ssh_ingress_cidrs
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "this" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.ssh.id]
  key_name                    = aws_key_pair.this.key_name
  iam_instance_profile        = var.enable_session_manager ? aws_iam_instance_profile.session_manager[0].name : null
  associate_public_ip_address = var.assign_public_ip

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gib
    encrypted             = true
    delete_on_termination = true
  }

  dynamic "instance_market_options" {
    for_each = var.enable_spot ? [1] : []

    content {
      market_type = "spot"

      spot_options {
        instance_interruption_behavior = "terminate"
        spot_instance_type             = "one-time"
        max_price                      = var.spot_max_price
      }
    }
  }

  tags = {
    Name = var.name
  }
}
