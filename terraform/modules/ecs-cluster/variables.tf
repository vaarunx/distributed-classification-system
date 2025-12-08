# variables.tf
variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "ECS security group ID"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "backend_task_role_arn" {
  description = "Backend task role ARN"
  type        = string
}

variable "ml_task_role_arn" {
  description = "ML task role ARN"
  type        = string
}

variable "backend_image_url" {
  description = "Backend Docker image URL"
  type        = string
}

variable "ml_service_image_url" {
  description = "ML service Docker image URL"
  type        = string
}

variable "backend_cpu" {
  description = "Backend CPU units"
  type        = number
}

variable "backend_memory" {
  description = "Backend memory"
  type        = number
}

variable "ml_cpu" {
  description = "ML CPU units"
  type        = number
}

variable "ml_memory" {
  description = "ML memory"
  type        = number
}

variable "backend_desired_count" {
  description = "Backend desired count"
  type        = number
}

variable "ml_desired_count" {
  description = "ML desired count"
  type        = number
}

variable "input_bucket_name" {
  description = "Input bucket name"
  type        = string
}

variable "output_bucket_name" {
  description = "Output bucket name"
  type        = string
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name"
  type        = string
}

variable "request_queue_url" {
  description = "Request queue URL"
  type        = string
}

variable "status_queue_url" {
  description = "Status queue URL"
  type        = string
}

variable "backend_target_group_arn" {
  description = "Backend target group ARN"
  type        = string
}

variable "alb_resource_label" {
  description = "ALB resource label for autoscaling policies (format: app/name/id)"
  type        = string
}

variable "target_group_resource_label" {
  description = "Target group resource label for autoscaling policies (format: targetgroup/name/id)"
  type        = string
}

variable "request_queue_name" {
  description = "Request queue name for SQS autoscaling"
  type        = string
}

variable "request_queue_arn" {
  description = "Request queue ARN for CloudWatch alarms"
  type        = string
}

variable "autoscaling_role_arn" {
  description = "IAM role ARN for autoscaling (LabRole)"
  type        = string
}

