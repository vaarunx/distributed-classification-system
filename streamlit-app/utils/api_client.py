"""API client for interacting with the backend service"""
import os
import requests
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class APIClient:
    """Client for backend API interactions"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("BACKEND_API_URL", "http://localhost:8080")
        if not self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {method} {url} - {str(e)}")
            raise
    
    def get_upload_url(self, filename: str, content_type: str) -> Dict[str, Any]:
        """Get presigned URL for uploading an image"""
        data = {
            "filename": filename,
            "content_type": content_type
        }
        response = self._request("POST", "/upload-url", json=data)
        return response.json()
    
    def list_images(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all images in the input bucket"""
        params = {}
        if prefix:
            params["prefix"] = prefix
        
        response = self._request("GET", "/images", params=params)
        data = response.json()
        return data.get("images", [])
    
    def delete_image(self, s3_key: str) -> Dict[str, Any]:
        """Delete an image from S3"""
        # URL encode the key
        import urllib.parse
        encoded_key = urllib.parse.quote(s3_key, safe="")
        response = self._request("DELETE", f"/images/{encoded_key}")
        return response.json()
    
    def submit_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a classification job"""
        response = self._request("POST", "/submit", json=job_data)
        return response.json()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a job"""
        response = self._request("GET", f"/status/{job_id}")
        return response.json()
    
    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """Get results of a completed job"""
        response = self._request("GET", f"/result/{job_id}")
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check backend health"""
        response = self._request("GET", "/health")
        return response.json()
    
    def list_jobs(self, limit: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs with optional filtering"""
        params = {}
        if limit is not None:
            params["limit"] = str(limit)
        if status:
            params["status"] = status
        
        response = self._request("GET", "/jobs", params=params)
        data = response.json()
        return data.get("jobs", [])

