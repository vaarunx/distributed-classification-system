from transformers import pipeline
from PIL import Image
from typing import List, Dict
import logging
from .base_model import BaseClassificationModel

logger = logging.getLogger(__name__)


class MobileNetModel(BaseClassificationModel):
    """MobileNetV2 model for standard ImageNet classification"""
    
    def __init__(self):
        super().__init__()
        self.model_name = "google/mobilenet_v2_1.0_224"
    
    def load_model(self):
        """Load MobileNetV2 model"""
        try:
            logger.info(f"Loading {self.model_name}...")
            self.model = pipeline(
                "image-classification",
                model=self.model_name,
                device=-1  # CPU only
            )
            logger.info(f"{self.model_name} loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {str(e)}")
            raise
    
    def predict(self, image: Image.Image, top_k: int = 5, **kwargs) -> List[Dict[str, float]]:
        """
        Classify image using MobileNetV2
        
        Args:
            image: PIL Image
            top_k: Number of top predictions to return
            
        Returns:
            List of predictions with label and score
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        try:
            results = self.model(image, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            raise