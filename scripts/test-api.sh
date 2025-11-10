#!/bin/bash

# Test script for the Distributed Image Classifier API

set -e

# Configuration
if [ -z "$1" ]; then
    echo "Usage: ./test-api.sh <ALB_ENDPOINT>"
    echo "Example: ./test-api.sh http://distributed-classifier-alb-123456.us-east-1.elb.amazonaws.com"
    exit 1
fi

ALB_ENDPOINT=$1
INPUT_BUCKET=${INPUT_BUCKET:-"distributed-classifier-input-dev"}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Testing Distributed Image Classifier API${NC}"
echo -e "Endpoint: ${ALB_ENDPOINT}"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
curl -s ${ALB_ENDPOINT}/health | jq .
echo ""

# Test 2: Upload test images to S3
echo -e "${YELLOW}Test 2: Uploading test images to S3${NC}"

# Create test images using Python (works on most systems)
python3 << EOF
from PIL import Image
import numpy as np

# Create a red image
img1 = Image.fromarray(np.full((224, 224, 3), [255, 0, 0], dtype=np.uint8))
img1.save('test_dog.jpg')

# Create a blue image  
img2 = Image.fromarray(np.full((224, 224, 3), [0, 0, 255], dtype=np.uint8))
img2.save('test_cat.jpg')

# Create a green image
img3 = Image.fromarray(np.full((224, 224, 3), [0, 255, 0], dtype=np.uint8))
img3.save('test_bird.jpg')

print("Test images created")
EOF

# Upload to S3
aws s3 cp test_dog.jpg s3://${INPUT_BUCKET}/test/dog.jpg
aws s3 cp test_cat.jpg s3://${INPUT_BUCKET}/test/cat.jpg
aws s3 cp test_bird.jpg s3://${INPUT_BUCKET}/test/bird.jpg

echo -e "${GREEN}Images uploaded to S3${NC}"
echo ""

# Test 3: Submit standard classification job
echo -e "${YELLOW}Test 3: Submit Standard Classification Job${NC}"
RESPONSE=$(curl -s -X POST ${ALB_ENDPOINT}/submit \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "image_classification",
    "s3_keys": ["test/dog.jpg", "test/cat.jpg", "test/bird.jpg"],
    "top_k": 5,
    "confidence_threshold": 0.3
  }')

echo "$RESPONSE" | jq .
JOB_ID_1=$(echo "$RESPONSE" | jq -r .job_id)
echo -e "${GREEN}Job ID: ${JOB_ID_1}${NC}"
echo ""

# Test 4: Submit custom classification job
echo -e "${YELLOW}Test 4: Submit Custom Classification Job${NC}"
RESPONSE=$(curl -s -X POST ${ALB_ENDPOINT}/submit \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "custom_classification",
    "s3_keys": ["test/dog.jpg"],
    "custom_labels": ["dog", "cat", "bird", "car", "airplane", "red square", "blue square"],
    "top_k": 3,
    "confidence_threshold": 0.2
  }')

echo "$RESPONSE" | jq .
JOB_ID_2=$(echo "$RESPONSE" | jq -r .job_id)
echo -e "${GREEN}Job ID: ${JOB_ID_2}${NC}"
echo ""

# Test 5: Check job status
echo -e "${YELLOW}Test 5: Checking Job Status${NC}"
echo "Waiting for jobs to process..."
sleep 5

echo "Job 1 Status:"
curl -s ${ALB_ENDPOINT}/status/${JOB_ID_1} | jq .
echo ""

echo "Job 2 Status:"
curl -s ${ALB_ENDPOINT}/status/${JOB_ID_2} | jq .
echo ""

# Test 6: Wait for completion and get results
echo -e "${YELLOW}Test 6: Waiting for Completion and Getting Results${NC}"

# Function to check job status
check_status() {
    local job_id=$1
    local status=$(curl -s ${ALB_ENDPOINT}/status/${job_id} | jq -r .status)
    echo "$status"
}

# Wait for job 1
echo "Waiting for Job 1 to complete..."
while true; do
    STATUS=$(check_status $JOB_ID_1)
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$STATUS" = "completed" ]; then
    echo -e "${GREEN}Job 1 completed successfully!${NC}"
    echo "Results:"
    curl -s ${ALB_ENDPOINT}/result/${JOB_ID_1} | jq .
else
    echo -e "${RED}Job 1 failed${NC}"
    curl -s ${ALB_ENDPOINT}/status/${JOB_ID_1} | jq .
fi
echo ""

# Wait for job 2
echo "Waiting for Job 2 to complete..."
while true; do
    STATUS=$(check_status $JOB_ID_2)
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$STATUS" = "completed" ]; then
    echo -e "${GREEN}Job 2 completed successfully!${NC}"
    echo "Results:"
    curl -s ${ALB_ENDPOINT}/result/${JOB_ID_2} | jq .
else
    echo -e "${RED}Job 2 failed${NC}"
    curl -s ${ALB_ENDPOINT}/status/${JOB_ID_2} | jq .
fi

# Cleanup
rm -f test_dog.jpg test_cat.jpg test_bird.jpg

echo ""
echo -e "${GREEN}Testing complete!${NC}"