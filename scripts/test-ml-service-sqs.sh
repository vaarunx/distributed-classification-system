#!/bin/bash
# test-ml-service-sqs.sh

cd terraform

# Get resource names
INPUT_BUCKET=$(terraform output -json aws_resources | jq -r '.input_bucket')
REQUEST_QUEUE=$(terraform output -json aws_resources | jq -r '.request_queue')
STATUS_QUEUE=$(terraform output -jsonsudo apt update && sudo apt install -y jq aws_resources | jq -r '.status_queue')

# Get queue URLs
REQUEST_QUEUE_URL=$(aws sqs get-queue-url --queue-name ${REQUEST_QUEUE} --query 'QueueUrl' --output text)
STATUS_QUEUE_URL=$(aws sqs get-queue-url --queue-name ${STATUS_QUEUE} --query 'QueueUrl' --output text)

# Upload image (if not already uploaded)
echo "Uploading test image..."
aws s3 cp ml-service/test/test-image.jpg s3://${INPUT_BUCKET}/test/test-image.jpg || echo "Image already exists or upload failed"

# Send job
JOB_ID="sqs-test-$(date +%s)"
echo "Sending job: ${JOB_ID}"

aws sqs send-message \
  --queue-url ${REQUEST_QUEUE_URL} \
  --message-body "{
    \"job_id\": \"${JOB_ID}\",
    \"job_type\": \"image_classification\",
    \"s3_bucket\": \"${INPUT_BUCKET}\",
    \"s3_keys\": [\"test/test-image.jpg\"],
    \"top_k\": 5,
    \"confidence_threshold\": 0.5
  }"

echo "Job sent! Waiting for results..."
sleep 10

# Check status
aws sqs receive-message \
  --queue-url ${STATUS_QUEUE_URL} \
  --max-number-of-messages 10 \
  --wait-time-seconds 20 | jq '.'