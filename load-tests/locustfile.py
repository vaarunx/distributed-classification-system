"""Main Locust file for load testing"""
import random
import time
import logging
from locust import HttpUser, task, between, events
from typing import Dict, List

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.image_manager import get_image_manager
from config import BACKEND_API_URL

# Import test scenario classes so Locust can find them
from test_scenarios.throughput_scaling import ThroughputScalingUser
from test_scenarios.autoscaling_response import AutoscalingResponseUser
from test_scenarios.queue_explosion import QueueExplosionUser
from test_scenarios.sustained_load import SustainedLoadUser

logger = logging.getLogger(__name__)


class JobSubmitterUser(HttpUser):
    """User that submits classification jobs"""
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """Initialize on user start"""
        self.image_manager = get_image_manager()
        self.job_ids: List[str] = []
    
    @task(10)
    def submit_job(self):
        """Submit a classification job"""
        try:
            # Get S3 keys for job
            s3_keys = self.image_manager.get_s3_keys_for_job()
            
            # Submit job
            job_data = {
                "job_type": random.choice(["image_classification", "custom_classification"]),
                "s3_keys": s3_keys,
                "top_k": random.randint(3, 10),
                "confidence_threshold": round(random.uniform(0.3, 0.8), 2)
            }
            
            # Add custom labels for custom classification
            if job_data["job_type"] == "custom_classification":
                job_data["custom_labels"] = random.choice([
                    ["dog", "cat", "bird", "car", "person"],
                    ["building", "tree", "sky", "road", "sign"],
                    ["food", "drink", "plate", "cup", "bottle"]
                ])
            
            response = self.client.post(
                "/submit",
                json=job_data,
                name="/submit",
                catch_response=True
            )
            
            if response.status_code == 202:
                result = response.json()
                job_id = result.get("job_id")
                if job_id:
                    self.job_ids.append(job_id)
                    response.success()
                else:
                    response.failure("No job_id in response")
            else:
                response.failure(f"Status code: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error submitting job: {str(e)}")
    
    @task(2)
    def get_job_status(self):
        """Check status of a submitted job"""
        if not self.job_ids:
            return
        
        job_id = random.choice(self.job_ids)
        try:
            response = self.client.get(
                f"/status/{job_id}",
                name="/status/[job_id]",
                catch_response=True
            )
            
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error checking status: {str(e)}")
    
    @task(1)
    def get_job_result(self):
        """Get result of a completed job"""
        if not self.job_ids:
            return
        
        job_id = random.choice(self.job_ids)
        try:
            response = self.client.get(
                f"/result/{job_id}",
                name="/result/[job_id]",
                catch_response=True
            )
            
            if response.status_code in [200, 202]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error getting result: {str(e)}")


class StatusCheckerUser(HttpUser):
    """User that only checks job status"""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize on user start"""
        self.job_ids: List[str] = []
        # Get some job IDs from previous submissions (in real scenario)
    
    @task
    def check_status(self):
        """Check status of a job"""
        if not self.job_ids:
            # Try a random job ID (might not exist)
            job_id = f"test-{random.randint(1000, 9999)}"
        else:
            job_id = random.choice(self.job_ids)
        
        try:
            self.client.get(
                f"/status/{job_id}",
                name="/status/[job_id]"
            )
        except Exception as e:
            logger.error(f"Error checking status: {str(e)}")


class ResultRetrieverUser(HttpUser):
    """User that retrieves job results"""
    wait_time = between(2, 5)
    
    def on_start(self):
        """Initialize on user start"""
        self.job_ids: List[str] = []
    
    @task
    def get_result(self):
        """Get result of a job"""
        if not self.job_ids:
            return
        
        job_id = random.choice(self.job_ids)
        try:
            self.client.get(
                f"/result/{job_id}",
                name="/result/[job_id]"
            )
        except Exception as e:
            logger.error(f"Error getting result: {str(e)}")


class ImageUploaderUser(HttpUser):
    """User that uploads images (optional for mixed tests)"""
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Initialize on user start"""
        self.image_manager = get_image_manager()
    
    @task
    def upload_image(self):
        """Upload an image (simplified - in real scenario would upload file)"""
        # This is a placeholder - actual upload would require file handling
        # For load testing, we assume images are pre-uploaded
        try:
            # Just get upload URL (doesn't actually upload)
            response = self.client.post(
                "/upload-url",
                json={
                    "filename": f"test_{random.randint(1, 1000)}.jpg",
                    "content_type": "image/jpeg"
                },
                name="/upload-url"
            )
        except Exception as e:
            logger.error(f"Error getting upload URL: {str(e)}")


# Set base URL
class WebsiteUser(HttpUser):
    """Base user class"""
    host = BACKEND_API_URL

