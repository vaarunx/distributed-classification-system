#!/bin/bash
# Pre-upload images to S3 for load testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOAD_TESTS_DIR="$PROJECT_DIR/load-tests"

# Default values
IMAGE_FOLDER="${IMAGE_FOLDER:-images}"
IMAGE_COUNT="${IMAGE_COUNT:-5000}"
WORKERS="${WORKERS:-20}"

echo "Pre-uploading images to S3"
echo "  Folder: $IMAGE_FOLDER"
echo "  Count: $IMAGE_COUNT"
echo "  Workers: $WORKERS"
echo ""

# Run Python script
python "$SCRIPT_DIR/pre-upload-images.py" \
    --folder "$IMAGE_FOLDER" \
    --count "$IMAGE_COUNT" \
    --workers "$WORKERS"

echo ""
echo "Upload complete!"

