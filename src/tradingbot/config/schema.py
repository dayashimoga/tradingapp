"""Configuration schema — Pydantic models for validated configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""

    enabled: bool = True
    volatility_threshold: float = Field(default=3.0, gt=0)
    cooldown_minutes: int = Field(default=30, gt=0)


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_daily_loss: float = Field(default=500.0, gt=0)
    max_position_size: float = Field(default=0.05, gt=0, le=1.0)
    max_total_exposure: float = Field(default=0.30, gt=0, le=1.0)
    stop_loss_pct: float = Field(default=0.02, gt=0, lt=1.0)
    take_profit_pct: float = Field(default=0.05, gt=0, lt=1.0)
    max_open_positions: int = Field(default=5, gt=0)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)


class StrategyConfig(BaseModel):
    """Strategy configuration."""

    name: str = "sma_crossover"
    params: dict[str, Any] = Field(default_factory=dict)


class DataConfig(BaseModel):
    """Market data configuration."""

    provider: str = "ccxt"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "1m"
    history_bars: int = Field(default=200, gt=0)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one symbol must be configured")
        return v

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        valid = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
        if v not in valid:
            raise ValueError(f"Invalid timeframe '{v}'. Must be one of: {valid}")
        return v


class PaperTradingConfig(BaseModel):
    """Paper trading simulation settings."""

    initial_balance: float = Field(default=100000.0, gt=0)
    simulated_slippage: float = Field(default=0.0005, ge=0)
    simulated_latency_ms: int = Field(default=50, ge=0)


class ExecutionConfig(BaseModel):
    """Execution layer configuration."""

    retry_attempts: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, gt=0)
    order_timeout: int = Field(default=30, gt=0)
    slippage_tolerance: float = Field(default=0.001, ge=0)
    paper_trading: PaperTradingConfig = Field(default_factory=PaperTradingConfig)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite+aiosqlite:///./tradingbot.db"
    echo: bool = False


class PrometheusConfig(BaseModel):
    """Prometheus metrics configuration."""

    enabled: bool = True
    port: int = Field(default=9090, gt=0, lt=65536)


class TelegramConfig(BaseModel):
    """Telegram alert configuration."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class EmailConfig(BaseModel):
    """Email alert configuration."""

    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    recipient: str = ""


class AlertsConfig(BaseModel):
    """Alerts configuration."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    log_format: str = "json"

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        if v not in {"json", "console"}:
            raise ValueError(f"Invalid log_format '{v}'. Must be 'json' or 'console'")
        return v


class BotConfig(BaseModel):
    """Top-level bot configuration."""

    name: str = "TradingBot"
    mode: str = "paper"
    log_level: str = "INFO"
    heartbeat_interval: int = Field(default=30, gt=0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in {"paper", "live"}:
            raise ValueError(f"Invalid mode '{v}'. Must be 'paper' or 'live'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"Invalid log_level '{v}'. Must be one of: {valid}")
        return v.upper()


class TradingBotConfig(BaseModel):
    """Root configuration model — validates the entire config tree."""

    bot: BotConfig = Field(default_factory=BotConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
