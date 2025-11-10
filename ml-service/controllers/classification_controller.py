from PIL import Image
import io
import logging
import boto3
from typing import List, Dict
import time
from botocore.exceptions import ClientError
from models import MobileNetModel, ClipModel
from schemas.requests import (
    ClassificationRequest,
    ClassificationResponse,
    ImageResult,
    ClassificationSummary,
    JobType, Prediction
)

logger = logging.getLogger(__name__)


class ClassificationController:
    """Controller for handling classification requests"""
    
    def __init__(self):
        # Initialize models
        self.mobilenet = MobileNetModel()
        self.clip = ClipModel()
        
        # Load models on startup
        self.mobilenet.load_model()
        self.clip.load_model()
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        logger.info("Classification controller initialized with all models")
    
    def _download_image_from_s3(self, bucket: str, key: str) -> Image.Image:
        """Download image from S3 and return PIL Image"""
        try:
            # Download image
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            image_bytes = response['Body'].read()
            
            # Open as PIL Image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            return image
            
        except ClientError as e:
            logger.error(f"Failed to download from S3: s3://{bucket}/{key}, Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to process image from S3: s3://{bucket}/{key}, Error: {str(e)}")
            raise
    
    async def _classify_single_image(
        self,
        s3_bucket: str,
        s3_key: str,
        job_type: JobType,
        top_k: int,
        custom_labels: List[str] = None,
        confidence_threshold: float = 0.5
    ) -> ImageResult:
        """Classify a single image"""
        start_time = time.time()
        
        try:
            # Download image
            image = self._download_image_from_s3(s3_bucket, s3_key)
            
            # Run classification
            if job_type == JobType.IMAGE_CLASSIFICATION:
                predictions = self._classify_with_mobilenet(image, top_k)
            else:
                predictions = self._classify_with_clip(image, custom_labels, top_k)
            
            processing_time = (time.time() - start_time) * 1000
            
            # Extract filename
            filename = s3_key.split('/')[-1]
            
            # Check confidence threshold
            top_prediction = predictions[0]['label']
            top_confidence = predictions[0]['score']
            reason = None
            
            if top_confidence < confidence_threshold:
                original_prediction = top_prediction
                top_prediction = "unknown"
                reason = f"confidence below threshold ({top_confidence:.2f} < {confidence_threshold}). Original prediction: {original_prediction}"
                logger.info(f"{filename}: Marked as unknown due to low confidence")
            
            return ImageResult(
                filename=filename,
                s3_key=s3_key,
                top_prediction=top_prediction,
                top_confidence=top_confidence,
                all_predictions=[Prediction(label=p['label'], score=p['score']) for p in predictions],  # Convert to Prediction objects,
                processing_time_ms=processing_time,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Failed to classify {s3_key}: {str(e)}")
            raise
    
    async def classify_batch(
        self,
        request: ClassificationRequest
    ) -> ClassificationResponse:
        """
        Classify a batch of images from S3
        
        Args:
            request: Classification request with S3 paths
            
        Returns:
            Classification response with all results grouped by label
        """
        start_time = time.time()
        
        try:
            # Validate custom labels if needed
            if request.job_type == JobType.CUSTOM_CLASSIFICATION:
                if not request.custom_labels:
                    raise ValueError("custom_labels is required for custom_classification")
            
            # Process all images
            detailed_results = []
            grouped_by_label = {}
            
            for s3_key in request.s3_keys:
                result = await self._classify_single_image(
                    s3_bucket=request.s3_bucket,
                    s3_key=s3_key,
                    job_type=request.job_type,
                    top_k=request.top_k,
                    custom_labels=request.custom_labels,
                    confidence_threshold=request.confidence_threshold
                )
                
                detailed_results.append(result)
                
                # Group by label
                label = result.top_prediction
                if label not in grouped_by_label:
                    grouped_by_label[label] = []
                grouped_by_label[label].append(result.filename)
            
            total_time = (time.time() - start_time) * 1000
            
            # Determine model used
            model_used = "MobileNetV2" if request.job_type == JobType.IMAGE_CLASSIFICATION else "CLIP"
            
            # Calculate summary
            unknown_count = len(grouped_by_label.get("unknown", []))
            classified_count = len(detailed_results) - unknown_count
            
            summary = ClassificationSummary(
                total=len(detailed_results),
                classified=classified_count,
                unknown=unknown_count
            )
            
            logger.info(
                f"Job {request.job_id} complete: "
                f"{len(detailed_results)} images processed, "
                f"{classified_count} classified, {unknown_count} unknown "
                f"(threshold: {request.confidence_threshold})"
            )
            
            return ClassificationResponse(
                success=True,
                job_id=request.job_id,
                job_type=request.job_type.value,
                model_used=model_used,
                total_images=len(detailed_results),
                processing_time_ms=total_time,
                grouped_by_label=grouped_by_label,
                detailed_results=detailed_results,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Batch classification failed for job {request.job_id}: {str(e)}")
            raise
    
    def _classify_with_mobilenet(self, image: Image.Image, top_k: int) -> List[Dict]:
        """Use MobileNet for classification"""
        return self.mobilenet.predict(image, top_k=top_k)
    
    def _classify_with_clip(self, image: Image.Image, custom_labels: list, top_k: int) -> List[Dict]:
        """Use CLIP for custom classification"""
        return self.clip.predict(image, custom_labels=custom_labels, top_k=top_k)
    
    def get_health_status(self) -> Dict:
        """Get health status of all models"""
        return {
            "status": "healthy",
            "models": {
                "mobilenet": {
                    "loaded": self.mobilenet.is_loaded(),
                    "name": self.mobilenet.model_name
                },
                "clip": {
                    "loaded": self.clip.is_loaded(),
                    "name": self.clip.model_name
                }
            }
        }