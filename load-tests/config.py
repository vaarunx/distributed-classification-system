"""Configuration for load tests"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Backend API URL
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8080")

# Test parameters
DEFAULT_RPS = 200
DEFAULT_DURATION = 300  # 5 minutes in seconds (reduced from 10 minutes)

# Image configuration
IMAGE_FOLDER = os.getenv("IMAGE_FOLDER", "images")
IMAGE_COUNT = int(os.getenv("IMAGE_COUNT", "1000"))  # Default 1000, configurable up to 2000
S3_KEYS_FILE = os.getenv("S3_KEYS_FILE", "s3_keys.json")

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# CloudWatch metrics
CLOUDWATCH_NAMESPACE = "AWS/ECS"
SQS_NAMESPACE = "AWS/SQS"
ALB_NAMESPACE = "AWS/ApplicationELB"

# Graph output directory
GRAPH_OUTPUT_DIR = os.getenv("GRAPH_OUTPUT_DIR", "reports")
RESULTS_DIR = os.getenv("RESULTS_DIR", "results")

# Job configuration
JOB_SIZE_DISTRIBUTION = {
    "small": {"min": 1, "max": 3, "weight": 0.4},
    "medium": {"min": 4, "max": 10, "weight": 0.5},
    "large": {"min": 11, "max": 20, "weight": 0.1}
}

# Ensure directories exist
Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
Path(GRAPH_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

