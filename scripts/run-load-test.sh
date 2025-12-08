#!/bin/bash
# Run a single Locust load test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOAD_TESTS_DIR="$PROJECT_DIR/load-tests"

# Use python command
PYTHON_CMD="python"

# Get test scenario name
TEST_SCENARIO="${1:-throughput_scaling}"

# Load .env file from load-tests directory if it exists
ENV_FILE="$LOAD_TESTS_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    # Export variables from .env file (handles KEY=value format, ignores comments and empty lines)
    set -a  # automatically export all variables
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        case "$line" in
            \#*|'') continue ;;
        esac
        # Parse KEY=value and export (handles values with spaces and special chars)
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            # Remove quotes if present
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"
            export "$key"="$value"
        fi
    done < "$ENV_FILE"
    set +a
    echo "Loaded configuration from $ENV_FILE"
fi

# Get backend URL - try environment variable (from .env or already set), then Terraform, then default to localhost
if [ -z "$BACKEND_API_URL" ]; then
    # Try to get ALB endpoint from Terraform
    TERRAFORM_DIR="$PROJECT_DIR/terraform"
    if [ -d "$TERRAFORM_DIR" ]; then
        cd "$TERRAFORM_DIR"
        ALB_ENDPOINT=$(terraform output -raw alb_endpoint 2>/dev/null || echo "")
        if [ -n "$ALB_ENDPOINT" ]; then
            BACKEND_URL="$ALB_ENDPOINT"
            echo "Using ALB endpoint from Terraform: $BACKEND_URL"
        else
            BACKEND_URL="http://localhost:8080"
            echo "⚠️  Warning: Could not get ALB endpoint from Terraform"
            echo "   Using default: $BACKEND_URL"
            echo "   Set BACKEND_API_URL environment variable or deploy infrastructure"
        fi
        cd "$PROJECT_DIR"
    else
        BACKEND_URL="http://localhost:8080"
        echo "⚠️  Warning: Terraform directory not found"
        echo "   Using default: $BACKEND_URL"
        echo "   Set BACKEND_API_URL environment variable to point to your backend"
    fi
else
    BACKEND_URL="$BACKEND_API_URL"
fi

# Configuration
USERS="${LOCUST_USERS:-25}"
SPAWN_RATE="${LOCUST_SPAWN_RATE:-5}"
DURATION="${LOCUST_DURATION:-300}"

# Adjust throughput_scaling test for 20-minute queue clear
if [ "$TEST_SCENARIO" = "throughput_scaling" ]; then
    USERS=20  # Reduced load for throughput scaling test
fi

RESULTS_DIR="$LOAD_TESTS_DIR/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Running load test: $TEST_SCENARIO"
echo "  Backend URL: $BACKEND_URL"
echo "  Users: $USERS"
echo "  Spawn Rate: $SPAWN_RATE"
echo "  Duration: ${DURATION}s"
echo ""

# Show autoscaling status hint for throughput_scaling
if [ "$TEST_SCENARIO" = "throughput_scaling" ]; then
    echo "⚠️  Note: This test works best with autoscaling DISABLED"
    echo "   Run: $SCRIPT_DIR/manage-autoscaling.sh suspend"
    echo ""
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

# Set environment
export BACKEND_API_URL="$BACKEND_URL"

# Start metrics collection
echo "Starting metrics collection..."
"$PYTHON_CMD" "$SCRIPT_DIR/collect-metrics.py" "$TEST_SCENARIO" start || {
    echo "⚠️  Warning: Failed to start metrics collection. Continuing with test..."
}

# Run Locust in headless mode
cd "$LOAD_TESTS_DIR"

# Convert test scenario name to class name (e.g., throughput_scaling -> ThroughputScalingUser)
CLASS_NAME=$(echo "$TEST_SCENARIO" | sed 's/_\([a-z]\)/\U\1/g' | sed 's/^\([a-z]\)/\U\1/g')User

# Run Locust - capture exit code (exit code 1 is normal when time limit is reached)
set +e  # Temporarily disable exit on error
locust \
    --headless \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "${DURATION}s" \
    --host "$BACKEND_URL" \
    --csv "$RESULTS_DIR/${TEST_SCENARIO}_${TIMESTAMP}" \
    --html "$RESULTS_DIR/${TEST_SCENARIO}_${TIMESTAMP}.html" \
    --locustfile locustfile.py \
    --class "$CLASS_NAME"
LOCUST_EXIT_CODE=$?
set -e  # Re-enable exit on error

# Locust exits with code 1 when time limit is reached - this is normal/successful
if [ $LOCUST_EXIT_CODE -eq 1 ]; then
    echo ""
    echo "Test complete! Results saved to: $RESULTS_DIR/${TEST_SCENARIO}_${TIMESTAMP}"
    echo "  (Locust exit code 1 is normal when time limit is reached)"
    echo ""
elif [ $LOCUST_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠️  Warning: Locust exited with code $LOCUST_EXIT_CODE"
    echo "  Results may be incomplete, but continuing with metrics collection..."
    echo ""
else
    echo ""
    echo "Test complete! Results saved to: $RESULTS_DIR/${TEST_SCENARIO}_${TIMESTAMP}"
    echo ""
fi

# Extend metrics collection until queue is empty
echo "Extending metrics collection until queue is empty..."
"$PYTHON_CMD" "$SCRIPT_DIR/collect-metrics.py" "$TEST_SCENARIO" extend || {
    echo "⚠️  Warning: Failed to extend metrics collection. Metrics may be incomplete."
}

