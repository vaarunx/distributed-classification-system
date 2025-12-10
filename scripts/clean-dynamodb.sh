#!/bin/bash
# Clean/empty DynamoDB table - wrapper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use python command
PYTHON_CMD="python"

echo "=========================================="
echo "Cleaning DynamoDB Table"
echo "=========================================="
echo ""

# Run the Python script to empty DynamoDB
"$PYTHON_CMD" "$SCRIPT_DIR/empty-dynamodb.py" || {
    echo ""
    echo "❌ Error: Failed to clean DynamoDB table"
    exit 1
}

echo ""
echo "✓ DynamoDB table cleaned successfully!"
echo ""

