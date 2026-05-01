"""Prometheus metrics — exposes trading bot metrics for monitoring."""

from __future__ import annotations

import logging

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

logger = logging.getLogger(__name__)

# --- Bot Info ---
bot_info = Info("tradingbot", "Trading bot information")

# --- Trade Metrics ---
trades_total = Counter(
    "tradingbot_trades_total",
    "Total number of trades executed",
    ["symbol", "side"],
)

trades_value = Counter(
    "tradingbot_trades_value_total",
    "Total value of trades executed",
    ["symbol", "side"],
)

# --- Order Metrics ---
orders_submitted = Counter(
    "tradingbot_orders_submitted_total",
    "Total orders submitted",
)

orders_filled = Counter(
    "tradingbot_orders_filled_total",
    "Total orders filled",
)

orders_failed = Counter(
    "tradingbot_orders_failed_total",
    "Total orders failed",
)

# --- Portfolio Metrics ---
portfolio_value = Gauge(
    "tradingbot_portfolio_value",
    "Current portfolio value in USD",
)

portfolio_cash = Gauge(
    "tradingbot_portfolio_cash",
    "Current cash balance in USD",
)

portfolio_pnl = Gauge(
    "tradingbot_portfolio_pnl",
    "Current P&L in USD",
    ["type"],  # realized, unrealized
)

open_positions = Gauge(
    "tradingbot_open_positions",
    "Number of open positions",
)

# --- Signal Metrics ---
signals_generated = Counter(
    "tradingbot_signals_generated_total",
    "Total signals generated",
    ["strategy", "side"],
)

signals_approved = Counter(
    "tradingbot_signals_approved_total",
    "Signals approved by risk manager",
)

signals_rejected = Counter(
    "tradingbot_signals_rejected_total",
    "Signals rejected by risk manager",
)

# --- System Metrics ---
event_bus_events = Counter(
    "tradingbot_events_total",
    "Total events processed by event bus",
    ["event_type"],
)

order_latency = Histogram(
    "tradingbot_order_latency_seconds",
    "Order execution latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

circuit_breaker_trips = Counter(
    "tradingbot_circuit_breaker_trips_total",
    "Number of circuit breaker activations",
)


def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus metrics HTTP server."""
    try:
        start_http_server(port)
        logger.info("Prometheus metrics server started on port %d", port)
    except Exception as exc:
        logger.error("Failed to start metrics server: %s", exc)


def update_bot_info(name: str, mode: str, version: str) -> None:
    """Update bot info metric."""
    bot_info.info({"name": name, "mode": mode, "version": version})
