"""Advanced Multi-Dimensional Strategy using the Advanced Aggregator."""

from __future__ import annotations

import logging
from typing import Any

from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
from tradingbot.core.events import MarketDataEvent, SignalEvent
from tradingbot.strategy.base import Strategy
from tradingbot.strategy.registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy("advanced")
class AdvancedStrategy(Strategy):
    """
    Advanced Strategy using Technicals, Microstructure, Sentiment, and ML.
    """

    def __init__(self, name: str = "advanced", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self.aggregator = AdvancedAggregator()
        self._last_state: dict[str, Any] = {}
        from collections import deque
        self._window = int(kwargs.get("params", {}).get("window", 200))
        self._history: deque[MarketDataEvent] = deque(maxlen=self._window + 50)

    def calculate_signal(self, market_data: MarketDataEvent) -> SignalEvent | None:
        """
        Feed market data into the aggregator and evaluate signal.
        """
        import pandas as pd
        
        self._history.append(market_data)
        
        if len(self._history) < self._window:
            self._is_warmed_up = False
            self._last_state = {"status": f"Warming up ({len(self._history)}/{self._window})"}
            return None
            
        self._is_warmed_up = True
        
        # Build dataframe
        df_data = []
        dates = []
        for event in self._history:
            df_data.append({
                "open": event.open,
                "high": event.high,
                "low": event.low,
                "close": event.close,
                "volume": event.volume
            })
            dates.append(event.timestamp)
            
        df = pd.DataFrame(df_data, index=dates)
        
        # Use Aggregator
        signal = self.aggregator.generate_signal(market_data.symbol, df, market_data.close)
        
        # Save state for UI
        # The aggregator already ran technicals and ml predictor inside, 
        # but to extract the scores for UI, we can peek at the signal metadata or re-extract slightly.
        # Actually, if signal is generated, it has metadata. 
        # But if NO signal is generated, we still want to show the current score!
        
        # Let's extract current metrics directly so they always update
        tech_df = self.aggregator.technical.add_all_indicators(df.copy())
        tech_state = self.aggregator.technical.extract_state(tech_df)
        micro_features = self.aggregator.microstructure.evaluate_signals(market_data.symbol)
        macro_bias = self.aggregator.sentiment.evaluate_macro_bias()
        
        # Construct feature vector to get ML prob
        zscore = tech_df["close_zscore"].iloc[-1] if "close_zscore" in tech_df.columns else 0.0
        ml_features = {
            "rsi": tech_state.get("rsi", 50.0),
            "macd": tech_state.get("macd", 0.0),
            "atr": tech_state.get("atr", 0.0),
            "zscore": float(zscore),
            "ob_imbalance": micro_features.get("ob_imbalance", 0.0),
            "funding_rate": micro_features.get("funding_rate", 0.0),
            "sentiment": macro_bias,
        }
        
        prob_up = 0.5
        if self.aggregator.ml_predictor.is_trained:
            prob_up = self.aggregator.ml_predictor.predict_probability(ml_features)
            
        # Re-create total score math to show in UI
        tech_bias = 0.0
        if tech_state.get("trend") in ["STRONG_BULLISH", "BULLISH"]: tech_bias += 1.0
        elif tech_state.get("trend") in ["STRONG_BEARISH", "BEARISH"]: tech_bias -= 1.0
        
        if zscore < -2.0: tech_bias += 0.5
        elif zscore > 2.0: tech_bias -= 0.5
        
        micro_bias = micro_features.get("microstructure_bias", 0.0)
        ml_bias = (prob_up - 0.5) * 2.0
        
        total_score = (tech_bias * 0.4) + (micro_bias * 0.2) + (macro_bias * 0.1) + (ml_bias * 0.3)
        confidence = 50.0 + (total_score * 25.0)
        confidence = min(100.0, max(0.0, confidence))
        
        self._last_state = {
            "status": "Active",
            "total_score": round(total_score, 2),
            "confidence": round(confidence, 1),
            "ml_prob": round(prob_up * 100, 1),
            "micro_bias": round(micro_bias, 2),
            "macro_bias": round(macro_bias, 2),
            "trend": tech_state.get("trend", "UNKNOWN"),
        }
        
        return signal

    def get_state(self) -> dict[str, Any]:
        """Get current advanced state for dashboard."""
        return {
            **super().get_state(),
            "type": "Multi-Dimensional Consensus",
            **self._last_state,
        }

    def reset(self) -> None:
        """Reset strategy state."""
        self._last_state.clear()
        self._is_warmed_up = False
