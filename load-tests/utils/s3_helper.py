"""S3 helper utilities for image upload"""
import json
import os
import requests
import logging
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BACKEND_API_URL, IMAGE_FOLDER, S3_KEYS_FILE, IMAGE_COUNT

logger = logging.getLogger(__name__)


def get_upload_url(filename: str, content_type: str) -> Dict:
    """Get presigned upload URL from backend"""
    try:
        response = requests.post(
            f"{BACKEND_API_URL}/upload-url",
            json={
                "filename": filename,
                "content_type": content_type
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get upload URL for {filename}: {str(e)}")
        raise


def upload_to_s3(presigned_url: str, file_data: bytes, content_type: str) -> bool:
    """Upload file to S3 using presigned URL"""
    try:
        headers = {"Content-Type": content_type}
        response = requests.put(presigned_url, data=file_data, headers=headers, timeout=60)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        return False


def get_image_files(folder: str, max_count: Optional[int] = None) -> List[Path]:
    """Get list of image files from folder"""
    folder_path = Path(folder)
    if not folder_path.exists():
        raise ValueError(f"Image folder not found: {folder}")
    
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    image_files = [
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if max_count:
        image_files = image_files[:max_count]
    
    return image_files


def get_content_type(filename: str) -> str:
    """Get content type from filename"""
    ext = Path(filename).suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp"
    }
    return content_types.get(ext, "image/jpeg")


def upload_single_image(image_path: Path, checkpoint: Dict) -> Optional[Dict]:
    """Upload a single image to S3"""
    filename = image_path.name
    s3_key = checkpoint.get(filename)
    
    # Skip if already uploaded
    if s3_key:
        logger.debug(f"Skipping {filename} (already uploaded)")
        return {"filename": filename, "s3_key": s3_key}
    
    try:
        # Read file
        file_data = image_path.read_bytes()
        content_type = get_content_type(filename)
        
        # Get presigned URL
        upload_info = get_upload_url(filename, content_type)
        s3_key = upload_info["s3_key"]
        
        # Upload to S3
        success = upload_to_s3(upload_info["upload_url"], file_data, content_type)
        
        if success:
            return {"filename": filename, "s3_key": s3_key}
        else:
            logger.error(f"Failed to upload {filename}")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading {filename}: {str(e)}")
        return None


def pre_upload_images(
    folder: str = IMAGE_FOLDER,
    max_count: int = IMAGE_COUNT,
    max_workers: int = 10,
    checkpoint_file: str = "upload_checkpoint.json"
) -> Dict[str, str]:
    """Pre-upload images to S3 with progress tracking"""
    logger.info(f"Starting image upload: {max_count} images from {folder}")
    
    # Load checkpoint
    checkpoint = {}
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r") as f:
            checkpoint = json.load(f)
        logger.info(f"Resuming from checkpoint: {len(checkpoint)} images already uploaded")
    
    # Get image files
    image_files = get_image_files(folder, max_count)
    logger.info(f"Found {len(image_files)} image files")
    
    # Filter out already uploaded
    remaining = [f for f in image_files if f.name not in checkpoint]
    logger.info(f"Remaining to upload: {len(remaining)}")
    
    if not remaining:
        logger.info("All images already uploaded")
        return checkpoint
    
    # Upload images in parallel
    s3_keys = checkpoint.copy()
    uploaded = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(upload_single_image, img, checkpoint): img
            for img in remaining
        }
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                s3_keys[result["filename"]] = result["s3_key"]
                uploaded += 1
                
                # Save checkpoint every 10 images
                if uploaded % 10 == 0:
                    with open(checkpoint_file, "w") as f:
                        json.dump(s3_keys, f, indent=2)
                    logger.info(f"Progress: {uploaded}/{len(remaining)} uploaded")
            else:
                failed += 1
    
    # Save final checkpoint
    with open(checkpoint_file, "w") as f:
        json.dump(s3_keys, f, indent=2)
    
    # Save S3 keys mapping
    with open(S3_KEYS_FILE, "w") as f:
        json.dump(s3_keys, f, indent=2)
    
    logger.info(f"Upload complete: {uploaded} uploaded, {failed} failed, {len(s3_keys)} total")
    return s3_keys


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Pre-upload images to S3")
    parser.add_argument("--folder", default=IMAGE_FOLDER, help=f"Image folder path (default: {IMAGE_FOLDER})")
    parser.add_argument("--count", type=int, default=IMAGE_COUNT, help=f"Number of images to upload (default: {IMAGE_COUNT})")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers (default: 10)")
    
    args = parser.parse_args()
    pre_upload_images(folder=args.folder, max_count=args.count, max_workers=args.workers)

