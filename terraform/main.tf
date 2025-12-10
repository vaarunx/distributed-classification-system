terraform {
  required_version = ">= 1.0"
  
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

# Add this after the providers and before the modules
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

provider "aws" {
  region = var.aws_region
}

provider "docker" {
  registry_auth {
    address  = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
    username = data.aws_ecr_authorization_token.token.user_name
    password = data.aws_ecr_authorization_token.token.password
  }
}

data "aws_caller_identity" "current" {}
data "aws_ecr_authorization_token" "token" {}

# Networking Module
module "networking" {
  source = "./modules/networking"
  
  project_name = var.project_name
  environment  = var.environment
}

# Storage Module
module "storage" {
  source = "./modules/storage"
  
  project_name = var.project_name
  environment  = var.environment
}

# Queues Module
module "queues" {
  source = "./modules/queues"
  
  project_name = var.project_name
  environment  = var.environment
}

# Container Registry Module (Handles Docker builds!)
module "container_registry" {
  source = "./modules/container-registry"
  
  project_name          = var.project_name
  environment           = var.environment
  backend_dockerfile    = "${path.root}/../backend-service/Dockerfile"
  backend_context       = "${path.root}/../backend-service"
  ml_service_dockerfile = "${path.root}/../ml-service/Dockerfile"
  ml_service_context    = "${path.root}/../ml-service"
}

# Load Balancer Module
module "load_balancer" {
  source = "./modules/load-balancer"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.networking.vpc_id
  subnet_ids   = module.networking.public_subnet_ids
  alb_sg_id    = module.networking.alb_security_group_id
}

# ECS Cluster Module
module "ecs_cluster" {
  source = "./modules/ecs-cluster"
  
  project_name                = var.project_name
  environment                 = var.environment
  
  # Networking
  vpc_id                      = module.networking.vpc_id
  private_subnet_ids          = module.networking.private_subnet_ids
  ecs_security_group_id       = module.networking.ecs_security_group_id
  
# IAM Roles
  ecs_task_execution_role_arn = data.aws_iam_role.lab_role.arn
  backend_task_role_arn       = data.aws_iam_role.lab_role.arn
  ml_task_role_arn           = data.aws_iam_role.lab_role.arn
  
  # Container Images (from container_registry module)
  backend_image_url           = module.container_registry.backend_image_url
  ml_service_image_url        = module.container_registry.ml_service_image_url
  
  # Configuration
  backend_cpu                 = var.backend_cpu
  backend_memory              = var.backend_memory
  ml_cpu                      = var.ml_cpu
  ml_memory                   = var.ml_memory
  backend_desired_count       = var.backend_desired_count
  ml_desired_count           = var.ml_desired_count
  
  # AWS Resources
  input_bucket_name           = module.storage.input_bucket_name
  output_bucket_name          = module.storage.output_bucket_name
  dynamodb_table_name         = module.storage.dynamodb_table_name
  request_queue_url           = module.queues.request_queue_url
  status_queue_url            = module.queues.status_queue_url
  
  # Load Balancer
  backend_target_group_arn    = module.load_balancer.backend_target_group_arn
  alb_resource_label          = module.load_balancer.alb_resource_label
  target_group_resource_label = module.load_balancer.target_group_resource_label
  
  # Queues
  request_queue_name          = module.queues.request_queue_name
  request_queue_arn          = module.queues.request_queue_arn
  
  # Autoscaling
  autoscaling_role_arn        = data.aws_iam_role.lab_role.arn
  
  depends_on = [
    module.container_registry,
    module.storage,
    module.queues
  ]
}