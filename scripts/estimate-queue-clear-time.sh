#!/bin/bash
# Estimate how long the queue will take to clear

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found"
    exit 1
fi

echo "Estimating queue clear time..."
echo ""

# Get queue name and URL
cd "$PROJECT_DIR/terraform"

QUEUE_NAME=""
if [ -f "$PROJECT_DIR/terraform/terraform.tfstate" ] || [ -f "$PROJECT_DIR/terraform/.terraform/terraform.tfstate" ]; then
    # Try to get from aws_resources JSON output
    QUEUE_NAME=$(terraform output -json aws_resources 2>/dev/null | \
        "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('request_queue', ''))" 2>/dev/null || echo "")
fi

if [ -z "$QUEUE_NAME" ]; then
    # Try to list queues and find the request queue
    QUEUE_URLS=$(aws sqs list-queues --output text 2>/dev/null | grep -i request || echo "")
    if [ -n "$QUEUE_URLS" ]; then
        QUEUE_URL=$(echo "$QUEUE_URLS" | head -1)
        QUEUE_NAME=$(basename "$QUEUE_URL" 2>/dev/null || echo "")
    fi
fi

if [ -z "$QUEUE_NAME" ]; then
    echo "Error: Could not get queue name from Terraform"
    echo "  Make sure infrastructure is deployed: ./scripts/deploy.sh"
    exit 1
fi

# Get queue URL if we don't have it
if [ -z "$QUEUE_URL" ]; then
    QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" --query 'QueueUrl' --output text 2>/dev/null || echo "")
fi

if [ -z "$QUEUE_URL" ]; then
    echo "Error: Could not get queue URL"
    exit 1
fi

# Get current queue status directly
QUEUE_ATTR=$(aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible \
    --output json 2>/dev/null)

# Parse the attributes - AWS returns them in Attributes object
VISIBLE=$(echo "$QUEUE_ATTR" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); attrs=d.get('Attributes', {}); print(int(attrs.get('ApproximateNumberOfMessagesVisible', 0)))" 2>/dev/null || echo "0")
IN_FLIGHT=$(echo "$QUEUE_ATTR" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); attrs=d.get('Attributes', {}); print(int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)))" 2>/dev/null || echo "0")

if [ "$VISIBLE" = "0" ] && [ "$IN_FLIGHT" = "0" ]; then
    echo "✓ Queue is empty!"
    echo ""
    echo "No messages to process. Queue clear time: 0 minutes"
    exit 0
fi

TOTAL_MESSAGES=$((VISIBLE + IN_FLIGHT))

# Get current task count
cd "$PROJECT_DIR/terraform"
CLUSTER=$(terraform output -raw cluster_name 2>/dev/null || echo "")
ML_SERVICE=$(terraform output -raw ml_service_name 2>/dev/null || echo "")

if [ -z "$CLUSTER" ] || [ -z "$ML_SERVICE" ]; then
    echo "Could not get cluster/service names"
    exit 1
fi

TASK_INFO=$(aws ecs describe-services \
    --cluster "$CLUSTER" \
    --services "$ML_SERVICE" \
    --query 'services[0].{Running:runningCount,Desired:desiredCount}' \
    --output json 2>/dev/null)

RUNNING_TASKS=$(echo "$TASK_INFO" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('Running', 0))" 2>/dev/null || echo "0")
DESIRED_TASKS=$(echo "$TASK_INFO" | "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('Desired', 0))" 2>/dev/null || echo "0")

# Processing rate: 30.35 msg/sec with 50 tasks (from plan documentation)
# Rate per task: 30.35 / 50 = 0.607 msg/sec per task
RATE_PER_TASK=0.607

# Calculate rates
CURRENT_RATE=$(echo "$RUNNING_TASKS $RATE_PER_TASK" | awk '{printf "%.2f", $1 * $2}')
MAX_RATE=$(echo "$DESIRED_TASKS $RATE_PER_TASK" | awk '{printf "%.2f", $1 * $2}')

# Calculate time in seconds
TIME_CURRENT=$(echo "$TOTAL_MESSAGES $CURRENT_RATE" | awk '{if ($2 > 0) printf "%.0f", $1 / $2; else print "inf"}')
TIME_MAX=$(echo "$TOTAL_MESSAGES $MAX_RATE" | awk '{if ($2 > 0) printf "%.0f", $1 / $2; else print "inf"}')

# Convert to minutes and hours
MIN_CURRENT=$(echo "$TIME_CURRENT" | awk '{if ($1 != "inf") printf "%.1f", $1 / 60; else print "inf"}')
HOURS_CURRENT=$(echo "$TIME_CURRENT" | awk '{if ($1 != "inf") printf "%.2f", $1 / 3600; else print "inf"}')
MIN_MAX=$(echo "$TIME_MAX" | awk '{if ($1 != "inf") printf "%.1f", $1 / 60; else print "inf"}')
HOURS_MAX=$(echo "$TIME_MAX" | awk '{if ($1 != "inf") printf "%.2f", $1 / 3600; else print "inf"}')

echo "Current Queue Status:"
echo "  Visible messages: $VISIBLE"
echo "  In-flight messages: $IN_FLIGHT"
echo "  Total messages: $TOTAL_MESSAGES"
echo ""
echo "ML Service Status:"
echo "  Running tasks: $RUNNING_TASKS"
echo "  Desired tasks: $DESIRED_TASKS"
echo ""
echo "Processing Rate:"
echo "  Rate per task: ${RATE_PER_TASK} messages/second"
echo "  Current rate ($RUNNING_TASKS tasks): $CURRENT_RATE messages/second"
echo "  Max rate ($DESIRED_TASKS tasks): $MAX_RATE messages/second"
echo ""
echo "Estimated Clear Time:"
if [ "$TIME_CURRENT" != "inf" ]; then
    echo "  With $RUNNING_TASKS tasks: $MIN_CURRENT minutes ($HOURS_CURRENT hours)"
else
    echo "  With $RUNNING_TASKS tasks: Cannot calculate (no running tasks)"
fi
if [ "$TIME_MAX" != "inf" ]; then
    echo "  With $DESIRED_TASKS tasks: $MIN_MAX minutes ($HOURS_MAX hours)"
else
    echo "  With $DESIRED_TASKS tasks: Cannot calculate"
fi
echo ""
echo "Note: Service may scale up further if autoscaling is enabled"

