resource "aws_cloudwatch_log_group" "svc" {
  for_each = local.task_defs

  name              = "/ecs/${var.project_name}/${each.key}"
  retention_in_days = 30
}
