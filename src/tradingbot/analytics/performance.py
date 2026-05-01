"""Performance analytics — computes portfolio and strategy metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PerformanceMetrics:
    """Container for all computed performance metrics."""

    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration_hours: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    daily_returns: list[float] = field(default_factory=list)


class PerformanceCalculator:
    """Computes trading performance metrics from trade and portfolio data."""

    @staticmethod
    def calculate_total_return(current_value: float, initial_capital: float) -> float:
        """Calculate total return percentage."""
        if initial_capital <= 0:
            return 0.0
        return ((current_value - initial_capital) / initial_capital) * 100

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[float], risk_free_rate: float = 0.0, annualization: float = 252.0
    ) -> float:
        """Calculate annualized Sharpe ratio from a list of periodic returns."""
        if len(returns) < 2:
            return 0.0
        excess = [r - risk_free_rate / annualization for r in returns]
        mean_excess = sum(excess) / len(excess)
        variance = sum((r - mean_excess) ** 2 for r in excess) / (len(excess) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return 0.0
        return (mean_excess / std) * math.sqrt(annualization)

    @staticmethod
    def calculate_sortino_ratio(
        returns: list[float], risk_free_rate: float = 0.0, annualization: float = 252.0
    ) -> float:
        """Calculate annualized Sortino ratio (penalizes only downside volatility)."""
        if len(returns) < 2:
            return 0.0
        excess = [r - risk_free_rate / annualization for r in returns]
        mean_excess = sum(excess) / len(excess)
        downside = [r for r in excess if r < 0]
        if not downside:
            return 0.0 if mean_excess <= 0 else float("inf")
        downside_variance = sum(r**2 for r in downside) / len(downside)
        downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0
        if downside_std == 0:
            return 0.0
        return (mean_excess / downside_std) * math.sqrt(annualization)

    @staticmethod
    def calculate_max_drawdown(equity_curve: list[float]) -> float:
        """Calculate maximum drawdown percentage from an equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)
        return max_dd * 100

    @staticmethod
    def calculate_drawdown_series(equity_curve: list[float]) -> list[float]:
        """Calculate drawdown series from equity curve (for charting)."""
        if not equity_curve:
            return []
        peak = equity_curve[0]
        series = []
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = ((peak - value) / peak * 100) if peak > 0 else 0.0
            series.append(-dd)
        return series

    @staticmethod
    def compute_from_trades(
        trades: list[dict],
        portfolio_snapshots: list[dict],
        initial_capital: float,
        current_value: float,
    ) -> PerformanceMetrics:
        """
        Compute all performance metrics from trade data and portfolio history.

        Args:
            trades: List of trade dicts with keys: side, pnl, timestamp
            portfolio_snapshots: List of dicts with key: total_value
            initial_capital: Starting capital
            current_value: Current portfolio value
        """
        metrics = PerformanceMetrics()
        metrics.total_return_pct = PerformanceCalculator.calculate_total_return(
            current_value, initial_capital
        )
        metrics.total_trades = len(trades)

        # Trade analysis
        pnls = [t.get("pnl", 0.0) for t in trades if t.get("side", "").lower() == "sell"]
        if pnls:
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p < 0]
            metrics.winning_trades = len(winning)
            metrics.losing_trades = len(losing)
            metrics.gross_profit = sum(winning)
            metrics.gross_loss = abs(sum(losing))
            metrics.win_rate = len(winning) / len(pnls) if pnls else 0.0
            metrics.profit_factor = (
                metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else float("inf")
            )
            metrics.best_trade = max(pnls) if pnls else 0.0
            metrics.worst_trade = min(pnls) if pnls else 0.0

        # Portfolio returns
        values = [s.get("total_value", 0) for s in portfolio_snapshots if s.get("total_value", 0) > 0]
        if len(values) >= 2:
            daily_returns = []
            for i in range(1, len(values)):
                ret = (values[i] - values[i - 1]) / values[i - 1] if values[i - 1] > 0 else 0.0
                daily_returns.append(ret)
            metrics.daily_returns = daily_returns
            metrics.sharpe_ratio = PerformanceCalculator.calculate_sharpe_ratio(daily_returns)
            metrics.sortino_ratio = PerformanceCalculator.calculate_sortino_ratio(daily_returns)
            metrics.max_drawdown_pct = PerformanceCalculator.calculate_max_drawdown(values)

        return metrics
