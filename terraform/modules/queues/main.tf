# SQS Queues
resource "aws_sqs_queue" "classification_requests" {
  name                       = "${var.project_name}-classification-requests"
  message_retention_seconds  = 172800  # 2 days
  visibility_timeout_seconds = 300     # 5 minutes
  receive_wait_time_seconds  = 20      # Long polling
  
  tags = {
    Name        = "${var.project_name}-classification-requests"
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "classification_status" {
  name                       = "${var.project_name}-classification-status"
  message_retention_seconds  = 172800  # 2 days
  visibility_timeout_seconds = 30
  receive_wait_time_seconds  = 20      # Long polling
  
  tags = {
    Name        = "${var.project_name}-classification-status"
    Environment = var.environment
  }
}