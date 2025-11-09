# outputs.tf
output "alb_endpoint" {
  description = "ALB endpoint URL"
  value       = "http://${module.load_balancer.alb_dns_name}"
}

output "api_endpoints" {
  description = "API endpoints"
  value = {
    health = "http://${module.load_balancer.alb_dns_name}/health"
    submit = "http://${module.load_balancer.alb_dns_name}/submit"
    status = "http://${module.load_balancer.alb_dns_name}/status/{jobId}"
    result = "http://${module.load_balancer.alb_dns_name}/result/{jobId}"
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