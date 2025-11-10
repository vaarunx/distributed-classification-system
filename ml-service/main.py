from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import logging
import asyncio
import threading
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
    description="Scalable image classification service supporting MobileNet and CLIP models with SQS integration",
    version="1.0.0"
)

# Initialize controller (loads models on startup)
controller = ClassificationController()

# Global variable for SQS worker
worker_thread = None


def run_sqs_worker():
    """Run SQS worker in a separate thread"""
    try:
        # Import here to avoid circular imports
        from sqs_worker import SQSWorker
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create and start worker without signal handlers
        worker = SQSWorker(use_signal_handlers=False)
        loop.run_until_complete(worker.start())
    except Exception as e:
        logger.error(f"SQS Worker error: {str(e)}")
        # Don't crash the entire service if SQS worker fails
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


@app.on_event("startup")
async def startup_event():
    """Start SQS worker on application startup"""
    global worker_thread
    
    logger.info("Starting SQS Worker thread...")
    worker_thread = threading.Thread(target=run_sqs_worker, daemon=True)
    worker_thread.start()
    
    # Give the worker a moment to start
    await asyncio.sleep(2)
    
    if worker_thread.is_alive():
        logger.info("SQS Worker thread started successfully")
    else:
        logger.warning("SQS Worker thread may have failed to start")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down application...")


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Image Classification ML Service",
        "version": "1.0.0",
        "models": ["MobileNetV2", "CLIP"],
        "integration": "SQS",
        "endpoints": {
            "classify": "POST /classify",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    health_status = controller.get_health_status()
    health_status["sqs_worker"] = {
        "status": "running" if worker_thread and worker_thread.is_alive() else "stopped"
    }
    return health_status


@app.post("/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest):
    """
    Direct classification endpoint (for testing/debugging)
    
    Args:
        request: Classification request
        
    Returns:
        Classification results
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)