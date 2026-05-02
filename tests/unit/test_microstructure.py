import pytest
import pandas as pd
import numpy as np

from tradingbot.analysis.microstructure import MicrostructureAnalyzer
from tradingbot.analysis.quantitative import QuantModels
from tradingbot.core.events import OrderBookEvent, FundingRateEvent

def test_microstructure_analyzer():
    analyzer = MicrostructureAnalyzer()
    
    # Test Orderbook Processing
    bids = [[100.0, 1.0], [99.0, 2.0], [98.0, 5.0]]
    asks = [[101.0, 1.0], [102.0, 3.0], [103.0, 1.0]]
    
    ob_event = OrderBookEvent(symbol="BTC/USDT", exchange="binance", bids=bids, asks=asks)
    
    state = analyzer.process_orderbook(ob_event)
    assert state.symbol == "BTC/USDT"
    
    # Mid price = 100.5, spread = 1.0
    assert abs(state.spread_pct - (1.0 / 100.5 * 100)) < 0.01
    
    # Bid vol = 8.0, Ask vol = 5.0, Total = 13.0
    # Imbalance = (8.0 - 5.0) / 13.0 = 3.0 / 13.0
    assert abs(state.imbalance - (3.0 / 13.0)) < 0.01

def test_quant_models():
    # Test Z-score
    series = pd.Series([10, 10, 10, 10, 20])
    zscore = QuantModels.calculate_zscore(series, window=5)
    assert len(zscore) == 5
    assert pd.isna(zscore.iloc[0])
    assert zscore.iloc[-1] > 0  # 20 is above mean
    
    # Test regime detection returns valid series of 0s and 1s
    rng = np.random.RandomState(42)
    returns = pd.Series(rng.normal(0, 0.001, 500))  # Long low-vol series
    # Inject extreme high vol at the end
    returns.iloc[-50:] = rng.normal(0, 0.5, 50)
    
    regime = QuantModels.detect_regime(returns, window=20)
    assert len(regime) == 500
    assert set(regime.dropna().unique()).issubset({0, 1})
    # At least some high-vol detected in the tail
    assert regime.iloc[-50:].sum() > 0
