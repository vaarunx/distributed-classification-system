"""S3 upload client using presigned URLs"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def upload_to_s3(presigned_url: str, file_data: bytes, content_type: str) -> bool:
    """
    Upload file to S3 using presigned URL
    
    Args:
        presigned_url: Presigned PUT URL from backend
        file_data: File content as bytes
        content_type: MIME type of the file
        
    Returns:
        True if upload successful, False otherwise
    """
    try:
        headers = {
            "Content-Type": content_type
        }
        
        response = requests.put(presigned_url, data=file_data, headers=headers, timeout=60)
        response.raise_for_status()
        
        logger.info(f"Successfully uploaded file to S3")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        return False

