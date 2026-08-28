import os
import joblib
import pandas as pd
import logging

logger = logging.getLogger(__name__)

from app.core.config import settings

class MLRiskEngine:
    def __init__(self, model_path=None):
        if not model_path:
            model_path = os.path.join(settings.DATA_DIR, "models", "risk_model_v1.joblib")
        
        self.model_path = model_path
        self.is_ready = False
        self.model = None
        self.scaler = None
        self.features = []
        self.threshold = 0.5
        
        self.load_model()
        
    def load_model(self):
        try:
            if os.path.exists(self.model_path):
                artifacts = joblib.load(self.model_path)
                self.model = artifacts["model"]
                self.scaler = artifacts["scaler"]
                self.features = artifacts["features"]
                self.threshold = artifacts["optimal_threshold"]
                self.is_ready = True
                logger.info(f"Loaded ML model from {self.model_path}")
            else:
                logger.warning(f"Model path {self.model_path} not found. Running in fallback mode.")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}. Running in fallback mode.")
            self.is_ready = False
            
    def predict(self, df_with_features: pd.DataFrame) -> dict:
        """
        Predicts risk score using the ML model.
        Returns a probability and the model threshold.
        """
        if not self.is_ready:
            # Failure Safety: Return fallback indicating ML is unavailable
            return {"status": "fallback", "error": "Model not available"}
            
        try:
            # Ensure correct feature ordering
            X = df_with_features[self.features]
            X_scaled = self.scaler.transform(X)
            
            probability = float(self.model.predict_proba(X_scaled)[0, 1])
            is_risky = probability >= self.threshold
            
            return {
                "status": "success",
                "probability": probability,
                "is_risky": is_risky,
                "threshold": self.threshold,
                "model_version": "1.0"
            }
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return {"status": "fallback", "error": str(e)}

risk_engine = MLRiskEngine()
