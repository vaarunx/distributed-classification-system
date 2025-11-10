# variables.tf
variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "backend_dockerfile" {
  description = "Path to backend Dockerfile"
  type        = string
}

variable "backend_context" {
  description = "Docker build context for backend"
  type        = string
}

variable "ml_service_dockerfile" {
  description = "Path to ML service Dockerfile"
  type        = string
}

variable "ml_service_context" {
  description = "Docker build context for ML service"
  type        = string
}
