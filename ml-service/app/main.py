from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import logging
from controllers import ClassificationController
from schemas import ClassificationRequest, ClassificationResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Image Classification ML Service",
    description="Scalable image classification service supporting MobileNet and CLIP models",
    version="1.0.0"
)

# Initialize controller (loads models on startup)
controller = ClassificationController()


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Image Classification ML Service",
        "version": "1.0.0",
        "models": ["MobileNetV2", "CLIP"],
        "endpoints": {
            "classify": "POST /classify",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return controller.get_health_status()


@app.post("/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest):
    """
    Classify a batch of images from S3
    
    Args:
        request: Classification request containing:
            - job_id: Unique job identifier
            - job_type: "image_classification" or "custom_classification"
            - s3_bucket: S3 bucket containing images
            - s3_keys: List of S3 keys to images
            - custom_labels: Required for custom_classification
            - top_k: Number of predictions per image (default 5)
            - confidence_threshold: Minimum confidence (default 0.5)
        
    Returns:
        Classification results for all images grouped by label
    """
    try:
        return await controller.classify_batch(request)
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "Internal server error"}
    )