#!/bin/bash
# Manage ECS autoscaling state for load testing

# Don't use set -e here - we want to handle errors gracefully
# set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Get cluster and service names from Terraform or use defaults
cd "$PROJECT_DIR/terraform"

# Try direct outputs first (if terraform apply was run after adding outputs)
CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null || echo "")
BACKEND_SERVICE=$(terraform output -raw backend_service_name 2>/dev/null || echo "")
ML_SERVICE=$(terraform output -raw ml_service_name 2>/dev/null || echo "")

# If direct outputs don't exist, try getting from aws_resources nested output
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME=$(terraform output -json aws_resources 2>/dev/null | \
        python -c "import sys, json; d=json.load(sys.stdin); print(d.get('cluster_name', ''))" 2>/dev/null || echo "")
fi

# If still empty, use default naming convention (based on Terraform code)
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME="distributed-classifier-cluster"
    BACKEND_SERVICE="distributed-classifier-backend-service"
    ML_SERVICE="distributed-classifier-ml-service"
    echo "Using default names (run 'terraform apply' to get actual names from outputs)"
else
    # If we have cluster name but not service names, use defaults
    if [ -z "$BACKEND_SERVICE" ]; then
        BACKEND_SERVICE="distributed-classifier-backend-service"
    fi
    if [ -z "$ML_SERVICE" ]; then
        ML_SERVICE="distributed-classifier-ml-service"
    fi
fi

# Allow environment variable overrides
CLUSTER_NAME="${CLUSTER_NAME_ENV:-$CLUSTER_NAME}"
BACKEND_SERVICE="${BACKEND_SERVICE_ENV:-$BACKEND_SERVICE}"
ML_SERVICE="${ML_SERVICE_ENV:-$ML_SERVICE}"

echo "Using:"
echo "  Cluster: $CLUSTER_NAME"
echo "  Backend Service: $BACKEND_SERVICE"
echo "  ML Service: $ML_SERVICE"
echo ""

BACKEND_RESOURCE_ID="service/${CLUSTER_NAME}/${BACKEND_SERVICE}"
ML_RESOURCE_ID="service/${CLUSTER_NAME}/${ML_SERVICE}"

ACTION="${1:-status}"

case "$ACTION" in
    suspend|disable)
        echo "Suspending autoscaling for both services..."
        echo "  Backend: $BACKEND_RESOURCE_ID"
        echo "  ML Service: $ML_RESOURCE_ID"
        
        BACKEND_SUCCESS=0
        ML_SUCCESS=0
        
        aws application-autoscaling register-scalable-target \
            --service-namespace ecs \
            --scalable-dimension ecs:service:DesiredCount \
            --resource-id "$BACKEND_RESOURCE_ID" \
            --suspended-state DynamicScalingOutSuspended=true,DynamicScalingInSuspended=true,ScheduledScalingSuspended=true && \
        BACKEND_SUCCESS=1 || {
            echo "⚠️  Warning: Failed to suspend autoscaling for backend service"
        }
        
        aws application-autoscaling register-scalable-target \
            --service-namespace ecs \
            --scalable-dimension ecs:service:DesiredCount \
            --resource-id "$ML_RESOURCE_ID" \
            --suspended-state DynamicScalingOutSuspended=true,DynamicScalingInSuspended=true,ScheduledScalingSuspended=true && \
        ML_SUCCESS=1 || {
            echo "⚠️  Warning: Failed to suspend autoscaling for ML service"
        }
        
        if [ $BACKEND_SUCCESS -eq 1 ] && [ $ML_SUCCESS -eq 1 ]; then
            echo "✓ Autoscaling suspended for both services"
        elif [ $BACKEND_SUCCESS -eq 1 ] || [ $ML_SUCCESS -eq 1 ]; then
            echo "⚠️  Partially suspended autoscaling (some services may still be active)"
            exit 1
        else
            echo "❌ Failed to suspend autoscaling for both services"
            exit 1
        fi
        ;;
    
    resume|enable)
        echo "Resuming autoscaling for both services..."
        echo "  Backend: $BACKEND_RESOURCE_ID"
        echo "  ML Service: $ML_RESOURCE_ID"
        
        BACKEND_SUCCESS=0
        ML_SUCCESS=0
        
        aws application-autoscaling register-scalable-target \
            --service-namespace ecs \
            --scalable-dimension ecs:service:DesiredCount \
            --resource-id "$BACKEND_RESOURCE_ID" \
            --suspended-state DynamicScalingOutSuspended=false,DynamicScalingInSuspended=false,ScheduledScalingSuspended=false && \
        BACKEND_SUCCESS=1 || {
            echo "⚠️  Warning: Failed to resume autoscaling for backend service"
        }
        
        aws application-autoscaling register-scalable-target \
            --service-namespace ecs \
            --scalable-dimension ecs:service:DesiredCount \
            --resource-id "$ML_RESOURCE_ID" \
            --suspended-state DynamicScalingOutSuspended=false,DynamicScalingInSuspended=false,ScheduledScalingSuspended=false && \
        ML_SUCCESS=1 || {
            echo "⚠️  Warning: Failed to resume autoscaling for ML service"
        }
        
        if [ $BACKEND_SUCCESS -eq 1 ] && [ $ML_SUCCESS -eq 1 ]; then
            echo "✓ Autoscaling resumed for both services"
        elif [ $BACKEND_SUCCESS -eq 1 ] || [ $ML_SUCCESS -eq 1 ]; then
            echo "⚠️  Partially resumed autoscaling (some services may still be suspended)"
            exit 1
        else
            echo "❌ Failed to resume autoscaling for both services"
            exit 1
        fi
        ;;
    
    status)
        echo "Checking autoscaling status..."
        echo ""
        echo "Backend service ($BACKEND_SERVICE):"
        aws application-autoscaling describe-scalable-targets \
            --service-namespace ecs \
            --resource-ids "$BACKEND_RESOURCE_ID" \
            --query 'ScalableTargets[0].SuspendedState' \
            --output json 2>/dev/null || echo "  Not found or error"
        
        echo ""
        echo "ML service ($ML_SERVICE):"
        aws application-autoscaling describe-scalable-targets \
            --service-namespace ecs \
            --resource-ids "$ML_RESOURCE_ID" \
            --query 'ScalableTargets[0].SuspendedState' \
            --output json 2>/dev/null || echo "  Not found or error"
        ;;
    
    *)
        echo "Usage: $0 {suspend|resume|status}"
        echo ""
        echo "Commands:"
        echo "  suspend - Disable autoscaling (for throughput_scaling test)"
        echo "  resume  - Enable autoscaling (for autoscaling tests)"
        echo "  status  - Check current autoscaling status"
        echo ""
        exit 1
        ;;
esac

