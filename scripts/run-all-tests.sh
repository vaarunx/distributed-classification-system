#!/bin/bash
# Run all high-impact load tests sequentially with autoscaling management

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use python command
PYTHON_CMD="python"

# Test scenarios with their autoscaling requirements
# Format: "test_name:autoscaling_state"
TESTS=(
    # "throughput_scaling:suspend"  # Disabled - not running throughput_scaling test
    "autoscaling_response:resume"
    "queue_explosion:resume"
    "sustained_load:resume"
)

echo "=========================================="
echo "Running All Load Tests"
echo "=========================================="
echo ""
echo "Note: Autoscaling will be managed automatically between tests"
echo ""

# Track autoscaling state
CURRENT_AUTOSCALING_STATE=""
FIRST_TEST=true

for test_config in "${TESTS[@]}"; do
    IFS=':' read -r test_name autoscaling_state <<< "$test_config"
    
    echo "=========================================="
    echo "Running: $test_name"
    echo "  Required autoscaling state: $autoscaling_state"
    echo "=========================================="
    echo ""
    
    # Wait for queue to empty first (except for first test)
    # This allows autoscaling to naturally scale down as queue empties
    if [ "$FIRST_TEST" = false ]; then
        echo "Waiting for queue to empty (allowing autoscaling to scale down naturally)..."
        "$PYTHON_CMD" "$SCRIPT_DIR/collect-metrics.py" "$test_name" check-queue || {
            echo "Queue not empty. Waiting for queue to clear..."
            "$PYTHON_CMD" "$SCRIPT_DIR/collect-metrics.py" "$test_name" wait-queue || {
                echo "❌ Error: Failed to clear queue. Aborting test sequence."
                exit 1
            }
        }
        echo ""
        
        # Now reset both services to baseline (1 task each) after queue is empty
        echo "Queue is empty. Resetting services to baseline (1 task each)..."
        "$SCRIPT_DIR/scale-backend-service.sh" 1 || {
            echo "⚠️  Warning: Failed to reset backend service. Continuing anyway..."
        }
        "$SCRIPT_DIR/scale-ml-service.sh" 1 || {
            echo "⚠️  Warning: Failed to reset ML service. Continuing anyway..."
        }
        echo "Waiting 15 seconds for services to stabilize..."
        sleep 15
        echo ""
    fi
    FIRST_TEST=false
    
    # Manage autoscaling state if needed
    if [ "$CURRENT_AUTOSCALING_STATE" != "$autoscaling_state" ]; then
        echo "Changing autoscaling state to: $autoscaling_state"
        "$SCRIPT_DIR/manage-autoscaling.sh" "$autoscaling_state" || {
            echo "⚠️  Warning: Failed to change autoscaling state to $autoscaling_state"
            echo "   Continuing with test anyway..."
        }
        CURRENT_AUTOSCALING_STATE="$autoscaling_state"
        
        # Wait for autoscaling state to take effect
        echo "Waiting 30 seconds for autoscaling state to stabilize..."
        sleep 30
        echo ""
    fi
    
    # Scale ML service to 50 tasks before throughput_scaling test
    if [ "$test_name" = "throughput_scaling" ]; then
        echo "Scaling ML service to 50 tasks for throughput_scaling test..."
        "$SCRIPT_DIR/scale-ml-service.sh" 50 || {
            echo "⚠️  Warning: Failed to scale ML service to 50 tasks. Continuing anyway..."
        }
        echo ""
    fi
    
    # Run the test (metrics collection is handled within run-load-test.sh)
    # Don't fail if Locust exits with code 1 (normal when time limit is reached)
    "$SCRIPT_DIR/run-load-test.sh" "$test_name" || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 1 ]; then
            echo "⚠️  Warning: Test script exited with code 1, but continuing with next test..."
        else
            echo "❌ Error: Test script failed with exit code $EXIT_CODE"
            echo "  Aborting test sequence."
            exit 1
        fi
    }
    
    # Scale ML service back to 1 task after throughput_scaling test
    if [ "$test_name" = "throughput_scaling" ]; then
        echo ""
        echo "Scaling ML service back to 1 task after throughput_scaling test..."
        "$SCRIPT_DIR/scale-ml-service.sh" 1 || {
            echo "⚠️  Warning: Failed to scale ML service back to 1 task."
        }
        echo ""
    fi
    
    echo ""
    echo "Test completed. Metrics collection extended until queue is empty."
    echo ""
done

echo "=========================================="
echo "All Tests Complete!"
echo "=========================================="
echo ""

# Ensure autoscaling is resumed at the end
echo "Resuming autoscaling to normal state..."
"$SCRIPT_DIR/manage-autoscaling.sh" resume || {
    echo "⚠️  Warning: Failed to resume autoscaling. You may need to resume it manually."
}
echo ""

echo "Generating reports..."
"$SCRIPT_DIR/generate-report.sh" || {
    echo "⚠️  Warning: Failed to generate reports. You can run it manually:"
    echo "   $SCRIPT_DIR/generate-report.sh"
}

echo ""
echo "Done!"

