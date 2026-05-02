"""Tests for ML model, sentiment analysis, and API routes — coverage boosters."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pandas as pd
import pytest

from tradingbot.core.events import (
    EventType, MarketDataEvent, SignalEvent, SignalSide,
    FillEvent, OrderEvent, OrderType, AlertEvent, AlertLevel,
    HeartbeatEvent, ErrorEvent, PortfolioEvent, OrderBookEvent,
    FundingRateEvent, OrderStatus
)


# ============================================================
# ML Model Tests
# ============================================================

class TestXGBoostPredictor:
    """Tests for XGBoostPredictor."""

    def test_untrained_returns_neutral(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            assert pred.is_trained is False
            result = pred.predict_probability({"rsi": 50, "macd": 0})
            assert result == 0.5

    def test_train_and_predict(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            
            rng = np.random.RandomState(42)
            X = pd.DataFrame({
                "rsi": rng.uniform(20, 80, 200),
                "macd": rng.randn(200),
                "atr": rng.uniform(0.01, 0.05, 200),
            })
            y = pd.Series((rng.rand(200) > 0.5).astype(int))
            
            pred.train(X, y)
            assert pred.is_trained is True
            
            prob = pred.predict_probability({"rsi": 60, "macd": 0.5, "atr": 0.02})
            assert 0.0 <= prob <= 1.0

    def test_train_too_few_samples(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            
            X = pd.DataFrame({"rsi": [50, 60], "macd": [0.1, -0.1]})
            y = pd.Series([1, 0])
            pred.train(X, y)
            assert pred.is_trained is False  # Too few samples

    def test_save_and_load_model(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            
            rng = np.random.RandomState(42)
            X = pd.DataFrame({
                "rsi": rng.uniform(20, 80, 200),
                "macd": rng.randn(200),
            })
            y = pd.Series((rng.rand(200) > 0.5).astype(int))
            pred.train(X, y)
            
            # Load in a new instance
            pred2 = XGBoostPredictor(model_path=model_path)
            assert pred2.is_trained is True
            prob = pred2.predict_probability({"rsi": 50, "macd": 0})
            assert 0.0 <= prob <= 1.0

    def test_predict_with_error_returns_neutral(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            pred.is_trained = True
            pred.model = MagicMock()
            pred.scaler = MagicMock()
            pred.scaler.transform.side_effect = Exception("boom")
            result = pred.predict_probability({"rsi": 50})
            assert result == 0.5

    def test_save_untrained_noop(self):
        from tradingbot.analysis.ml_model import XGBoostPredictor
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            pred = XGBoostPredictor(model_path=model_path)
            pred.save_model()
            assert not os.path.exists(model_path)


# ============================================================
# Sentiment Analysis Tests
# ============================================================

class TestSentimentAnalyzer:
    """Tests for SentimentAnalyzer."""

    def test_analyze_positive_text(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        result = sa.analyze_text("Bitcoin soars to all-time highs! Amazing growth!")
        assert result.compound > 0

    def test_analyze_negative_text(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        result = sa.analyze_text("Market crash! Terrible losses everywhere!")
        assert result.compound < 0

    def test_aggregate_sentiment(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        sa.analyze_text("Great news!")
        sa.analyze_text("Wonderful performance!")
        agg = sa.get_aggregate_sentiment(window=5)
        assert agg > 0

    def test_aggregate_no_data(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        assert sa.get_aggregate_sentiment() == 0.0

    def test_evaluate_macro_bias(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        bias = sa.evaluate_macro_bias()
        assert bias == 0.0  # No data

    def test_sentiment_result_fields(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer, SentimentResult
        sa = SentimentAnalyzer()
        result = sa.analyze_text("Neutral statement about bitcoin")
        assert isinstance(result, SentimentResult)
        assert result.text == "Neutral statement about bitcoin"
        assert result.source == "news"

    def test_sentiment_trims_to_100(self):
        from tradingbot.analysis.sentiment import SentimentAnalyzer
        sa = SentimentAnalyzer()
        for i in range(110):
            sa.analyze_text(f"Text {i}")
        assert len(sa.recent_sentiments) == 100


# ============================================================
# Advanced Aggregator Deep Tests
# ============================================================

class TestAggregatorDeep:
    """Deep coverage tests for AdvancedAggregator."""

    def _make_df(self, n=200, seed=42):
        rng = np.random.RandomState(seed)
        closes = 50000 + np.cumsum(rng.randn(n) * 100)
        return pd.DataFrame({
            "open": closes - 50,
            "high": closes + 100,
            "low": closes - 100,
            "close": closes,
            "volume": rng.uniform(100, 50000, n)
        })

    def test_generate_signal_too_few_rows(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator()
        df = self._make_df(n=10)
        result = agg.generate_signal("BTC/USDT", df, 50000.0)
        assert result is None

    def test_generate_signal_empty_df(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator()
        df = pd.DataFrame()
        result = agg.generate_signal("BTC/USDT", df, 50000.0)
        assert result is None

    def test_generate_signal_returns_event_or_none(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator(signal_threshold=0.01)
        df = self._make_df(n=200, seed=100)
        result = agg.generate_signal("BTC/USDT", df, float(df["close"].iloc[-1]))
        if result is not None:
            assert result.symbol == "BTC/USDT"
            assert result.side in (SignalSide.BUY, SignalSide.SELL)
            assert 0.0 <= result.strength <= 1.0
            assert len(result.reasoning) > 0

    def test_signal_has_stop_loss_and_take_profit(self):
        from tradingbot.analysis.advanced_aggregator import AdvancedAggregator
        agg = AdvancedAggregator(signal_threshold=0.01)
        df = self._make_df(n=200, seed=55)
        result = agg.generate_signal("BTC/USDT", df, float(df["close"].iloc[-1]))
        if result is not None:
            assert result.stop_loss is not None
            assert result.take_profit is not None


# ============================================================
# Event Model Tests
# ============================================================

class TestEventModels:
    """Additional event model coverage."""

    def test_orderbook_event(self):
        e = OrderBookEvent(symbol="BTC/USDT", exchange="binance", bids=[[100, 1]], asks=[[101, 1]])
        assert e.event_type == EventType.ORDERBOOK
        assert e.symbol == "BTC/USDT"

    def test_funding_rate_event(self):
        e = FundingRateEvent(symbol="BTC/USDT", exchange="binance", funding_rate=0.01)
        assert e.event_type == EventType.FUNDING_RATE
        assert e.funding_rate == 0.01

    def test_portfolio_event(self):
        e = PortfolioEvent(total_value=100000, cash=50000)
        assert e.event_type == EventType.PORTFOLIO
        assert e.total_value == 100000

    def test_error_event(self):
        e = ErrorEvent(error_type="RuntimeError", message="test error")
        assert e.event_type == EventType.ERROR

    def test_heartbeat_event(self):
        e = HeartbeatEvent(component="engine", status="healthy")
        assert e.event_type == EventType.HEARTBEAT

    def test_signal_event_invalid_strength(self):
        with pytest.raises(ValueError):
            SignalEvent(symbol="BTC/USDT", side=SignalSide.BUY, strength=2.0, strategy_name="x", reason="x")

    def test_order_status_values(self):
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.CANCELLED == "cancelled"
