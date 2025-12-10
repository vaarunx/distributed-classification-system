# outputs.tf
output "alb_endpoint" {
  description = "ALB endpoint URL"
  value       = "http://${module.load_balancer.alb_dns_name}"
}

output "backend_api_url" {
  description = "Backend API base URL"
  value       = "http://${module.load_balancer.alb_dns_name}"
}

output "api_endpoints" {
  description = "API endpoints"
  value = {
    health = "http://${module.load_balancer.alb_dns_name}/health"
    submit = "http://${module.load_balancer.alb_dns_name}/submit"
    status = "http://${module.load_balancer.alb_dns_name}/status/{jobId}"
    result = "http://${module.load_balancer.alb_dns_name}/result/{jobId}"
    upload_url = "http://${module.load_balancer.alb_dns_name}/upload-url"
    images = "http://${module.load_balancer.alb_dns_name}/images"
  }
}

output "aws_resources" {
  description = "AWS resource identifiers"
  value = {
    cluster_name   = module.ecs_cluster.cluster_name
    input_bucket   = module.storage.input_bucket_name
    output_bucket  = module.storage.output_bucket_name
    dynamodb_table = module.storage.dynamodb_table_name
    request_queue  = module.queues.request_queue_name
    status_queue   = module.queues.status_queue_name
  }
}

# Direct outputs for scripts
output "cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs_cluster.cluster_name
}

output "backend_service_name" {
  description = "Backend ECS service name"
  value       = module.ecs_cluster.backend_service_name
}

output "ml_service_name" {
  description = "ML service ECS service name"
  value       = module.ecs_cluster.ml_service_name
}

output "alb_resource_label" {
  description = "ALB resource label for CloudWatch metrics (format: app/name/id)"
  value       = module.load_balancer.alb_resource_label
}

output "target_group_resource_label" {
  description = "Target group resource label for CloudWatch metrics (format: targetgroup/name/id)"
  value       = module.load_balancer.target_group_resource_label
}