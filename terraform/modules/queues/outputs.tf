# outputs.tf
output "request_queue_url" {
  value = aws_sqs_queue.classification_requests.url
}

output "status_queue_url" {
  value = aws_sqs_queue.classification_status.url
}

output "request_queue_arn" {
  value = aws_sqs_queue.classification_requests.arn
}

output "status_queue_arn" {
  value = aws_sqs_queue.classification_status.arn
}

output "request_queue_name" {
  value = aws_sqs_queue.classification_requests.name
}

output "status_queue_name" {
  value = aws_sqs_queue.classification_status.name
}