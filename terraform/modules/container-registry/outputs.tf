# outputs.tf
output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ml_service_repository_url" {
  value = aws_ecr_repository.ml_service.repository_url
}

output "backend_image_url" {
  value = "${aws_ecr_repository.backend.repository_url}:latest"
}

output "ml_service_image_url" {
  value = "${aws_ecr_repository.ml_service.repository_url}:latest"
}