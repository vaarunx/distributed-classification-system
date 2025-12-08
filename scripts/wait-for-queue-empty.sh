#!/bin/bash
# Wait for SQS queue to be empty

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_DIR/terraform"

# Find Python command (try python3 first, then python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3."
    exit 1
fi

# Configuration
POLL_INTERVAL="${POLL_INTERVAL:-30}"  # seconds
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-7200}"  # 2 hours default

# Get queue name from Terraform
cd "$TERRAFORM_DIR"

QUEUE_NAME=""
if [ -f "$TERRAFORM_DIR/terraform.tfstate" ] || [ -f "$TERRAFORM_DIR/.terraform/terraform.tfstate" ]; then
    # Try to get from aws_resources JSON output
    QUEUE_NAME=$(terraform output -json aws_resources 2>/dev/null | \
        "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('request_queue', ''))" 2>/dev/null || echo "")
fi

if [ -z "$QUEUE_NAME" ]; then
    echo "Error: Could not get queue name from Terraform"
    echo "  Make sure infrastructure is deployed: ./scripts/deploy.sh"
    exit 1
fi

echo "Waiting for queue to be empty: $QUEUE_NAME"
echo "  Poll interval: ${POLL_INTERVAL}s"
echo "  Timeout: ${TIMEOUT_SECONDS}s"
echo ""

# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" --query 'QueueUrl' --output text 2>/dev/null || echo "")

if [ -z "$QUEUE_URL" ]; then
    echo "Error: Could not get queue URL for $QUEUE_NAME"
    exit 1
fi

# Calculate timeout time
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    TIMEOUT_TIME=$(date -v+${TIMEOUT_SECONDS}S +%s)
else
    # Linux
    TIMEOUT_TIME=$(date -d "+${TIMEOUT_SECONDS} seconds" +%s)
fi

START_TIME=$(date +%s)
ITERATION=0

while true; do
    CURRENT_TIME=$(date +%s)
    
    # Check timeout
    if [ "$CURRENT_TIME" -ge "$TIMEOUT_TIME" ]; then
        echo ""
        echo "❌ Timeout reached (${TIMEOUT_SECONDS}s) while waiting for queue to empty"
        exit 1
    fi
    
    # Get queue attributes
    ATTRIBUTES=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --attribute-names All \
        --query 'Attributes.{Visible:ApproximateNumberOfMessages,InFlight:ApproximateNumberOfMessagesNotVisible}' \
        --output json 2>/dev/null || echo '{"Visible":"0","InFlight":"0"}')
    
    VISIBLE=$(echo "$ATTRIBUTES" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('Visible', '0'))" 2>/dev/null || echo "0")
    IN_FLIGHT=$(echo "$ATTRIBUTES" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('InFlight', '0'))" 2>/dev/null || echo "0")
    
    # Convert to integers
    VISIBLE=$((VISIBLE + 0))
    IN_FLIGHT=$((IN_FLIGHT + 0))
    
    ELAPSED=$((CURRENT_TIME - START_TIME))
    ITERATION=$((ITERATION + 1))
    
    if [ "$VISIBLE" -eq 0 ] && [ "$IN_FLIGHT" -eq 0 ]; then
        echo ""
        echo "✓ Queue is empty. Proceeding..."
        exit 0
    fi
    
    # Show progress every iteration
    echo "[$ITERATION] Queue: $VISIBLE visible, $IN_FLIGHT in-flight (elapsed: ${ELAPSED}s)"
    
    sleep "$POLL_INTERVAL"
done

