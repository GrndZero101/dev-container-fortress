# Hosts applied before the resources moved into ../modules/disposable-host keep
# their state; Terraform maps the old addresses onto the module.

moved {
  from = aws_key_pair.this
  to   = module.host.aws_key_pair.this
}

moved {
  from = aws_security_group.ssh
  to   = module.host.aws_security_group.ssh
}

moved {
  from = aws_instance.this
  to   = module.host.aws_instance.this
}

moved {
  from = aws_iam_role.session_manager
  to   = module.host.aws_iam_role.session_manager
}

moved {
  from = aws_iam_role_policy_attachment.session_manager_core
  to   = module.host.aws_iam_role_policy_attachment.session_manager_core
}

moved {
  from = aws_iam_instance_profile.session_manager
  to   = module.host.aws_iam_instance_profile.session_manager
}
