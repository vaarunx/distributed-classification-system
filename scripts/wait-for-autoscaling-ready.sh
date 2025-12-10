#!/bin/bash
# Wait for autoscaling targets to be ready (no pending updates)
# This helps avoid ConcurrentUpdateException errors during Terraform deployments

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Get cluster and service names
cd "$PROJECT_DIR/terraform"

CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null || echo "distributed-classifier-cluster")
BACKEND_SERVICE=$(terraform output -raw backend_service_name 2>/dev/null || echo "distributed-classifier-backend-service")
ML_SERVICE=$(terraform output -raw ml_service_name 2>/dev/null || echo "distributed-classifier-ml-service")

BACKEND_RESOURCE_ID="service/${CLUSTER_NAME}/${BACKEND_SERVICE}"
ML_RESOURCE_ID="service/${CLUSTER_NAME}/${ML_SERVICE}"

MAX_WAIT_TIME="${MAX_WAIT_TIME:-300}"  # 5 minutes default
WAIT_INTERVAL=5
ELAPSED=0

echo "Waiting for autoscaling targets to be ready..."
echo "  Backend: $BACKEND_RESOURCE_ID"
echo "  ML Service: $ML_RESOURCE_ID"
echo "  Max wait time: ${MAX_WAIT_TIME}s"
echo ""

check_autoscaling_ready() {
    local resource_id=$1
    local service_name=$2
    
    # Try to describe the scalable target
    # If there's a ConcurrentUpdateException or the target is being updated,
    # AWS will return an error or the target might be in a transitional state
    local result=$(aws application-autoscaling describe-scalable-targets \
        --service-namespace ecs \
        --resource-ids "$resource_id" \
        --query 'ScalableTargets[0]' \
        --output json 2>&1)
    
    # Check for errors
    if echo "$result" | grep -qi "ConcurrentUpdateException\|pending\|error"; then
        return 1
    fi
    
    # Check if we got valid JSON (not empty or error)
    if [ -z "$result" ] || [ "$result" = "null" ] || [ "$result" = "{}" ]; then
        return 1
    fi
    
    # Check if the target exists and is not in a transitional state
    local creation_time=$(echo "$result" | grep -o '"CreationTime":"[^"]*"' | cut -d'"' -f4 || echo "")
    if [ -z "$creation_time" ]; then
        return 1
    fi
    
    return 0
}

check_ecs_service_stable() {
    local cluster=$1
    local service=$2
    
    # Check if ECS service is stable (not updating)
    local status=$(aws ecs describe-services \
        --cluster "$cluster" \
        --services "$service" \
        --query 'services[0].status' \
        --output text 2>&1)
    
    if [ "$status" != "ACTIVE" ]; then
        return 1
    fi
    
    # Check if there are any deployments in progress
    local deployments=$(aws ecs describe-services \
        --cluster "$cluster" \
        --services "$service" \
        --query 'services[0].deployments[?status==`PRIMARY`].runningCount' \
        --output text 2>&1)
    
    if [ -z "$deployments" ] || [ "$deployments" = "None" ]; then
        return 1
    fi
    
    return 0
}

while [ $ELAPSED -lt $MAX_WAIT_TIME ]; do
    BACKEND_READY=0
    ML_READY=0
    BACKEND_ECS_READY=0
    ML_ECS_READY=0
    
    # Check backend autoscaling
    if check_autoscaling_ready "$BACKEND_RESOURCE_ID" "$BACKEND_SERVICE"; then
        BACKEND_READY=1
    fi
    
    # Check ML autoscaling
    if check_autoscaling_ready "$ML_RESOURCE_ID" "$ML_SERVICE"; then
        ML_READY=1
    fi
    
    # Check ECS services are stable
    if check_ecs_service_stable "$CLUSTER_NAME" "$BACKEND_SERVICE"; then
        BACKEND_ECS_READY=1
    fi
    
    if check_ecs_service_stable "$CLUSTER_NAME" "$ML_SERVICE"; then
        ML_ECS_READY=1
    fi
    
    if [ $BACKEND_READY -eq 1 ] && [ $ML_READY -eq 1 ] && [ $BACKEND_ECS_READY -eq 1 ] && [ $ML_ECS_READY -eq 1 ]; then
        echo "✓ All autoscaling targets and ECS services are ready!"
        exit 0
    fi
    
    # Show status
    echo "[${ELAPSED}s] Waiting..."
    [ $BACKEND_READY -eq 1 ] && echo "  ✓ Backend autoscaling ready" || echo "  ⏳ Backend autoscaling pending"
    [ $ML_READY -eq 1 ] && echo "  ✓ ML autoscaling ready" || echo "  ⏳ ML autoscaling pending"
    [ $BACKEND_ECS_READY -eq 1 ] && echo "  ✓ Backend ECS stable" || echo "  ⏳ Backend ECS updating"
    [ $ML_ECS_READY -eq 1 ] && echo "  ✓ ML ECS stable" || echo "  ⏳ ML ECS updating"
    
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

echo "⚠️  Timeout waiting for autoscaling targets to be ready"
echo "   You may need to wait a bit longer or check AWS console for pending updates"
exit 1

