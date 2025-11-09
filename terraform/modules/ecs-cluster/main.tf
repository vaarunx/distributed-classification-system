# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enhanced"
  }
  
  tags = {
    Name        = "${var.project_name}-cluster"
    Environment = var.environment
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 1
  
  tags = {
    Name        = "${var.project_name}-backend-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "ml_service" {
  name              = "/ecs/${var.project_name}/ml-service"
  retention_in_days = 1
  
  tags = {
    Name        = "${var.project_name}-ml-logs"
    Environment = var.environment
  }
}

# Backend Service Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.backend_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = "backend"
      image = var.backend_image_url
      
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "PORT"
          value = "8080"
        },
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.name
        },
        {
          name  = "INPUT_BUCKET"
          value = var.input_bucket_name
        },
        {
          name  = "OUTPUT_BUCKET"
          value = var.output_bucket_name
        },
        {
          name  = "REQUEST_QUEUE_URL"
          value = var.request_queue_url
        },
        {
          name  = "STATUS_QUEUE_URL"
          value = var.status_queue_url
        },
        {
          name  = "DYNAMODB_TABLE"
          value = var.dynamodb_table_name
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      essential = true
    }
  ])
  
  tags = {
    Name        = "${var.project_name}-backend-task"
    Environment = var.environment
  }
}

# ML Service Task Definition
resource "aws_ecs_task_definition" "ml_service" {
  family                   = "${var.project_name}-ml-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ml_cpu
  memory                   = var.ml_memory
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.ml_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = "ml-service"
      image = var.ml_service_image_url
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.name
        },
        {
          name  = "REQUEST_QUEUE_URL"
          value = var.request_queue_url
        },
        {
          name  = "STATUS_QUEUE_URL"
          value = var.status_queue_url
        },
        {
          name  = "MAX_WORKERS"
          value = "5"
        },
        {
          name  = "BATCH_SIZE"
          value = "10"
        },
        {
          name  = "VISIBILITY_TIMEOUT"
          value = "300"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ml_service.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      essential = true
    }
  ])
  
  tags = {
    Name        = "${var.project_name}-ml-service-task"
    Environment = var.environment
  }
}

# Backend ECS Service
resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"
  
  force_new_deployment = true  # Always deploy latest
  
  network_configuration {
    security_groups  = [var.ecs_security_group_id]
    subnets         = var.private_subnet_ids
    assign_public_ip = true  # Required for Fargate
  }
  
  load_balancer {
    target_group_arn = var.backend_target_group_arn
    container_name   = "backend"
    container_port   = 8080
  }
  
  tags = {
    Name        = "${var.project_name}-backend-service"
    Environment = var.environment
  }
}

# ML ECS Service
resource "aws_ecs_service" "ml_service" {
  name            = "${var.project_name}-ml-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ml_service.arn
  desired_count   = var.ml_desired_count
  launch_type     = "FARGATE"
  
  force_new_deployment = true  # Always deploy latest
  
  network_configuration {
    security_groups  = [var.ecs_security_group_id]
    subnets         = var.private_subnet_ids
    assign_public_ip = true  # Required for Fargate
  }
  
  tags = {
    Name        = "${var.project_name}-ml-service"
    Environment = var.environment
  }
}

data "aws_region" "current" {}
