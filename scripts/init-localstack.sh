#!/bin/bash

# Initialize LocalStack resources for local testing

set -e

AWS_ENDPOINT="http://localhost:4566"
AWS_REGION="us-east-1"

echo "Waiting for LocalStack to be ready..."
until aws --endpoint-url=$AWS_ENDPOINT s3 ls 2>/dev/null; do
    sleep 2
done

echo "Creating S3 buckets..."
aws --endpoint-url=$AWS_ENDPOINT s3 mb s3://distributed-classifier-input
aws --endpoint-url=$AWS_ENDPOINT s3 mb s3://distributed-classifier-output

echo "Creating SQS queues..."
aws --endpoint-url=$AWS_ENDPOINT sqs create-queue --queue-name classification-requests
aws --endpoint-url=$AWS_ENDPOINT sqs create-queue --queue-name classification-status

echo "Creating DynamoDB table..."
aws --endpoint-url=$AWS_ENDPOINT dynamodb create-table \
    --table-name classification-jobs \
    --attribute-definitions AttributeName=job_id,AttributeType=S \
    --key-schema AttributeName=job_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

echo "LocalStack initialization complete!"

echo ""
echo "Queue URLs:"
echo "Request Queue: $AWS_ENDPOINT/000000000000/classification-requests"
echo "Status Queue: $AWS_ENDPOINT/000000000000/classification-status"
echo ""
echo "S3 Buckets:"
echo "Input: distributed-classifier-input"
echo "Output: distributed-classifier-output"