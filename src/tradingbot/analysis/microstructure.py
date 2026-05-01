"""Market Microstructure module — analyzes orderbook depth and funding rates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingbot.core.events import OrderBookEvent, FundingRateEvent

logger = logging.getLogger(__name__)


@dataclass
class MicrostructureState:
    """State object holding the latest microstructure analysis for a symbol."""
    symbol: str
    imbalance: float = 0.0  # -1.0 to 1.0 (negative=sell pressure, positive=buy pressure)
    spread_pct: float = 0.0
    funding_rate: float = 0.0
    liquidity_score: float = 0.0 # 0.0 to 1.0


class MicrostructureAnalyzer:
    """
    Analyzes high-frequency microstructure data like orderbooks and funding.
    """

    def __init__(self) -> None:
        self.state: dict[str, MicrostructureState] = {}

    def get_state(self, symbol: str) -> MicrostructureState:
        if symbol not in self.state:
            self.state[symbol] = MicrostructureState(symbol=symbol)
        return self.state[symbol]

    def process_orderbook(self, event: "OrderBookEvent") -> MicrostructureState:
        """Process L2 orderbook snapshot and calculate imbalance/spread."""
        state = self.get_state(event.symbol)

        bids = event.bids
        asks = event.asks

        if not bids or not asks:
            return state

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        
        # 1. Spread Calculation
        mid_price = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid
        state.spread_pct = (spread / mid_price) * 100.0 if mid_price > 0 else 0.0

        # 2. Imbalance Calculation (Volume weighted)
        # Sum volume of top N levels
        bid_vol = sum(amount for price, amount in bids[:10])
        ask_vol = sum(amount for price, amount in asks[:10])
        total_vol = bid_vol + ask_vol

        if total_vol > 0:
            # -1 to 1: positive means more bids (buying pressure)
            state.imbalance = (bid_vol - ask_vol) / total_vol
        else:
            state.imbalance = 0.0

        # 3. Liquidity Score (simple proxy based on depth)
        # Assuming higher total volume near the spread equals higher liquidity
        # Normalize to a generic 0-1 score (arbitrary scaling for now)
        base_liquidity = min(total_vol / 100.0, 1.0)
        # Penalize if spread is high (> 0.5%)
        spread_penalty = max(0.0, min((state.spread_pct - 0.1) / 0.4, 1.0))
        state.liquidity_score = max(0.0, base_liquidity * (1.0 - spread_penalty))

        return state

    def process_funding(self, event: "FundingRateEvent") -> MicrostructureState:
        """Process perpetual swap funding rate."""
        state = self.get_state(event.symbol)
        state.funding_rate = event.funding_rate
        return state

    def evaluate_signals(self, symbol: str) -> dict[str, float]:
        """
        Evaluate microstructure state to generate predictive features.
        Returns a dictionary of features for the AI layer or Strategy logic.
        """
        state = self.get_state(symbol)
        
        features = {
            "ob_imbalance": state.imbalance,
            "spread_pct": state.spread_pct,
            "funding_rate": state.funding_rate,
            "liquidity_score": state.liquidity_score,
            "microstructure_bias": 0.0,
        }
        
        # Calculate a simple directional bias (-1 to 1) based on microstructure
        bias = 0.0
        # Positive imbalance adds to bullish bias
        bias += state.imbalance * 0.5 
        
        # Negative funding rate (shorts pay longs) is often a bullish contrarian signal 
        # or indicates heavy shorting. If funding is very high, it's bearish.
        if state.funding_rate > 0.0005:  # 0.05%
            bias -= 0.3
        elif state.funding_rate < -0.0005:
            bias += 0.3
            
        features["microstructure_bias"] = max(-1.0, min(1.0, bias))
        return features
