# outputs.tf
output "alb_arn" {
  value = aws_lb.main.arn
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "backend_target_group_arn" {
  value = aws_lb_target_group.backend.arn
}

output "listener_arn" {
  value = aws_lb_listener.main.arn
}

output "alb_resource_label" {
  description = "ALB resource label for autoscaling policies (format: app/name/id)"
  # Extract: app/load-balancer-name/load-balancer-id from ARN
  # ARN format: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
  # Need: app/name/id (extract everything after "loadbalancer/app/")
  # Using regexreplace to extract: loadbalancer/app/name/id -> app/name/id
  value = regex("app/.*$", aws_lb.main.arn)
}

output "target_group_resource_label" {
  description = "Target group resource label for autoscaling policies (format: targetgroup/name/id)"
  # Extract: targetgroup/target-group-name/target-group-id from ARN
  # ARN format: arn:aws:elasticloadbalancing:region:account:targetgroup/name/id
  # Need: targetgroup/name/id (extract everything after account ID, ensure targetgroup/ prefix)
  # Example: arn:aws:elasticloadbalancing:us-east-1:123:targetgroup/tg-name/123456 -> targetgroup/tg-name/123456
  value = replace(aws_lb_target_group.backend.arn, "/^.*:targetgroup\\//", "targetgroup/")
}