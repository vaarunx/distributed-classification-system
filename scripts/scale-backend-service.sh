#!/bin/bash
# Scale Backend service to target task count

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_DIR/terraform"

# Use python command
PYTHON_CMD="python"

# Get target task count from argument (default: 1)
TARGET_COUNT="${1:-1}"

if ! [[ "$TARGET_COUNT" =~ ^[0-9]+$ ]] || [ "$TARGET_COUNT" -lt 0 ]; then
    echo "Error: Invalid task count: $TARGET_COUNT"
    echo "Usage: $0 <task_count>"
    echo "  Example: $0 1"
    exit 1
fi

# Get cluster and service names from Terraform
cd "$TERRAFORM_DIR"

# Try direct outputs first
CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null || echo "")
BACKEND_SERVICE=$(terraform output -raw backend_service_name 2>/dev/null || echo "")

# If direct outputs don't exist, try getting from aws_resources nested output
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME=$(terraform output -json aws_resources 2>/dev/null | \
        "$PYTHON_CMD" -c "import sys, json; d=json.load(sys.stdin); print(d.get('cluster_name', ''))" 2>/dev/null || echo "")
fi

# If still empty, use default naming convention
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME="distributed-classifier-cluster"
    BACKEND_SERVICE="distributed-classifier-backend-service"
    echo "Using default names (run 'terraform apply' to get actual names from outputs)"
else
    # If we have cluster name but not service name, use default
    if [ -z "$BACKEND_SERVICE" ]; then
        BACKEND_SERVICE="distributed-classifier-backend-service"
    fi
fi

# Allow environment variable overrides
CLUSTER_NAME="${CLUSTER_NAME_ENV:-$CLUSTER_NAME}"
BACKEND_SERVICE="${BACKEND_SERVICE_ENV:-$BACKEND_SERVICE}"

echo "Scaling Backend service:"
echo "  Cluster: $CLUSTER_NAME"
echo "  Service: $BACKEND_SERVICE"
echo "  Target task count: $TARGET_COUNT"
echo ""

# Get current desired count with error checking
CURRENT_DESIRED_RAW=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$BACKEND_SERVICE" \
    --query 'services[0].desiredCount' \
    --output text 2>&1)

if [ $? -eq 0 ] && [ -n "$CURRENT_DESIRED_RAW" ] && [ "$CURRENT_DESIRED_RAW" != "None" ]; then
    CURRENT_DESIRED="$CURRENT_DESIRED_RAW"
else
    echo "⚠️  Warning: Could not get current desired count: $CURRENT_DESIRED_RAW"
    CURRENT_DESIRED="0"
fi

CURRENT_RUNNING_RAW=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$BACKEND_SERVICE" \
    --query 'services[0].runningCount' \
    --output text 2>&1)

if [ $? -eq 0 ] && [ -n "$CURRENT_RUNNING_RAW" ] && [ "$CURRENT_RUNNING_RAW" != "None" ]; then
    CURRENT_RUNNING="$CURRENT_RUNNING_RAW"
else
    echo "⚠️  Warning: Could not get current running count: $CURRENT_RUNNING_RAW"
    CURRENT_RUNNING="0"
fi

echo "Current state: $CURRENT_RUNNING running / $CURRENT_DESIRED desired"

if [ "$CURRENT_DESIRED" -eq "$TARGET_COUNT" ]; then
    echo "Service is already at target count ($TARGET_COUNT)"
    
    # Still wait for running count to match desired if needed
    if [ "$CURRENT_RUNNING" -ne "$TARGET_COUNT" ]; then
        echo "Waiting for running count to match desired count..."
    else
        echo "✓ Service is at target count and all tasks are running"
        exit 0
    fi
else
    # Update service
    echo "Updating service to desired count: $TARGET_COUNT"
    aws ecs update-service \
        --cluster "$CLUSTER_NAME" \
        --service "$BACKEND_SERVICE" \
        --desired-count "$TARGET_COUNT" \
        --output text > /dev/null
    
    echo "Service update initiated. Waiting for tasks to stabilize..."
fi

# Verify service exists before waiting
echo "Verifying service exists..."
SERVICE_CHECK=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$BACKEND_SERVICE" \
    --query 'services[0].status' \
    --output text 2>&1)

if [ $? -ne 0 ] || [ -z "$SERVICE_CHECK" ] || [ "$SERVICE_CHECK" = "None" ]; then
    echo "❌ Error: Could not find service '$BACKEND_SERVICE' in cluster '$CLUSTER_NAME'"
    echo "  AWS CLI output: $SERVICE_CHECK"
    echo ""
    echo "Please verify:"
    echo "  1. Cluster name is correct: $CLUSTER_NAME"
    echo "  2. Service name is correct: $BACKEND_SERVICE"
    echo "  3. AWS credentials are configured"
    echo "  4. You have permissions to describe ECS services"
    exit 1
fi

echo "✓ Service found. Status: $SERVICE_CHECK"
echo ""

# Wait for service to stabilize
MAX_WAIT_TIME=300  # 5 minutes
WAIT_INTERVAL=10
ELAPSED=0
ITERATION=0

while [ $ELAPSED -lt $MAX_WAIT_TIME ]; do
    # Get service status using direct field queries (more reliable than services[0])
    # This avoids null issues when service is updating
    RUNNING_RAW=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].runningCount' \
        --output text 2>&1)
    
    DESIRED_RAW=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].desiredCount' \
        --output text 2>&1)
    
    PENDING_RAW=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].pendingCount' \
        --output text 2>&1)
    
    # Check if any query failed
    if echo "$RUNNING_RAW" | grep -q "error\|Error\|ERROR" || \
       echo "$DESIRED_RAW" | grep -q "error\|Error\|ERROR" || \
       echo "$PENDING_RAW" | grep -q "error\|Error\|ERROR"; then
        echo "[$ITERATION] ⚠️  AWS CLI error detected"
        echo "  Running query: $RUNNING_RAW"
        echo "  Desired query: $DESIRED_RAW"
        echo "  Pending query: $PENDING_RAW"
        sleep "$WAIT_INTERVAL"
        ELAPSED=$((ELAPSED + WAIT_INTERVAL))
        ITERATION=$((ITERATION + 1))
        continue
    fi
    
    # Handle null/None responses (can happen briefly after update)
    if [ "$RUNNING_RAW" = "None" ] || [ "$RUNNING_RAW" = "null" ] || [ -z "$RUNNING_RAW" ]; then
        echo "[$ITERATION] ⚠️  Service status unavailable (null/None) - may be updating..."
        echo "  Cluster: $CLUSTER_NAME"
        echo "  Service: $BACKEND_SERVICE"
        sleep "$WAIT_INTERVAL"
        ELAPSED=$((ELAPSED + WAIT_INTERVAL))
        ITERATION=$((ITERATION + 1))
        continue
    fi
    
    # Convert to integers (handles text numbers)
    RUNNING=$((RUNNING_RAW + 0))
    DESIRED=$((DESIRED_RAW + 0))
    PENDING=$((PENDING_RAW + 0))
    
    ITERATION=$((ITERATION + 1))
    
    echo "[$ITERATION] Running: $RUNNING, Desired: $DESIRED, Pending: $PENDING (elapsed: ${ELAPSED}s)"
    
    if [ "$RUNNING" -eq "$TARGET_COUNT" ] && [ "$DESIRED" -eq "$TARGET_COUNT" ] && [ "$PENDING" -eq 0 ]; then
        echo ""
        echo "✓ Service scaled successfully: $RUNNING tasks running"
        exit 0
    fi
    
    sleep "$WAIT_INTERVAL"
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

echo ""
echo "⚠️  Warning: Timeout reached while waiting for service to stabilize"
echo "  Current: $RUNNING running / $DESIRED desired"
echo "  Target: $TARGET_COUNT"
echo "  Service may still be scaling. Check AWS console for status."
exit 0  # Don't fail, as scaling may still be in progress

