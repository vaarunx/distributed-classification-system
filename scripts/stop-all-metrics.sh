#!/bin/bash
# Stop all active metrics collections

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$PROJECT_DIR/load-tests/results"

echo "Stopping all metrics collections..."
echo ""

# Find all metrics state files
STATE_FILES=$(find "$RESULTS_DIR" -name "*_metrics_state.json" -type f 2>/dev/null || true)

if [ -z "$STATE_FILES" ]; then
    echo "No active metrics collections found."
    exit 0
fi

# Stop collection for each state file
STOPPED=0
for state_file in $STATE_FILES; do
    # Extract test scenario name from filename
    # Format: <test_scenario>_metrics_state.json
    filename=$(basename "$state_file")
    test_scenario=$(echo "$filename" | sed 's/_metrics_state\.json$//')
    
    if [ -n "$test_scenario" ]; then
        echo "Stopping metrics collection for: $test_scenario"
        python3 "$SCRIPT_DIR/collect-metrics.py" "$test_scenario" stop || {
            echo "⚠️  Warning: Failed to stop collection for $test_scenario"
        }
        STOPPED=$((STOPPED + 1))
    fi
done

echo ""
if [ $STOPPED -gt 0 ]; then
    echo "Stopped $STOPPED metrics collection(s)."
else
    echo "No metrics collections were stopped."
fi

