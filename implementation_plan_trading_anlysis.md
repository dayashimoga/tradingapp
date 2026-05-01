# Advanced Analysis Engine Implementation Plan

This document outlines the strategy for building the **High-Precision Stocks & Crypto Analysis Engine** into our existing event-driven autonomous trading bot. 

The approach strictly adheres to a **no-cost, 100% open-source strategy**, leveraging the existing Python/FastAPI backend and reacting to live market data streams without requiring expensive third-party subscriptions.

## Gap Analysis (Current vs. Target)

| Component | Current State | Target State | Open-Source Strategy |
| :--- | :--- | :--- | :--- |
| **Technical Analysis** | Basic custom SMA, RSI, Bollinger implementations. | Multi-dimensional (VWAP, MACD, Ichimoku, Volatility Regimes, Support/Resistance). | Integrate `pandas-ta` for highly optimized, comprehensive technical indicator calculation. |
| **Microstructure** | OHLCV only. | Order book depth, funding rates, spread analysis. | Expand `ccxt` data feeds to subscribe to L2 Orderbook and Funding Rate websockets. |
| **Multi-Timeframe** | Single timeframe (interval-based). | Alignment across 1m, 5m, 15m, 1h, 1d. | Implement a Timeframe Aggregator buffer that resamples base tick data using `pandas`. |
| **Sentiment & Macro** | None. | Twitter/News NLP scoring, DXY, Interest rates. | Use free tiers/scraping: `yfinance` for Macro (DXY, SPX), `vaderSentiment` / lightweight HuggingFace transformers for News NLP, Alternative.me for Fear/Greed. |
| **AI/ML Layer** | None. | Probability of movement, Confidence scoring. | `scikit-learn` (Random Forest) / `xgboost` trained periodically on historical data via a background worker task. |
| **Signal Engine** | Simple `SignalEvent` (Buy/Sell, Strength). | Consolidated JSON Output with reasoning, trend, momentum, volatility states. | Enhance `SignalEvent` schema and build a `SignalAggregator` that weights inputs from all layers. |

---

## Proposed Changes & Phased Implementation

The implementation will be divided into modular components to ensure stability and continuous integration into the existing `Engine`.

### Phase 1: Core Technical & Multi-Timeframe Engine (Foundation)
Replace basic custom indicator math with a robust, vectorized library and implement timeframe aggregation.

#### [NEW] `src/tradingbot/analysis/technical.py`
- Wrap `pandas-ta` to compute Trend (EMA, SMA, VWAP, SuperTrend), Momentum (RSI, MACD, ROC), and Volatility (ATR, Keltner) efficiently.
- Calculate Volatility Regimes (Compression/Expansion) based on Bollinger Band Width.

#### [NEW] `src/tradingbot/analysis/timeframe.py`
- `MultiTimeframeAggregator`: Subscribes to `MarketDataEvent`, buffers 1m candles, and dynamically resamples into 5m, 15m, 1h, 4h, 1d DataFrames.

#### [MODIFY] `src/tradingbot/core/events.py`
- Expand `SignalEvent` to include the required comprehensive payload: `confidence`, `trend`, `momentum`, `volatility`, `sentiment`, `risk_score`, `entry`, `stop_loss`, `take_profit`, and `reasoning`.

---

### Phase 2: Market Microstructure & Quantitative Models
Enhance data ingestion specifically for crypto mechanics and statistical models.

#### [MODIFY] `src/tradingbot/data/feeds/ccxt_feed.py`
- Add optional subscriptions for Order Book (L2) and Funding Rates.
- Emit new events: `OrderBookEvent` and `FundingRateEvent`.

#### [NEW] `src/tradingbot/analysis/microstructure.py`
- Calculate Bid/Ask Imbalance Ratio, Spread Analysis, and detect Liquidity Walls from OrderBook updates.

#### [NEW] `src/tradingbot/analysis/quantitative.py`
- Z-score normalization for mean reversion.
- Rolling correlation matrix (e.g., BTC vs. specific altcoin) for pair trading signals.

---

### Phase 3: Sentiment & Macro Intelligence (Zero-Cost Data)
Integrate external context without paying for premium APIs.

#### [NEW] `src/tradingbot/data/feeds/macro_feed.py`
- Poll `yfinance` daily/hourly for S&P 500, NASDAQ, DXY (Dollar Index), and TNX (Interest Rates).

#### [NEW] `src/tradingbot/analysis/sentiment.py`
- `SentimentAnalyzer`: Fetch free Fear & Greed Index API.
- Scrape/poll free Crypto news RSS feeds (e.g., CoinTelegraph, CryptoPanic free tier).
- Use `vaderSentiment` (lexicon-based, extremely fast, no GPU needed) to score news headlines and generate a blended Sentiment Score (-100 to 100).

---

### Phase 4: Signal Aggregation & AI Predictive Layer
Fuse all data points into a single actionable decision.

#### [NEW] `src/tradingbot/analysis/ml_predictor.py`
- Implement an XGBoost classifier.
- **Feature Engineering:** Feed technical indicators, volume profile, sentiment score, and macro data as features.
- **Target:** Predict if the next $N$ periods will have a positive return > threshold.
- Outputs a `Confidence Score (0-100)`.

#### [NEW] `src/tradingbot/strategy/advanced_aggregator.py`
- A new master strategy class that listens to all analysis layers.
- Uses a weight-based scoring system (e.g., Technical 40%, ML 30%, Sentiment 15%, Macro 15%).
- Generates the final, enriched `SignalEvent`.

---

### Phase 5: Advanced Risk & Execution
Upgrade the existing risk manager to handle the new signal complexities.

#### [MODIFY] `src/tradingbot/risk/manager.py` & `position_sizer.py`
- Implement Volatility-Adjusted Sizing (inverse to ATR).
- Add ATR-based dynamic Stop Loss and configurable Risk/Reward Take Profits (e.g., 1:2 R:R).
- Correlation-adjusted exposure (prevent buying 5 highly correlated crypto assets simultaneously).

---

> [!IMPORTANT]
> **Performance Considerations (Event Loop Blockers)**
> Machine Learning inference (`xgboost`) and heavy `pandas` calculations can block the `asyncio` event loop. 
> We must execute these in `concurrent.futures.ProcessPoolExecutor` or `ThreadPoolExecutor` to ensure WebSocket streaming and immediate order execution are never delayed.

> [!WARNING]
> **Zero-Cost Limitations**
> - Institutional flow data (Options Gamma, Dark Pools) is strictly paywalled. We will rely on proxy metrics (e.g., Volume spikes, Order book depth).
> - Twitter/X API is prohibitively expensive. We will rely on News RSS feeds and free alternative data sources (Fear/Greed, Reddit scraping if API permits).

---

## User Review Required

Please review the proposed architecture and answer the following open questions:

1. **AI/ML Layer Approach:** Do you want the ML model to train dynamically in the background while running, or should we implement a static pre-trained model approach that you manually retrain via a CLI command? (A background training task is more complex but fully autonomous).
2. **Library Choices:** I propose using `pandas-ta` for technical analysis and `xgboost` for ML, as they are enterprise-standard and fully open-source. Does this align with your tech stack preferences?
3. **Phased Execution:** Should we execute Phase 1 (Technicals & Timeframes) and Phase 4 (Master Aggregator Strategy) first so you can see the advanced JSON signal structure in the UI immediately, before layering in Sentiment, Microstructure, and ML?
