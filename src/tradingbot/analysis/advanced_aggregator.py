"""Advanced Signal Aggregator Layer."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from tradingbot.analysis.microstructure import MicrostructureAnalyzer
from tradingbot.analysis.ml_model import XGBoostPredictor
from tradingbot.analysis.quantitative import QuantModels
from tradingbot.analysis.sentiment import SentimentAnalyzer
from tradingbot.analysis.technical import TechnicalEngine
from tradingbot.core.events import SignalEvent, SignalSide

logger = logging.getLogger(__name__)


class AdvancedAggregator:
    """
    Combines all analytical layers into a single high-confidence trading signal.
    """

    def __init__(self) -> None:
        self.technical = TechnicalEngine()
        self.microstructure = MicrostructureAnalyzer()
        self.sentiment = SentimentAnalyzer()
        self.ml_predictor = XGBoostPredictor()
        
    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        current_price: float,
    ) -> SignalEvent | None:
        """
        Evaluate the multi-dimensional state of the asset.
        """
        if df.empty or len(df) < 50:
            return None
            
        reasoning = []
        confidence = 50.0 # Start neutral
        
        # 1. Technical Analysis
        df_tech = self.technical.add_all_indicators(df)
        tech_state = self.technical.extract_state(df_tech)
        
        tech_bias = 0.0
        if tech_state.get("trend") in ["STRONG_BULLISH", "BULLISH"]:
            tech_bias += 1.0
            reasoning.append("Technical uptrend")
        elif tech_state.get("trend") in ["STRONG_BEARISH", "BEARISH"]:
            tech_bias -= 1.0
            reasoning.append("Technical downtrend")
            
        if tech_state.get("momentum") == "OVERSOLD":
            tech_bias += 0.5
            reasoning.append("RSI is oversold (Mean reversion potential)")
        elif tech_state.get("momentum") == "OVERBOUGHT":
            tech_bias -= 0.5
            reasoning.append("RSI is overbought (Reversal warning)")
            
        # 2. Quantitative Features
        quant_features = QuantModels.get_statistical_features(df_tech)
        zscore = quant_features.get("zscore", 0.0)
        
        if zscore < -2.0:
            tech_bias += 0.5
            reasoning.append(f"Statistically oversold (Z-score: {zscore:.2f})")
        elif zscore > 2.0:
            tech_bias -= 0.5
            reasoning.append(f"Statistically overbought (Z-score: {zscore:.2f})")
            
        # 3. Microstructure
        micro_features = self.microstructure.evaluate_signals(symbol)
        micro_bias = micro_features.get("microstructure_bias", 0.0)
        if micro_bias > 0.5:
            reasoning.append("Positive orderbook imbalance and funding profile")
        elif micro_bias < -0.5:
            reasoning.append("Negative orderbook imbalance (Sell pressure)")
            
        # 4. Sentiment / Macro
        macro_bias = self.sentiment.evaluate_macro_bias()
        if macro_bias > 0.2:
            reasoning.append(f"Positive macro/news sentiment ({macro_bias:.2f})")
        elif macro_bias < -0.2:
            reasoning.append(f"Negative macro/news sentiment ({macro_bias:.2f})")
            
        # 5. ML Predictive Layer
        # Prepare feature vector for ML
        ml_features = {
            "rsi": tech_state.get("rsi", 50.0),
            "macd": tech_state.get("macd", 0.0),
            "atr": tech_state.get("atr", 0.0),
            "zscore": zscore,
            "ob_imbalance": micro_features.get("ob_imbalance", 0.0),
            "funding_rate": micro_features.get("funding_rate", 0.0),
            "sentiment": macro_bias,
        }
        
        prob_up = self.ml_predictor.predict_probability(ml_features)
        ml_bias = (prob_up - 0.5) * 2.0  # Scale 0-1 to -1 to 1
        
        if prob_up > 0.65:
            reasoning.append(f"ML Model predicts UP ({prob_up*100:.1f}%)")
        elif prob_up < 0.35:
            reasoning.append(f"ML Model predicts DOWN ({(1-prob_up)*100:.1f}%)")
            
        # Combine Biases
        # Weighted sum of biases: Tech (40%), Micro (20%), Macro (10%), ML (30%)
        total_score = (tech_bias * 0.4) + (micro_bias * 0.2) + (macro_bias * 0.1) + (ml_bias * 0.3)
        
        # Determine Signal
        side = SignalSide.HOLD
        strength = abs(total_score) / 2.0  # Normalize roughly to 0-1
        strength = min(1.0, max(0.0, strength))
        
        confidence = 50.0 + (total_score * 25.0)  # Map -2 to 2 into 0 to 100%
        confidence = min(100.0, max(0.0, confidence))
        
        if total_score > 0.7:
            side = SignalSide.BUY
        elif total_score < -0.7:
            side = SignalSide.SELL
            
        if side == SignalSide.HOLD:
            return None  # No strong signal
            
        # Risk / Targets (Simple ATR based)
        atr = tech_state["atr"]
        stop_loss = current_price - (atr * 2.0) if side == SignalSide.BUY else current_price + (atr * 2.0)
        take_profit = current_price + (atr * 3.0) if side == SignalSide.BUY else current_price - (atr * 3.0)

        bb_high = tech_state.get("bb_high", 0.0)
        bb_low = tech_state.get("bb_low", 0.0)
        bb_width = bb_high - bb_low

        # Build Event
        return SignalEvent(
            symbol=symbol,
            side=side,
            strength=strength,
            strategy_name="AdvancedAggregator",
            reason=reasoning[0] if reasoning else "Algorithm consensus",
            confidence=confidence,
            trend="BULLISH" if tech_bias > 0 else "BEARISH",
            momentum="STRONG" if abs(tech_bias) > 0.5 else "WEAK",
            volatility="EXPANDING" if bb_width > current_price * 0.05 else "COMPRESSING",
            sentiment=macro_bias * 100,
            risk_score=(1.0 - strength) * 100,
            suggested_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            metadata=ml_features
        )
