"""Machine Learning Predictive Layer."""

from __future__ import annotations

import logging
import os
import pickle
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class XGBoostPredictor:
    """
    XGBoost model for predicting price movement probabilities.
    Features should be pre-scaled or handled by the tree model, 
    but we use a StandardScaler for stability.
    """

    def __init__(self, model_path: str = "data/models/xgboost_model.pkl") -> None:
        self.model_path = model_path
        self.model: xgb.XGBClassifier | None = None
        self.scaler: StandardScaler | None = None
        self.is_trained = False
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Train the XGBoost model.
        y should be binary: 1 for UP, 0 for DOWN.
        """
        if len(X) < 100:
            logger.warning("Not enough data to train XGBoost model. Need at least 100 samples.")
            return

        logger.info("Training XGBoost model on %d samples", len(X))
        
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="binary:logistic",
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X_scaled, y)
        self.is_trained = True
        self.save_model()
        logger.info("XGBoost model trained successfully.")

    def predict_probability(self, features: dict[str, float]) -> float:
        """
        Predict the probability of an UP movement.
        Returns float between 0.0 and 1.0.
        If untrained, returns 0.5 (neutral).
        """
        if not self.is_trained or self.model is None or self.scaler is None:
            return 0.5
            
        try:
            # Convert single feature dict to DataFrame
            df = pd.DataFrame([features])
            X_scaled = self.scaler.transform(df)
            
            # Predict probabilities [prob_down, prob_up]
            probs = self.model.predict_proba(X_scaled)
            return float(probs[0][1])  # Return probability of class 1 (UP)
        except Exception as e:
            logger.error("XGBoost prediction failed: %s", e)
            return 0.5

    def save_model(self) -> None:
        """Serialize and save model to disk."""
        if not self.is_trained:
            return
            
        try:
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": self.model, "scaler": self.scaler}, f)
            logger.debug("Saved model to %s", self.model_path)
        except Exception as e:
            logger.error("Failed to save XGBoost model: %s", e)

    def load_model(self) -> None:
        """Load model from disk if it exists."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                    self.model = data.get("model")
                    self.scaler = data.get("scaler")
                    if self.model and self.scaler:
                        self.is_trained = True
                        logger.info("Loaded pre-trained XGBoost model.")
            except Exception as e:
                logger.error("Failed to load XGBoost model: %s", e)
