#!/usr/bin/env python3
"""Pre-upload images to S3 for load testing"""
import sys
import os
import logging
from pathlib import Path

# Add load-tests to path
sys.path.insert(0, str(Path(__file__).parent.parent / "load-tests"))

from utils.s3_helper import pre_upload_images
from config import IMAGE_FOLDER, IMAGE_COUNT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pre-upload images to S3")
    parser.add_argument(
        "--folder",
        default=IMAGE_FOLDER,
        help=f"Image folder path (default: {IMAGE_FOLDER})"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=IMAGE_COUNT,
        help=f"Number of images to upload (default: {IMAGE_COUNT})"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)"
    )
    
    args = parser.parse_args()
    
    print(f"Starting image upload:")
    print(f"  Folder: {args.folder}")
    print(f"  Count: {args.count}")
    print(f"  Workers: {args.workers}")
    print()
    
    try:
        s3_keys = pre_upload_images(
            folder=args.folder,
            max_count=args.count,
            max_workers=args.workers
        )
        
        print(f"\nUpload complete! {len(s3_keys)} images uploaded.")
        print(f"S3 keys saved to: s3_keys.json")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

