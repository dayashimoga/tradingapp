"""API routes for the trading bot dashboard."""

from fastapi import APIRouter, HTTPException

router = APIRouter()

def get_engine():
    """Dependency to get the globally running engine."""
    from tradingbot.api.main import engine
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not started")
    return engine

@router.get("/status")
async def get_status():
    """Get overall bot status."""
    eng = get_engine()
    return {
        "status": "running" if eng.is_running else "stopped",
        "bot_name": eng.config.bot.name,
        "mode": eng.config.bot.mode,
        "symbols": eng.config.data.symbols,
    }

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
        "unrealized_pnl": pt.total_value - eng.config.bot.initial_capital,
        "positions": {
            sym: {
                "quantity": pos.quantity,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_pct": pos.pnl_pct,
            }
            for sym, pos in pt.positions.items()
        }
    }

@router.get("/trades")
async def get_recent_trades(limit: int = 50):
    """Get recently executed trades from the database."""
    eng = get_engine()
    
    # Check if database is initialized
    if not getattr(eng, "_database", None):
        return {"trades": []}
        
    from tradingbot.persistence.repository import Repository
    repo = Repository(eng._database)
    
    trades = await repo.get_recent_trades(limit=limit)
    
    return {
        "trades": [
            {
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "commission": t.commission,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "strategy_name": t.strategy_name,
            }
            for t in trades
        ]
    }
