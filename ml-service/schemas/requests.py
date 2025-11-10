from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class JobType(str, Enum):
    IMAGE_CLASSIFICATION = "image_classification"
    CUSTOM_CLASSIFICATION = "custom_classification"


class Prediction(BaseModel):
    """Single prediction result"""
    label: str
    score: float


class ClassificationRequest(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    job_type: JobType = Field(..., description="Type of classification to perform")
    s3_bucket: str = Field(..., description="S3 bucket containing images")
    s3_keys: List[str] = Field(..., description="List of S3 keys to images")
    custom_labels: Optional[List[str]] = Field(
        None,
        description="Custom labels for CLIP classification (required for custom_classification)"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of top predictions to return per image"
    )
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to accept a prediction. Below this, label as 'unknown'"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "job_id": "job-12345",
                    "job_type": "image_classification",
                    "s3_bucket": "my-bucket",
                    "s3_keys": ["input/dog.jpg", "input/blurry.jpg"],
                    "top_k": 5,
                    "confidence_threshold": 0.5
                }
            ]
        }


class ImageResult(BaseModel):
    filename: str
    s3_key: str
    top_prediction: str
    top_confidence: float
    all_predictions: List[Prediction]  # Changed from List[Dict[str, float]]
    processing_time_ms: float
    reason: Optional[str] = Field(
        None,
        description="Reason for classification (e.g., why it was marked unknown)"
    )


class ClassificationSummary(BaseModel):
    total: int
    classified: int
    unknown: int


class ClassificationResponse(BaseModel):
    success: bool
    job_id: str
    job_type: str
    model_used: str
    total_images: int
    processing_time_ms: float
    grouped_by_label: Dict[str, List[str]]
    detailed_results: List[ImageResult]
    summary: ClassificationSummary