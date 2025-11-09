# outputs.tf
output "input_bucket_name" {
  value = aws_s3_bucket.input.id
}

output "output_bucket_name" {
  value = aws_s3_bucket.output.id
}

output "input_bucket_arn" {
  value = aws_s3_bucket.input.arn
}

output "output_bucket_arn" {
  value = aws_s3_bucket.output.arn
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.jobs.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.jobs.arn
}