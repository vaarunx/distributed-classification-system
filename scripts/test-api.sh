#!/bin/bash

# Test script for the Distributed Image Classifier API

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
if [ -z "$1" ]; then
    # Try to get ALB endpoint from Terraform
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TERRAFORM_DIR="$SCRIPT_DIR/../terraform"
    
    if [ -d "$TERRAFORM_DIR" ]; then
        cd "$TERRAFORM_DIR"
        ALB_ENDPOINT=$(terraform output -raw alb_endpoint 2>/dev/null || echo "")
        
        if [ -z "$ALB_ENDPOINT" ]; then
            echo -e "${RED}Error: Could not get ALB endpoint from Terraform${NC}"
            echo "Usage: ./test-api.sh <ALB_ENDPOINT>"
            echo "Example: ./test-api.sh http://distributed-classifier-alb-123456.us-east-1.elb.amazonaws.com"
            exit 1
        fi
        
        echo -e "${YELLOW}Using ALB endpoint from Terraform: $ALB_ENDPOINT${NC}"
        echo ""
    else
        echo "Usage: ./test-api.sh <ALB_ENDPOINT>"
        echo "Example: ./test-api.sh http://distributed-classifier-alb-123456.us-east-1.elb.amazonaws.com"
        exit 1
    fi
else
    ALB_ENDPOINT=$1
fi

INPUT_BUCKET=${INPUT_BUCKET:-"distributed-classifier-input-dev"}

echo -e "${GREEN}Testing Distributed Image Classifier API${NC}"
echo -e "Endpoint: ${ALB_ENDPOINT}"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
curl -s ${ALB_ENDPOINT}/health | jq .
echo ""

# Test 2: Get Presigned Upload URL
echo -e "${YELLOW}Test 2: Get Presigned Upload URL${NC}"
UPLOAD_URL_RESPONSE=$(curl -s -X POST ${ALB_ENDPOINT}/upload-url \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test_api_image.jpg",
    "content_type": "image/jpeg"
  }')

echo "$UPLOAD_URL_RESPONSE" | jq .
UPLOAD_URL=$(echo "$UPLOAD_URL_RESPONSE" | jq -r .upload_url)
S3_KEY=$(echo "$UPLOAD_URL_RESPONSE" | jq -r .s3_key)
echo -e "${GREEN}S3 Key: ${S3_KEY}${NC}"
echo ""

# Test 3: List Images (before upload)
echo -e "${YELLOW}Test 3: List Images (before upload)${NC}"
curl -s ${ALB_ENDPOINT}/images | jq .
echo ""

# Test 4: Upload test images to S3 (traditional method for job submission)
echo -e "${YELLOW}Test 4: Uploading test images to S3 (for job submission)${NC}"

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

# Test 5: Upload image using presigned URL (if we got one)
if [ -n "$UPLOAD_URL" ] && [ "$UPLOAD_URL" != "null" ]; then
    echo -e "${YELLOW}Test 5: Upload Image Using Presigned URL${NC}"
    
    # Create a simple test image
    python3 << EOF
from PIL import Image
import numpy as np
img = Image.fromarray(np.full((224, 224, 3), [255, 0, 0], dtype=np.uint8))
img.save('test_presigned.jpg')
EOF
    
    UPLOAD_STATUS=$(curl -s -X PUT "$UPLOAD_URL" \
        -H "Content-Type: image/jpeg" \
        --data-binary "@test_presigned.jpg" \
        -w "%{http_code}" -o /dev/null)
    
    if [ "$UPLOAD_STATUS" = "200" ]; then
        echo -e "${GREEN}✓ Image uploaded successfully${NC}"
        rm -f test_presigned.jpg
    else
        echo -e "${RED}✗ Image upload failed (HTTP $UPLOAD_STATUS)${NC}"
    fi
    echo ""
    
    # Test 6: List Images (after upload)
    echo -e "${YELLOW}Test 6: List Images (after upload)${NC}"
    curl -s ${ALB_ENDPOINT}/images | jq .
    echo ""
fi

# Test 7: Upload test images to S3 (traditional method for job submission)
echo -e "${YELLOW}Test 7: Upload Test Images to S3 (for job submission)${NC}"
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

# Test 9: Submit custom classification job
echo -e "${YELLOW}Test 9: Submit Custom Classification Job${NC}"
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

# Test 10: Check job status
echo -e "${YELLOW}Test 10: Checking Job Status${NC}"
echo "Waiting for jobs to process..."
sleep 5

echo "Job 1 Status:"
curl -s ${ALB_ENDPOINT}/status/${JOB_ID_1} | jq .
echo ""

echo "Job 2 Status:"
curl -s ${ALB_ENDPOINT}/status/${JOB_ID_2} | jq .
echo ""

# Test 11: Wait for completion and get results
echo -e "${YELLOW}Test 11: Waiting for Completion and Getting Results${NC}"

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

# Test 12: Delete uploaded image (cleanup)
if [ -n "$S3_KEY" ] && [ "$S3_KEY" != "null" ]; then
    echo -e "${YELLOW}Test 12: Delete Uploaded Image (cleanup)${NC}"
    ENCODED_KEY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$S3_KEY', safe=''))")
    DELETE_RESPONSE=$(curl -s -X DELETE "${ALB_ENDPOINT}/images/${ENCODED_KEY}")
    echo "$DELETE_RESPONSE" | jq .
    echo ""
fi

# Cleanup
rm -f test_dog.jpg test_cat.jpg test_bird.jpg

echo ""
echo -e "${GREEN}Testing complete!${NC}"