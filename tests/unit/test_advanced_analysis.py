"""Unit tests for the Advanced Analysis Engine (Phase 1)."""

import pytest
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime, timezone, timedelta

from tradingbot.analysis.technical import TechnicalEngine
from tradingbot.analysis.timeframe import TimeframeAggregator
from tradingbot.core.events import MarketDataEvent, SignalEvent, SignalSide

@pytest.fixture
def sample_ohlcv():
    """Generate 300 rows of random OHLCV data."""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=300, freq='1min')
    df = pd.DataFrame({
        'time': dates,
        'open': np.random.normal(100, 2, 300),
        'high': np.random.normal(105, 2, 300),
        'low': np.random.normal(95, 2, 300),
        'close': np.random.normal(101, 2, 300),
        'volume': np.random.normal(1000, 200, 300)
    })
    df.set_index('time', inplace=True)
    return df

def test_technical_engine_add_all_indicators(sample_ohlcv):
    df = TechnicalEngine.add_all_indicators(sample_ohlcv)
    
    # Check that key columns exist
    assert 'ema_50' in df.columns
    assert 'rsi_14' in df.columns
    assert 'macd_hist' in df.columns
    assert 'bb_width' in df.columns
    assert 'volatility_regime' in df.columns
    
    # Check that they are not all NaNs (the first few rows will be NaN, but later rows should have data)
    assert not pd.isna(df['ema_50'].iloc[-1])
    assert not pd.isna(df['rsi_14'].iloc[-1])

def test_technical_engine_extract_state(sample_ohlcv):
    df = TechnicalEngine.add_all_indicators(sample_ohlcv)
    state = TechnicalEngine.extract_state(df)
    
    assert "trend" in state
    assert "momentum" in state
    assert "volatility" in state
    assert "rsi" in state
    
    assert isinstance(state['rsi'], float)
    assert isinstance(state['trend'], str)

@pytest.mark.asyncio
async def test_timeframe_aggregator():
    aggregator = TimeframeAggregator()
    
    # Push 100 1-minute ticks
    base_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(100):
        dt = base_time + timedelta(minutes=i)
        event = MarketDataEvent(
            source="test",
            symbol="BTC/USDT",
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0 + (i * 0.1), # Slight upward trend
            volume=10.0,
            timestamp=dt
        )
        await aggregator.on_market_data(event)
        
    df_5m = await aggregator.get_dataframe("BTC/USDT", "5min")
    
    # 100 minutes = 20 5-minute candles
    assert len(df_5m) == 20
    assert "open" in df_5m.columns
    assert "close" in df_5m.columns
    
    # First 5m candle close should be 100.0 + 4 * 0.1 = 100.4
    assert df_5m['close'].iloc[0] == pytest.approx(100.4)
    
    # Test multi-timeframe state
    state = await aggregator.get_multi_timeframe_state("BTC/USDT")
    assert "5min" in state
    assert state["5min"] in ["BULLISH", "BEARISH", "NEUTRAL"]

def test_signal_event_advanced_payload():
    signal = SignalEvent(
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        strength=0.85,
        strategy_name="AdvancedAggregator",
        confidence=85.0,
        trend="BULLISH",
        momentum="STRONG",
        volatility="EXPANDING",
        sentiment=60.0,
        risk_score=30.0,
        suggested_price=50000.0,
        stop_loss=48000.0,
        take_profit=56000.0,
        reasoning=["Trend aligned", "MACD cross"]
    )
    
    assert signal.confidence == 85.0
    assert signal.trend == "BULLISH"
    assert signal.reasoning == ["Trend aligned", "MACD cross"]
