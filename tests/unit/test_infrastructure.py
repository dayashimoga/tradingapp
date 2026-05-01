"""Unit tests for normalizer, logger, metrics, alerts, and persistence."""

from __future__ import annotations

import pytest

from tradingbot.data.normalizer import DataNormalizer
from tradingbot.monitoring.alerts.base import AlertProvider
from tradingbot.monitoring.logger import get_logger, setup_logging


class TestDataNormalizer:
    def test_from_ohlcv_list(self):
        ohlcv = [1700000000000, 100.0, 105.0, 95.0, 102.0, 5000.0]
        event = DataNormalizer.from_ohlcv_list("BTC/USDT", ohlcv, "binance", "1h")
        assert event.symbol == "BTC/USDT"
        assert event.open == 100.0
        assert event.high == 105.0
        assert event.low == 95.0
        assert event.close == 102.0
        assert event.volume == 5000.0
        assert event.exchange == "binance"

    def test_from_ohlcv_short_list(self):
        with pytest.raises(ValueError, match="at least 6"):
            DataNormalizer.from_ohlcv_list("BTC/USDT", [1, 2, 3])

    def test_from_ticker(self):
        ticker = {"last": 50000.0, "high": 51000.0, "low": 49000.0,
                  "open": 49500.0, "baseVolume": 1000.0}
        event = DataNormalizer.from_ticker("BTC/USDT", ticker, "kraken")
        assert event.close == 50000.0
        assert event.volume == 1000.0

    def test_from_ticker_missing_fields(self):
        ticker = {"last": 100.0}
        event = DataNormalizer.from_ticker("X/Y", ticker)
        assert event.close == 100.0
        assert event.open == 100.0

    def test_from_ticker_none_values(self):
        ticker = {"last": 100.0, "high": None, "baseVolume": None}
        event = DataNormalizer.from_ticker("X/Y", ticker)
        assert event.close == 100.0
        assert event.high == 100.0
        assert event.volume == 0.0

    def test_from_alpaca_bar(self):
        bar = {"o": 150.0, "h": 155.0, "l": 148.0, "c": 152.0, "v": 10000}
        event = DataNormalizer.from_alpaca_bar("AAPL", bar)
        assert event.symbol == "AAPL"
        assert event.open == 150.0
        assert event.close == 152.0
        assert event.exchange == "alpaca"

    def test_from_alpaca_empty_bar(self):
        event = DataNormalizer.from_alpaca_bar("AAPL", {})
        assert event.close == 0.0


class TestLogger:
    def test_setup_json(self):
        setup_logging(level="DEBUG", log_format="json")

    def test_setup_console(self):
        setup_logging(level="INFO", log_format="console")

    def test_get_logger(self):
        log = get_logger("test")
        assert log is not None


class TestAlertBase:
    def test_abstract(self):
        with pytest.raises(TypeError):
            AlertProvider()  # type: ignore


class TestDatabaseModels:
    def test_trade_record_columns(self):
        from tradingbot.persistence.models import TradeRecord
        assert TradeRecord.__tablename__ == "trades"

    def test_position_record(self):
        from tradingbot.persistence.models import PositionRecord
        assert PositionRecord.__tablename__ == "positions"

    def test_portfolio_history(self):
        from tradingbot.persistence.models import PortfolioHistory
        assert PortfolioHistory.__tablename__ == "portfolio_history"

    def test_alert_record(self):
        from tradingbot.persistence.models import AlertRecord
        assert AlertRecord.__tablename__ == "alerts"


class TestDatabase:
    @pytest.mark.asyncio
    async def test_initialize_and_close(self):
        from tradingbot.persistence.database import Database
        db = Database(url="sqlite+aiosqlite:///:memory:")
        await db.initialize()
        session = await db.get_session()
        assert session is not None
        await session.close()
        await db.close()


class TestBrokerError:
    def test_broker_error(self):
        from tradingbot.execution.brokers.base import BrokerError
        err = BrokerError("test error", broker="paper", order_id="123")
        assert str(err) == "test error"
        assert err.broker == "paper"
        assert err.order_id == "123"
