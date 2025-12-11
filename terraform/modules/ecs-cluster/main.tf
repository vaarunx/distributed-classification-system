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

# Backend Service Autoscaling Target
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = 10000  # Effectively unlimited - no cap on tasks
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
  role_arn           = var.autoscaling_role_arn

  depends_on = [aws_ecs_service.backend]

  # Add lifecycle to prevent role_arn changes (always use LabRole)
  lifecycle {
    # Ignore role_arn changes to prevent concurrent update errors
    # LabRole is already configured correctly, no need to update
    ignore_changes = [role_arn]
  }
}

# Backend Service Autoscaling Policy - ALB Request Count
resource "aws_appautoscaling_policy" "backend_request_count" {
  name               = "${var.project_name}-backend-request-count-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 500.0  # Reduced from 1000.0 to trigger scaling at lower load
    scale_in_cooldown  = 30     # Reduced from 60s for faster scale in
    scale_out_cooldown = 10     # Reduced from 15s to match ML service faster scaling
    disable_scale_in   = false

    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      # Format: app/<alb-name>/<alb-id>/targetgroup/<tg-name>/<tg-id>
      resource_label          = "${var.alb_resource_label}/${var.target_group_resource_label}"
    }
  }
}

# Backend Service Autoscaling Policy - Response Time
# Note: ALBTargetResponseTime is not a valid predefined metric type for ECS autoscaling
# Response time monitoring can be done via CloudWatch metrics and step scaling if needed
# For now, using only ALBRequestCountPerTarget which is the primary scaling metric

# Backend Service Autoscaling Policy - CPU Utilization
resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "${var.project_name}-backend-cpu-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70.0
    scale_in_cooldown  = 60
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

# ML Service Autoscaling Target
resource "aws_appautoscaling_target" "ml_service" {
  max_capacity       = 10000  # Effectively unlimited - no cap on tasks
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.ml_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
  role_arn           = var.autoscaling_role_arn

  depends_on = [aws_ecs_service.ml_service]

  # Add lifecycle to prevent role_arn changes (always use LabRole)
  lifecycle {
    # Ignore role_arn changes to prevent concurrent update errors
    # LabRole is already configured correctly, no need to update
    ignore_changes = [role_arn]
  }
}

# ML Service Autoscaling Policy - SQS Queue Depth
# CloudWatch alarms for queue depth
resource "aws_cloudwatch_metric_alarm" "ml_service_queue_depth_high" {
  alarm_name          = "${var.project_name}-ml-queue-depth-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1      # Reduced from 2 for faster trigger
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 30     # Reduced from 60s for more responsive
  statistic           = "Average"
  threshold           = 300    # Reduced from 1000 to trigger earlier
  alarm_description    = "Trigger scale out when SQS queue depth exceeds 300 messages"
  alarm_actions       = [aws_appautoscaling_policy.ml_service_queue_scale_out.arn]

  dimensions = {
    QueueName = var.request_queue_name
  }

  depends_on = [aws_appautoscaling_policy.ml_service_queue_scale_out]

  tags = {
    Name        = "${var.project_name}-ml-queue-depth-high"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "ml_service_queue_depth_low" {
  alarm_name          = "${var.project_name}-ml-queue-depth-low-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2      # Reduced from 3 for faster trigger
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 30     # Reduced from 60s for more responsive
  statistic           = "Average"
  threshold           = 100     # Reduced from 500 to scale in earlier
  alarm_description    = "Trigger scale in when SQS queue depth drops below 100 messages"
  alarm_actions       = [aws_appautoscaling_policy.ml_service_queue_scale_in.arn]

  dimensions = {
    QueueName = var.request_queue_name
  }

  depends_on = [aws_appautoscaling_policy.ml_service_queue_scale_in]

  tags = {
    Name        = "${var.project_name}-ml-queue-depth-low"
    Environment = var.environment
  }
}

# Step scaling policy for scale out (queue depth high)
# Uses multi-step scaling based on queue depth above threshold (300)
# Intervals are relative to alarm threshold: threshold=300, so 0 = 300-1300, 1000 = 1300-10300, etc.
resource "aws_appautoscaling_policy" "ml_service_queue_scale_out" {
  name               = "${var.project_name}-ml-queue-scale-out-${var.environment}"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.ml_service.resource_id
  scalable_dimension = aws_appautoscaling_target.ml_service.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ml_service.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 10     # Reduced from 15s for faster subsequent scaling
    metric_aggregation_type  = "Average"

    # Small queue (300-1,300 messages): add 2 tasks
    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = 1000
      scaling_adjustment          = 2
    }
    
    # Medium queue (1,300-10,300 messages): add 5 tasks
    step_adjustment {
      metric_interval_lower_bound = 1000
      metric_interval_upper_bound = 10000
      scaling_adjustment          = 5
    }
    
    # Large queue (10,300-50,300 messages): add 10 tasks
    step_adjustment {
      metric_interval_lower_bound = 10000
      metric_interval_upper_bound = 50000
      scaling_adjustment          = 10
    }
    
    # Very large queue (50,300+ messages): add 20 tasks
    step_adjustment {
      metric_interval_lower_bound = 50000
      scaling_adjustment          = 20
    }
  }
}

# Step scaling policy for scale in (queue depth low)
resource "aws_appautoscaling_policy" "ml_service_queue_scale_in" {
  name               = "${var.project_name}-ml-queue-scale-in-${var.environment}"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.ml_service.resource_id
  scalable_dimension = aws_appautoscaling_target.ml_service.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ml_service.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 30     # Reduced from 60s for faster scale in
    metric_aggregation_type  = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1  # Remove 1 task when queue depth < 100
    }
  }
}

# ML Service Autoscaling Policy - CPU removed
# Now using only queue depth autoscaling for ML service