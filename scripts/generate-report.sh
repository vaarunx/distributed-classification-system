#!/bin/bash
# Generate post-test analysis and graphs

# Don't use set -e - we want to handle errors gracefully
# set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOAD_TESTS_DIR="$PROJECT_DIR/load-tests"

# Use python command (consistent with other scripts)
PYTHON_CMD="python"

echo "Generating test reports and graphs..."
echo ""

cd "$LOAD_TESTS_DIR"

# Find latest results
RESULTS_DIR="$LOAD_TESTS_DIR/results"
LATEST_LOCUST=$(ls -t "$RESULTS_DIR"/*.csv 2>/dev/null | head -1 || echo "")
LATEST_CLOUDWATCH=$(ls -t "$RESULTS_DIR"/*.json 2>/dev/null | head -1 || echo "")

if [ -z "$LATEST_LOCUST" ] && [ -z "$LATEST_CLOUDWATCH" ]; then
    echo "⚠️  Warning: No test results found in $RESULTS_DIR"
    echo "   Skipping report generation."
    exit 0  # Don't fail - just skip
fi

# Generate graphs
echo "Generating graphs..."
"$PYTHON_CMD" -m analysis.generate_graphs \
    ${LATEST_LOCUST:+"$LATEST_LOCUST"} \
    ${LATEST_CLOUDWATCH:+"$LATEST_CLOUDWATCH"} || {
    echo "⚠️  Warning: Failed to generate graphs. Continuing..."
}

# Generate summary report
echo "Generating summary report..."
"$PYTHON_CMD" -m analysis.analyze_results \
    ${LATEST_LOCUST:+"$LATEST_LOCUST"} \
    ${LATEST_CLOUDWATCH:+"$LATEST_CLOUDWATCH"} || {
    echo "⚠️  Warning: Failed to generate summary report. Continuing..."
}

echo ""
echo "Reports generated in: $LOAD_TESTS_DIR/reports"
echo "Graphs saved to: $LOAD_TESTS_DIR/reports"

