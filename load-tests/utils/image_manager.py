"""Image manager for load testing"""
import json
import random
import logging
from pathlib import Path
from typing import List, Dict, Optional

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import S3_KEYS_FILE, JOB_SIZE_DISTRIBUTION

logger = logging.getLogger(__name__)


class ImageManager:
    """Manages image selection and S3 keys for load testing"""
    
    def __init__(self, s3_keys_file: str = S3_KEYS_FILE):
        # Resolve path: if relative, look in project root (parent of load-tests)
        s3_keys_path = Path(s3_keys_file)
        if not s3_keys_path.is_absolute():
            # If running from load-tests directory, go up one level to project root
            project_root = Path(__file__).parent.parent.parent
            s3_keys_path = project_root / s3_keys_file
            # Also try current directory (load-tests) as fallback
            if not s3_keys_path.exists():
                current_dir_path = Path(s3_keys_file)
                if current_dir_path.exists():
                    s3_keys_path = current_dir_path
        
        self.s3_keys_file = str(s3_keys_path)
        self.s3_keys: Dict[str, str] = {}
        self.load_s3_keys()
    
    def load_s3_keys(self):
        """Load S3 keys from file"""
        try:
            s3_keys_path = Path(self.s3_keys_file)
            if s3_keys_path.exists():
                with open(s3_keys_path, "r") as f:
                    self.s3_keys = json.load(f)
                logger.info(f"Loaded {len(self.s3_keys)} S3 keys from {self.s3_keys_file}")
            else:
                logger.warning(f"S3 keys file not found: {self.s3_keys_file}")
                logger.warning(f"Current working directory: {Path.cwd()}")
                logger.warning(f"Looking for file at: {s3_keys_path.absolute()}")
        except Exception as e:
            logger.error(f"Failed to load S3 keys: {str(e)}")
            self.s3_keys = {}
    
    def get_all_s3_keys(self) -> List[str]:
        """Get all available S3 keys"""
        return list(self.s3_keys.values())
    
    def get_random_s3_keys(self, count: int) -> List[str]:
        """Get random S3 keys"""
        all_keys = self.get_all_s3_keys()
        if not all_keys:
            raise ValueError("No S3 keys available. Please upload images first.")
        
        # If we need more keys than available, reuse them
        if count > len(all_keys):
            return random.choices(all_keys, k=count)
        else:
            return random.sample(all_keys, count)
    
    def get_job_size(self) -> int:
        """Get random job size based on distribution"""
        rand = random.random()
        cumulative = 0.0
        
        for size_type, config in JOB_SIZE_DISTRIBUTION.items():
            cumulative += config["weight"]
            if rand <= cumulative:
                return random.randint(config["min"], config["max"])
        
        # Fallback to medium
        return random.randint(6, 20)
    
    def get_s3_keys_for_job(self) -> List[str]:
        """Get S3 keys for a single job based on size distribution"""
        job_size = self.get_job_size()
        return self.get_random_s3_keys(job_size)
    
    def get_count(self) -> int:
        """Get total number of available images"""
        return len(self.s3_keys)


# Global instance
_image_manager: Optional[ImageManager] = None


def get_image_manager() -> ImageManager:
    """Get global image manager instance"""
    global _image_manager
    if _image_manager is None:
        _image_manager = ImageManager()
    return _image_manager

