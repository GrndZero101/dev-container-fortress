data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "session_manager" {
  count = var.enable_session_manager ? 1 : 0

  name_prefix        = "${var.name}-ssm-"
  description        = "Instance role for Dev Fortress disposable Ubuntu hosts using AWS Systems Manager Session Manager"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name = "${var.name}-ssm-role"
  }
}

resource "aws_iam_role_policy_attachment" "session_manager_core" {
  count = var.enable_session_manager ? 1 : 0

  role       = aws_iam_role.session_manager[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "session_manager" {
  count = var.enable_session_manager ? 1 : 0

  name_prefix = "${var.name}-ssm-"
  role        = aws_iam_role.session_manager[0].name

  tags = {
    Name = "${var.name}-ssm-profile"
  }
}
