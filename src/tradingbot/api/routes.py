"""API routes for the trading bot dashboard."""

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def get_engine():
    """Dependency to get the globally running engine."""
    from tradingbot.api.main import engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not started")
    return engine


# ==================== STATUS ====================

@router.get("/status")
async def get_status():
    """Get overall bot status."""
    eng = get_engine()
    state = "ANALYZING"
    if getattr(eng, "_order_manager", None) and eng._order_manager.pending_count > 0:
        state = "TRANSACTING"
        
    return {
        "status": "running" if eng.is_running else "stopped",
        "state": state,
        "bot_name": eng.config.bot.name,
        "mode": eng.config.bot.mode,
        "symbols": eng.config.data.symbols,
    }


# ==================== PORTFOLIO ====================

@router.get("/portfolio")
async def get_portfolio():
    """Get current portfolio state and open positions."""
    eng = get_engine()
    pt = eng._portfolio_tracker
    if not pt:
        return {"cash": 0.0, "total_value": 0.0, "unrealized_pnl": 0.0, "positions": {}}
    
    return {
        "cash": pt.cash,
        "total_value": pt.total_value,
        "unrealized_pnl": pt.unrealized_pnl,
        "realized_pnl": pt.realized_pnl,
        "positions": {
            sym: {
                "quantity": pos.quantity,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_pct": pos.unrealized_pnl_pct / 100,
            }
            for sym, pos in pt.positions.items()
        }
    }


# ==================== TRADES ====================

@router.get("/trades")
async def get_recent_trades(limit: int = 50, symbol: str | None = None, strategy: str | None = None):
    """Get recently executed trades from the database."""
    eng = get_engine()
    
    # Check if database is initialized
    if not getattr(eng, "_database", None):
        return {"trades": []}
        
    from tradingbot.persistence.repository import TradeRepository
    repo = TradeRepository(eng._database)
    
    trades = await repo.get_trades(symbol=symbol, limit=limit)
    
    def parse_meta(m: str):
        try:
            return json.loads(m)
        except Exception:
            return {}

    result = []
    for t in trades:
        trade_dict = {
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "commission": t.commission,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "strategy_name": t.strategy_name,
            "reason": t.reason,
            "pnl": t.pnl,
            "metadata": parse_meta(t.metadata_json),
        }
        # Filter by strategy if specified
        if strategy and t.strategy_name != strategy:
            continue
        result.append(trade_dict)

    return {"trades": result}


# ==================== STRATEGIES ====================

@router.get("/strategies")
async def get_strategies():
    """List all registered strategies with their current state."""
    eng = get_engine()
    strategies = []
    for s in eng._strategies:
        state = s.get_state()
        strategies.append(state)
    return {"strategies": strategies, "count": len(strategies)}


@router.get("/strategies/state")
async def get_strategies_state():
    """Get real-time indicator state from all active strategies."""
    eng = get_engine()
    states = {}
    for s in eng._strategies:
        states[s.name] = s.get_state()
    return {"states": states}


# ==================== HEALTH ====================

@router.get("/health")
async def get_health():
    """Get system health metrics."""
    eng = get_engine()
    om = eng._order_manager
    return {
        "status": "healthy" if eng.is_running else "stopped",
        "event_count": eng.event_bus.event_count,
        "dead_letters": len(eng.event_bus.dead_letter_queue),
        "strategies": len(eng._strategies),
        "data_feeds": len(eng._data_feeds),
        "orders_filled": om.filled_count if om else 0,
        "orders_failed": om.failed_count if om else 0,
        "orders_pending": om.pending_count if om else 0,
        "subscribers": eng.event_bus.get_subscriber_count(),
    }


# ==================== ANALYTICS ====================

@router.get("/analytics")
async def get_analytics():
    """Get computed portfolio performance metrics."""
    eng = get_engine()
    pt = eng._portfolio_tracker
    if not pt:
        return {"metrics": {}}

    from tradingbot.analytics.performance import PerformanceCalculator

    # Get trades
    trades_data = []
    if getattr(eng, "_database", None):
        from tradingbot.persistence.repository import TradeRepository
        repo = TradeRepository(eng._database)
        records = await repo.get_trades(limit=500)
        for t in records:
            trades_data.append({
                "side": t.side,
                "pnl": t.pnl,
                "price": t.price,
                "quantity": t.quantity,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            })

    # Build portfolio snapshots from portfolio history 
    snapshots = [{"total_value": pt.total_value}]

    metrics = PerformanceCalculator.compute_from_trades(
        trades=trades_data,
        portfolio_snapshots=snapshots,
        initial_capital=pt._initial_cash,
        current_value=pt.total_value,
    )

    return {
        "metrics": {
            "total_return_pct": round(metrics.total_return_pct, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 2) if metrics.sharpe_ratio != float("inf") else 0,
            "sortino_ratio": round(metrics.sortino_ratio, 2) if metrics.sortino_ratio != float("inf") else 0,
            "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
            "win_rate": round(metrics.win_rate * 100, 1),
            "profit_factor": round(metrics.profit_factor, 2) if metrics.profit_factor != float("inf") else 999,
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "gross_profit": round(metrics.gross_profit, 2),
            "gross_loss": round(metrics.gross_loss, 2),
            "best_trade": round(metrics.best_trade, 2),
            "worst_trade": round(metrics.worst_trade, 2),
        }
    }


# ==================== CANDLES (Chart Data) ====================

@router.get("/candles/{symbol}")
async def get_candles(symbol: str, limit: int = 200):
    """Get OHLCV candle data for TradingView chart."""
    eng = get_engine()
    # URL-decode: BTC%2FUSDT → BTC/USDT
    symbol = symbol.replace("%2F", "/")
    candles = eng._ohlcv_history.get_candles_dict(symbol, limit)
    return {"symbol": symbol, "candles": candles, "count": len(candles)}


# ==================== RISK ====================

@router.get("/risk/state")
async def get_risk_state():
    """Get current risk management state."""
    eng = get_engine()
    rm = eng._risk_manager
    if not rm:
        return {"error": "No risk manager configured"}
    return rm.get_state()


class KillSwitchRequest(BaseModel):
    active: bool


@router.post("/risk/kill")
async def set_kill_switch(request: KillSwitchRequest):
    """Activate or deactivate the kill switch."""
    eng = get_engine()
    rm = eng._risk_manager
    if not rm:
        raise HTTPException(status_code=503, detail="No risk manager")
    rm.set_kill_switch(request.active)
    return {"message": f"Kill switch {'activated' if request.active else 'deactivated'}"}


# ==================== MANUAL TRADE ====================

class ManualTradeRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"


@router.post("/trade/manual")
async def execute_manual_trade(request: ManualTradeRequest):
    """Execute a manual trade."""
    eng = get_engine()
    
    from tradingbot.core.events import SignalEvent, SignalSide
    try:
        side_enum = SignalSide(request.side.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid side. Use 'buy' or 'sell'.")
        
    # We don't specify suggested_price to just use the current market price (Market Order)
    signal = SignalEvent(
        source="manual",
        symbol=request.symbol.upper(),
        side=side_enum,
        strength=1.0,
        strategy_name="Manual Override",
        reason="User Override",
        metadata={"type": "manual_trade"}
    )
    
    await eng.event_bus.publish(signal)
    
    return {"message": "Manual trade signal dispatched", "signal_id": signal.event_id}


# ==================== MARKET CONTEXT ====================

@router.get("/market/context")
async def get_market_context():
    """Get market context data (prices, volume from tracked symbols)."""
    eng = get_engine()
    prices = eng._ohlcv_history.latest_prices
    symbols_data = {}
    for sym in eng.config.data.symbols:
        candles = eng._ohlcv_history.get_candles(sym, limit=20)
        if candles:
            volumes = [c.volume for c in candles]
            avg_vol = sum(volumes) / len(volumes) if volumes else 0
            latest_vol = volumes[-1] if volumes else 0
            vol_spike = latest_vol > avg_vol * 1.5 if avg_vol > 0 else False
            price_change = 0
            if len(candles) >= 2:
                price_change = ((candles[-1].close - candles[0].close) / candles[0].close * 100)
            symbols_data[sym] = {
                "price": candles[-1].close,
                "price_change_pct": round(price_change, 2),
                "volume": round(latest_vol, 2),
                "avg_volume": round(avg_vol, 2),
                "volume_spike": vol_spike,
            }
    return {"symbols": symbols_data, "tracked_count": len(eng.config.data.symbols)}
