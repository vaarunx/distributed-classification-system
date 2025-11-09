# S3 Buckets
resource "aws_s3_bucket" "input" {
  bucket = "${var.project_name}-input-${var.environment}"
  
  tags = {
    Name        = "${var.project_name}-input"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "input" {
  bucket = aws_s3_bucket.input.id
  
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_cors_configuration" "input" {
  bucket = aws_s3_bucket.input.id
  
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket" "output" {
  bucket = "${var.project_name}-output-${var.environment}"
  
  tags = {
    Name        = "${var.project_name}-output"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "output" {
  bucket = aws_s3_bucket.output.id
  
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# DynamoDB Table
resource "aws_dynamodb_table" "jobs" {
  name           = "${var.project_name}-jobs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "job_id"
  
  attribute {
    name = "job_id"
    type = "S"
  }
  
  attribute {
    name = "status"
    type = "S"
  }
  
  attribute {
    name = "created_at"
    type = "S"
  }
  
  global_secondary_index {
    name            = "status-created-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }
  
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
  
  tags = {
    Name        = "${var.project_name}-jobs"
    Environment = var.environment
  }
}