# outputs.tf
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "ml_service_name" {
  value = aws_ecs_service.ml_service.name
}

output "backend_autoscaling_target_id" {
  description = "Backend service autoscaling target ID"
  value       = aws_appautoscaling_target.backend.id
}

output "ml_autoscaling_target_id" {
  description = "ML service autoscaling target ID"
  value       = aws_appautoscaling_target.ml_service.id
}