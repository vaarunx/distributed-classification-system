from abc import ABC, abstractmethod
from PIL import Image
from typing import List, Dict


class BaseClassificationModel(ABC):
    """Abstract base class for all classification models"""
    
    def __init__(self):
        self.model = None
        self.model_name = ""
    
    @abstractmethod
    def load_model(self):
        """Load the model into memory"""
        pass
    
    @abstractmethod
    def predict(self, image: Image.Image, **kwargs) -> List[Dict[str, float]]:
        """
        Run inference on an image
        
        Args:
            image: PIL Image object
            **kwargs: Additional parameters specific to model type
            
        Returns:
            List of dicts with 'label' and 'score' keys
        """
        pass
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None