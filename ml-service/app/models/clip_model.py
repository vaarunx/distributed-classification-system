from transformers import CLIPProcessor, CLIPModel
from PIL import Image
from typing import List, Dict
import torch
import logging
from .base_model import BaseClassificationModel

logger = logging.getLogger(__name__)


class ClipModel(BaseClassificationModel):
    """CLIP model for custom label classification"""
    
    def __init__(self):
        super().__init__()
        self.model_name = "openai/clip-vit-base-patch32"
        self.processor = None
    
    def load_model(self):
        """Load CLIP model and processor"""
        try:
            logger.info(f"Loading {self.model_name}...")
            self.model = CLIPModel.from_pretrained(self.model_name)
            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            logger.info(f"{self.model_name} loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {str(e)}")
            raise
    
    def predict(self, image: Image.Image, custom_labels: List[str], top_k: int = 5, **kwargs) -> List[Dict[str, float]]:
        """
        Classify image using CLIP with custom labels
        
        Args:
            image: PIL Image
            custom_labels: List of text labels to classify against
            top_k: Number of top predictions to return
            
        Returns:
            List of predictions with label and score
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        if not custom_labels:
            raise ValueError("custom_labels must be provided for CLIP classification")
        
        try:
            # Prepare text prompts
            text_inputs = [f"a photo of {label}" for label in custom_labels]
            
            # Process inputs
            inputs = self.processor(
                text=text_inputs,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)
            
            # Format results
            results = []
            for i, label in enumerate(custom_labels):
                results.append({
                    "label": label,
                    "score": float(probs[0][i])
                })
            
            # Sort by score and return top_k
            results = sorted(results, key=lambda x: x["score"], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"CLIP prediction failed: {str(e)}")
            raise