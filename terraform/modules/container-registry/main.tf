# Required providers for this module
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# ECR Repositories
resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name        = "${var.project_name}-backend"
    Environment = var.environment
  }
}

resource "aws_ecr_repository" "ml_service" {
  name                 = "${var.project_name}-ml-service"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name        = "${var.project_name}-ml-service"
    Environment = var.environment
  }
}

# Build and push backend Docker image
resource "docker_image" "backend" {
  name = "${aws_ecr_repository.backend.repository_url}:latest"
  
  build {
    context    = var.backend_context
    dockerfile = var.backend_dockerfile
    platform   = "linux/amd64"
  }
  
  # Force rebuild when source files change
  triggers = {
    dir_sha = sha256(join("", [
      for f in fileset(var.backend_context, "**/*.go") : 
      filesha256("${var.backend_context}/${f}")
    ]))
  }
}

resource "docker_registry_image" "backend" {
  name = docker_image.backend.name
  
  # Force push when image changes
  triggers = {
    image_id = docker_image.backend.image_id
  }
}

# Build and push ML service Docker image
resource "docker_image" "ml_service" {
  name = "${aws_ecr_repository.ml_service.repository_url}:latest"
  
  build {
    context    = var.ml_service_context
    dockerfile = var.ml_service_dockerfile
    platform   = "linux/amd64"
  }
  
  # Force rebuild when source files change
  triggers = {
    dir_sha = sha256(join("", [
      for f in fileset(var.ml_service_context, "**/*.py") : 
      filesha256("${var.ml_service_context}/${f}")
    ]))
  }
}

resource "docker_registry_image" "ml_service" {
  name = docker_image.ml_service.name
  
  # Force push when image changes
  triggers = {
    image_id = docker_image.ml_service.image_id
  }
}