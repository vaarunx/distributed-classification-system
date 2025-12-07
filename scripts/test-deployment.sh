#!/bin/bash
# test-deployment.sh - End-to-end testing of deployed backend API

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${BLUE}Testing: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASS: $test_name${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL: $test_name${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "${GREEN}=== End-to-End Deployment Test ===${NC}"
echo ""

# Get ALB endpoint from Terraform
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}Error: Terraform directory not found${NC}"
    exit 1
fi

cd "$TERRAFORM_DIR"

echo -e "${YELLOW}Getting ALB endpoint from Terraform...${NC}"
ALB_ENDPOINT=$(terraform output -raw alb_endpoint 2>/dev/null || echo "")

if [ -z "$ALB_ENDPOINT" ]; then
    echo -e "${RED}Error: Could not get ALB endpoint from Terraform${NC}"
    echo "  Make sure infrastructure is deployed: ./scripts/deploy.sh"
    exit 1
fi

echo -e "${GREEN}ALB Endpoint: $ALB_ENDPOINT${NC}"
echo ""

# Test 1: Backend Health
run_test "Backend Health Check" \
    "curl -s -f -o /dev/null -w '%{http_code}' '$ALB_ENDPOINT/health' | grep -q '200'"

# Test 2: Get Upload URL
echo ""
echo -e "${BLUE}Testing: Get Presigned Upload URL${NC}"
UPLOAD_RESPONSE=$(curl -s -X POST "$ALB_ENDPOINT/upload-url" \
    -H "Content-Type: application/json" \
    -d '{"filename": "test.jpg", "content_type": "image/jpeg"}')

if echo "$UPLOAD_RESPONSE" | grep -q "upload_url"; then
    UPLOAD_URL=$(echo "$UPLOAD_RESPONSE" | grep -o '"upload_url":"[^"]*' | cut -d'"' -f4)
    S3_KEY=$(echo "$UPLOAD_RESPONSE" | grep -o '"s3_key":"[^"]*' | cut -d'"' -f4)
    echo -e "${GREEN}✓ PASS: Get Presigned Upload URL${NC}"
    echo "  S3 Key: $S3_KEY"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAIL: Get Presigned Upload URL${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    UPLOAD_URL=""
    S3_KEY=""
fi

# Test 3: Upload Test Image (if we got a presigned URL)
if [ -n "$UPLOAD_URL" ] && [ -n "$S3_KEY" ]; then
    echo ""
    echo -e "${BLUE}Testing: Upload Image to S3${NC}"
    
    # Create a simple test image (1x1 pixel PNG)
    TEST_IMAGE="/tmp/test_image_$$.png"
    python3 << EOF
from PIL import Image
img = Image.new('RGB', (1, 1), color='red')
img.save('$TEST_IMAGE')
EOF
    
    if curl -s -X PUT "$UPLOAD_URL" \
        -H "Content-Type: image/jpeg" \
        --data-binary "@$TEST_IMAGE" \
        -o /dev/null -w '%{http_code}' | grep -q '200'; then
        echo -e "${GREEN}✓ PASS: Upload Image to S3${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        UPLOADED=true
    else
        echo -e "${RED}✗ FAIL: Upload Image to S3${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        UPLOADED=false
    fi
    
    rm -f "$TEST_IMAGE"
else
    UPLOADED=false
fi

# Test 4: List Images
echo ""
run_test "List Images" \
    "curl -s -f '$ALB_ENDPOINT/images' | grep -q 'images'"

# Test 5: Verify Uploaded Image in List
if [ "$UPLOADED" = true ] && [ -n "$S3_KEY" ]; then
    echo ""
    echo -e "${BLUE}Testing: Verify Image in List${NC}"
    IMAGES_LIST=$(curl -s "$ALB_ENDPOINT/images")
    if echo "$IMAGES_LIST" | grep -q "$S3_KEY"; then
        echo -e "${GREEN}✓ PASS: Verify Image in List${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗ FAIL: Verify Image in List${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
fi

# Test 6: Submit Classification Job
echo ""
echo -e "${BLUE}Testing: Submit Classification Job${NC}"
if [ -n "$S3_KEY" ] && [ "$UPLOADED" = true ]; then
    JOB_RESPONSE=$(curl -s -X POST "$ALB_ENDPOINT/submit" \
        -H "Content-Type: application/json" \
        -d "{
            \"job_type\": \"image_classification\",
            \"s3_keys\": [\"$S3_KEY\"],
            \"top_k\": 3,
            \"confidence_threshold\": 0.3
        }")
    
    if echo "$JOB_RESPONSE" | grep -q "job_id"; then
        JOB_ID=$(echo "$JOB_RESPONSE" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
        echo -e "${GREEN}✓ PASS: Submit Classification Job${NC}"
        echo "  Job ID: $JOB_ID"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Test 7: Poll Job Status
        echo ""
        echo -e "${BLUE}Testing: Poll Job Status${NC}"
        MAX_POLLS=30
        POLL_COUNT=0
        JOB_COMPLETED=false
        
        while [ $POLL_COUNT -lt $MAX_POLLS ]; do
            STATUS_RESPONSE=$(curl -s "$ALB_ENDPOINT/status/$JOB_ID")
            STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
            
            if [ "$STATUS" = "completed" ]; then
                echo -e "${GREEN}✓ PASS: Job Completed${NC}"
                JOB_COMPLETED=true
                TESTS_PASSED=$((TESTS_PASSED + 1))
                break
            elif [ "$STATUS" = "failed" ]; then
                echo -e "${RED}✗ FAIL: Job Failed${NC}"
                ERROR=$(echo "$STATUS_RESPONSE" | grep -o '"error":"[^"]*' | cut -d'"' -f4 || echo "Unknown error")
                echo "  Error: $ERROR"
                TESTS_FAILED=$((TESTS_FAILED + 1))
                break
            fi
            
            echo "  Polling... ($POLL_COUNT/$MAX_POLLS) Status: $STATUS"
            sleep 5
            POLL_COUNT=$((POLL_COUNT + 1))
        done
        
        if [ "$JOB_COMPLETED" = true ]; then
            # Test 8: Get Job Results
            echo ""
            echo -e "${BLUE}Testing: Get Job Results${NC}"
            RESULT_RESPONSE=$(curl -s "$ALB_ENDPOINT/result/$JOB_ID")
            if echo "$RESULT_RESPONSE" | grep -q "success"; then
                echo -e "${GREEN}✓ PASS: Get Job Results${NC}"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                echo -e "${RED}✗ FAIL: Get Job Results${NC}"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        fi
    else
        echo -e "${RED}✗ FAIL: Submit Classification Job${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    echo -e "${YELLOW}⚠ SKIP: Submit Classification Job (no uploaded image)${NC}"
fi

# Test 9: Delete Image (cleanup)
if [ -n "$S3_KEY" ] && [ "$UPLOADED" = true ]; then
    echo ""
    echo -e "${BLUE}Testing: Delete Image (cleanup)${NC}"
    # URL encode the S3 key
    ENCODED_KEY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$S3_KEY', safe=''))")
    if curl -s -X DELETE "$ALB_ENDPOINT/images/$ENCODED_KEY" | grep -q "success"; then
        echo -e "${GREEN}✓ PASS: Delete Image${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠ WARN: Delete Image (may have already been deleted)${NC}"
    fi
fi

# Summary
echo ""
echo -e "${GREEN}=== Test Summary ===${NC}"
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

