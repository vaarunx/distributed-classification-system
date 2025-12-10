"""Test scenario: Queue depth explosion"""
import logging
from locust import HttpUser, task, between
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.image_manager import get_image_manager

logger = logging.getLogger(__name__)


class QueueExplosionUser(HttpUser):
    """User for queue explosion test - rapid burst"""
    wait_time = between(0.05, 0.15)  # Reduced RPS for lower load
    
    def on_start(self):
        """Initialize on user start"""
        self.image_manager = get_image_manager()
        self.job_ids = []
    
    @task
    def submit_job(self):
        """Submit classification job rapidly"""
        try:
            s3_keys = self.image_manager.get_s3_keys_for_job()
            
            job_data = {
                "job_type": "image_classification",
                "s3_keys": s3_keys,
                "top_k": 5,
                "confidence_threshold": 0.5
            }
            
            response = self.client.post(
                "/submit",
                json=job_data,
                name="/submit"
            )
            
            if response.status_code == 202:
                result = response.json()
                job_id = result.get("job_id")
                if job_id:
                    self.job_ids.append(job_id)
        except Exception as e:
            logger.error(f"Error submitting job: {str(e)}")

