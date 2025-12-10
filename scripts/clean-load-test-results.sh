#!/bin/bash
# Clean load test results and reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOAD_TESTS_DIR="$PROJECT_DIR/load-tests"

RESULTS_DIR="$LOAD_TESTS_DIR/results"
REPORTS_DIR="$LOAD_TESTS_DIR/reports"

echo "=========================================="
echo "Cleaning Load Test Results"
echo "=========================================="
echo ""

# Count files before deletion
RESULTS_COUNT=0
REPORTS_COUNT=0

if [ -d "$RESULTS_DIR" ]; then
    RESULTS_COUNT=$(find "$RESULTS_DIR" -type f 2>/dev/null | wc -l)
fi

if [ -d "$REPORTS_DIR" ]; then
    REPORTS_COUNT=$(find "$REPORTS_DIR" -type f 2>/dev/null | wc -l)
fi

TOTAL_COUNT=$((RESULTS_COUNT + REPORTS_COUNT))

if [ $TOTAL_COUNT -eq 0 ]; then
    echo "No load test results found to clean."
    echo "  Results directory: $RESULTS_DIR"
    echo "  Reports directory: $REPORTS_DIR"
    echo ""
    exit 0
fi

echo "Found:"
echo "  Results files: $RESULTS_COUNT"
echo "  Report files: $REPORTS_COUNT"
echo "  Total: $TOTAL_COUNT"
echo ""

# Ask for confirmation (skip if --yes flag is provided)
if [ "$1" != "--yes" ] && [ "$1" != "-y" ]; then
    read -p "Delete all load test results and reports? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi
else
    echo "Auto-confirming deletion (--yes flag provided)..."
fi

# Clean results directory
if [ -d "$RESULTS_DIR" ] && [ $RESULTS_COUNT -gt 0 ]; then
    echo "Cleaning results directory..."
    find "$RESULTS_DIR" -type f -delete 2>/dev/null || true
    echo "✓ Cleaned $RESULTS_COUNT files from results/"
fi

# Clean reports directory
if [ -d "$REPORTS_DIR" ] && [ $REPORTS_COUNT -gt 0 ]; then
    echo "Cleaning reports directory..."
    find "$REPORTS_DIR" -type f -delete 2>/dev/null || true
    echo "✓ Cleaned $REPORTS_COUNT files from reports/"
fi

echo ""
echo "✓ Load test results cleaned successfully!"
echo ""

