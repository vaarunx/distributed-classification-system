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