import pytest
import pandas as pd
import numpy as np

from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
from tradingbot.core.events import SignalSide

def test_advanced_aggregator():
    aggregator = AdvancedAggregator()
    
    # Create fake OHLCV data
    dates = pd.date_range("2023-01-01", periods=200, freq="1min")
    df = pd.DataFrame({
        "open": np.linspace(100, 110, 200),
        "high": np.linspace(101, 111, 200),
        "low": np.linspace(99, 109, 200),
        "close": np.linspace(100.5, 110.5, 200),
        "volume": np.random.uniform(10, 100, 200)
    }, index=dates)
    
    # Mock ML predictor so we don't need a real trained model
    aggregator.ml_predictor.is_trained = True
    aggregator.ml_predictor.predict_probability = lambda features: 0.95  # Strong UP
    
    # Mock Sentiment
    aggregator.sentiment.evaluate_macro_bias = lambda: 1.0  # Max positive macro
    
    # Mock Microstructure
    aggregator.microstructure.evaluate_signals = lambda symbol: {"microstructure_bias": 1.0}
    
    signal = aggregator.generate_signal("BTC/USDT", df, current_price=110.5)
    
    assert signal is not None
    assert signal.symbol == "BTC/USDT"
    # Should be BUY because of strong ML and MACRO bias and general uptrend in df
    assert signal.side == SignalSide.BUY
    assert signal.confidence > 50.0
    assert signal.stop_loss is not None
    assert signal.take_profit is not None
    assert signal.reasoning is not None
    assert len(signal.reasoning) > 0
