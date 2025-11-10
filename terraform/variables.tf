# variables.tf
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "distributed-classifier"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "backend_cpu" {
  description = "CPU units for backend service"
  type        = number
  default     = 256
}

variable "backend_memory" {
  description = "Memory for backend service"
  type        = number
  default     = 512
}

variable "ml_cpu" {
  description = "CPU units for ML service"
  type        = number
  default     = 1024
}

variable "ml_memory" {
  description = "Memory for ML service"
  type        = number
  default     = 4096
}

variable "backend_desired_count" {
  description = "Desired count for backend service"
  type        = number
  default     = 1
}

variable "ml_desired_count" {
  description = "Desired count for ML service"
  type        = number
  default     = 1
}