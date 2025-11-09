# outputs.tf
output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution_role.arn
}

output "backend_task_role_arn" {
  value = aws_iam_role.backend_task_role.arn
}

output "ml_task_role_arn" {
  value = aws_iam_role.ml_task_role.arn
}