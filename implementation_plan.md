# Autonomous Trading Dashboard — Advanced Enhancement Plan

## Current Architecture Summary

The existing codebase is a well-structured **Python FastAPI backend** + **React/Vite frontend** with:

| Layer | Technology | Status |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI + AsyncIO event bus | ✅ Solid |
| **Frontend** | React 19 + Vite + Recharts | ⚠️ Basic |
| **Strategies** | SMA Crossover, RSI, Bollinger (registry pattern) | ✅ Solid |
| **Risk** | RiskManager + CircuitBreaker + PositionSizer | ✅ Solid |
| **Execution** | PaperBroker + CCXTBroker + OrderManager w/ retry | ✅ Solid |
| **Persistence** | SQLite (aiosqlite) + SQLAlchemy ORM | ✅ Solid |
| **Data Feeds** | SimulatedDataFeed + CCXTDataFeed | ✅ Solid |
| **WebSocket** | FastAPI WS → broadcasts all event types | ✅ Working |
| **Monitoring** | Prometheus metrics + Grafana + Docker Compose | ✅ Solid |

> [!IMPORTANT]
> **Key design decision: We keep the existing Python/FastAPI backend.** The requirements document suggests Node.js, but the current Python backend is production-quality with 3 strategies, a full event bus, risk engine, CCXT integration, and persistence — rewriting this in Node.js would be months of regression. Instead, we enhance what exists.

---

## User Review Required

> [!WARNING]
> **Stack Decision**: The requirements spec suggests migrating to Node.js/Express + PostgreSQL + Redis. The current stack (Python FastAPI + SQLite) already implements 90% of the backend requirements. I recommend **keeping Python FastAPI** and upgrading SQLite → PostgreSQL only if scale demands it. This saves ~3 weeks of rewrite work. **Do you agree?**

> [!IMPORTANT]
> **Frontend Framework**: The spec suggests Next.js SSR. Since the dashboard is a real-time SPA that connects via WebSocket to a local/Docker backend, SSR provides no benefit. I recommend **staying with Vite + React** (current stack) and adding Zustand for state management. **Do you agree?**

> [!IMPORTANT]
> **TailwindCSS**: The spec requests TailwindCSS. The current codebase uses handcrafted vanilla CSS with a premium dark theme. Migrating to Tailwind means rewriting all existing styles. I recommend **adding TailwindCSS for new components** and gradually migrating existing CSS. **Do you agree, or should we do a full migration first?**

---

## Open Questions

1. **Deployment target**: The spec mentions Cloudflare Pages/Workers. The backend runs a persistent Python process with WebSocket connections — this **cannot run on Cloudflare Workers** (which are stateless/ephemeral). Should we target **Docker Compose** (current) or **Fly.io/Railway** for the backend?

2. **Backtesting priority**: Should the backtesting engine be Phase 3 (as planned) or deferred to a later phase? It's significant work and the live dashboard enhancements may be more urgent.

3. **AI Layer**: The optional AI explainability layer (Section 13) — should this be included in the plan or deferred entirely?

---

## Proposed Changes

The plan is split into **6 phases**, each independently deployable. Estimated total: **~3-4 weeks**.

---

### Phase 1: Foundation & Quick Fixes (Day 1-2)
*Fix current bugs + add Zustand + install TradingView Charts*

This phase fixes the issues visible in the screenshot (empty panels, zero signals, missing chart data) and sets up the foundation for all subsequent phases.

---

#### Backend Fixes

##### [MODIFY] [useBotData.js](file:///j:/tradingapp/frontend/src/hooks/useBotData.js)
- Fix WebSocket `market_data` handler — the `FillEvent` uses `fill_price` not `price`, so the fill log line crashes silently
- Fix signal counter — currently counts `[SIGNAL]` prefix in log text, but logs are only created for non-HOLD signals. Need to also count from WS events directly
- Add `status` event handling so the dashboard refreshes status immediately on WS connect

##### [MODIFY] [main.py](file:///j:/tradingapp/src/tradingbot/api/main.py)
- Fix `_event_listener` serialization — `FillEvent.fill_price` and `SignalEvent.side` (StrEnum) need proper serialization
- Add `market_data` throttle — currently broadcasts every tick (every 3s × 2 symbols = high volume). Add a 1-in-N sampler or debounce for chart data

##### [MODIFY] [routes.py](file:///j:/tradingapp/src/tradingbot/api/routes.py)
- Add `/api/strategies` endpoint — list all registered strategies with their params
- Add `/api/health` endpoint — expose engine health (event count, dead letters, strategies, feeds)
- Add `/api/analytics` endpoint — computed portfolio metrics (will be enhanced in Phase 4)

---

#### Frontend Foundation

##### [NEW] frontend/tailwind.config.js
- Install and configure TailwindCSS alongside existing vanilla CSS
- Configure dark theme colors to match existing `--bg-base`, `--accent-primary`, etc.

##### [NEW] frontend/src/store/useTradingStore.js
- Zustand store to replace all `useState` in App.jsx
- Slices: `portfolio`, `trades`, `marketData`, `signals`, `health`, `strategies`
- WebSocket middleware that hydrates the store directly

##### Install TradingView Lightweight Charts
- `npm install lightweight-charts`
- This replaces the Recharts `ComposedChart` for the main trading chart

---

### Phase 2: Trading Chart & Strategy Brain (Day 3-6)
*The two most impactful visual upgrades*

---

#### C. Trading Chart Panel (CRITICAL UPGRADE)

##### [NEW] frontend/src/components/TradingChart.jsx
- **TradingView Lightweight Charts** candlestick chart
- Multi-timeframe selector (1m, 5m, 15m, 1h, 4h, 1d)
- Overlays:
  - EMA 50/200 (line series)
  - SMA (from strategy data)
  - Bollinger Bands (area series for band, line for middle)
- Trade markers: Buy (green ▲) and Sell (red ▼) markers at execution prices
- Real-time candle updates via WebSocket `market_data` events
- Stop Loss / Take Profit zones rendered as horizontal price lines

##### [MODIFY] [simulator.py](file:///j:/tradingapp/src/tradingbot/data/feeds/simulator.py)
- Emit full OHLCV data that the candlestick chart needs (already does — ✅)
- Add configurable timeframe aggregation for multi-timeframe support

##### [NEW] src/tradingbot/api/routes.py → `/api/candles/{symbol}`
- REST endpoint to fetch historical OHLCV for initial chart load
- Returns aggregated candle data from market history buffer

##### Backend: OHLCV History Buffer
##### [NEW] src/tradingbot/data/history.py
- In-memory ring buffer that stores last N candles per symbol per timeframe
- Fed by MarketDataEvent listener on the event bus
- Provides data for the REST `/api/candles` endpoint and indicator computation

---

#### B. Strategy Brain Panel (NEW - CRITICAL)

##### [NEW] frontend/src/components/StrategyBrain.jsx
- Active strategy name + type badge (Trend / Mean Reversion / Scalping)
- Signal strength gauge (0-100%) — animated radial progress
- Market regime indicator (Trending / Ranging / Volatile) — computed from price volatility
- Indicator breakdown:
  - RSI value with color-coded zone (oversold/neutral/overbought)
  - SMA fast/slow crossover state
  - Bollinger Band position (above/below/within)
  - Volume anomaly detection

##### [MODIFY] Strategy classes (base.py, all builtins)
- Add `get_state()` method to each strategy that returns current indicator values
- Example: `RSIStrategy.get_state()` → `{"rsi": 42.3, "signal": "neutral", "warmed_up": true}`
- SMA returns `{"fast_sma": 64200, "slow_sma": 64180, "crossover": "golden"}`
- Bollinger returns `{"upper": 64500, "middle": 64200, "lower": 63900, "position": "within"}`

##### [NEW] routes.py → `/api/strategies/state`
- Returns real-time indicator state from all active strategies
- Polled by frontend every 3s (or pushed via WS heartbeat)

---

### Phase 3: Analytics & Backtesting (Day 7-12)
*Professional-grade metrics and historical simulation*

---

#### F. Portfolio Analytics (UPGRADE)

##### [NEW] src/tradingbot/analytics/performance.py
- Pure Python performance calculator:
  - **Total Return (%)** — `(current_value - initial) / initial × 100`
  - **Sharpe Ratio** — `mean(daily_returns) / std(daily_returns) × sqrt(252)`
  - **Sortino Ratio** — Sharpe but only downside deviation
  - **Max Drawdown** — peak-to-trough calculation from portfolio history
  - **Win Rate** — `winning_trades / total_trades`
  - **Profit Factor** — `gross_profit / gross_loss`
  - **Avg Trade Duration** — from trade entry/exit timestamps

##### [NEW] frontend/src/components/PortfolioAnalytics.jsx
- Equity curve chart (TradingView Lightweight Charts line series)
- Drawdown curve (inverted area chart, red fill)
- Benchmark comparison toggle (BTC/ETH overlay)
- Metric cards in 2-column grid with sparklines

##### [MODIFY] routes.py → `/api/analytics`
- Returns all computed metrics from `performance.py`
- Uses portfolio history from database + current trade records

---

#### 7. Backtesting Engine (CRITICAL)

##### [NEW] src/tradingbot/backtesting/engine.py
- `BacktestEngine` class:
  - Takes: strategy name, symbol, timeframe, date range
  - Replays historical OHLCV data through strategy → risk → execution pipeline
  - Uses the existing `Engine.run_once()` method
  - Collects all fills, portfolio snapshots, signals

##### [NEW] src/tradingbot/backtesting/data_loader.py
- Loads historical data from:
  - CCXT `fetch_ohlcv()` for crypto
  - Local CSV files for offline backtesting
- Caches fetched data to SQLite for repeat runs

##### [NEW] routes.py → `/api/backtest`
- POST endpoint: `{strategy, symbol, timeframe, start_date, end_date}`
- Runs backtest asynchronously, returns job ID
- GET endpoint: `/api/backtest/{job_id}` for results
- Returns: ROI, drawdown, win rate, trade log, equity curve data

##### [NEW] frontend/src/components/BacktestPanel.jsx
- Strategy selector + parameter inputs
- Date range picker
- Results display:
  - Equity curve overlay on main chart
  - Performance metrics table
  - Trade-by-trade log with expandable details

---

### Phase 4: Risk & Multi-Strategy (Day 13-16)
*Critical operational controls*

---

#### J. Risk Management Dashboard (CRITICAL)

##### [NEW] frontend/src/components/RiskDashboard.jsx
- Risk per trade (%) — slider + current value
- Total exposure bar (% of portfolio in positions)
- Daily loss limit — progress bar toward limit
- Max drawdown threshold — with visual warning zones
- **Kill switch toggle** — big red button that sends POST to `/api/risk/kill`
- Circuit breaker status indicator with cooldown timer

##### [NEW] routes.py → Risk endpoints
- `GET /api/risk/state` — current risk metrics from RiskManager
- `POST /api/risk/kill` — activates circuit breaker with indefinite cooldown
- `POST /api/risk/resume` — deactivates circuit breaker
- `PUT /api/risk/config` — update risk parameters live (max_position_size, etc.)

##### [MODIFY] [manager.py](file:///j:/tradingapp/src/tradingbot/risk/manager.py)
- Add `get_state()` method returning all current risk metrics
- Add `set_kill_switch()` / `clear_kill_switch()` methods
- Track daily trade count, exposure per symbol

---

#### I. Multi-Strategy Panel (NEW)

##### [MODIFY] [engine.py](file:///j:/tradingapp/src/tradingbot/core/engine.py)
- Support registering multiple strategies simultaneously
- Track per-strategy signal count, trade count, PnL

##### [MODIFY] Config schema
- Support `strategies: [...]` array (plural) in config — list of strategy configs
- Backward-compatible: single `strategy:` still works

##### [NEW] frontend/src/components/MultiStrategyPanel.jsx
- List of all strategies with:
  - Name + type badge
  - Status toggle (Active / Paused)
  - Performance stats (win rate, PnL, trade count)
  - Last signal time + direction

##### [NEW] routes.py → `/api/strategies/{name}/toggle`
- POST to pause/resume individual strategies

---

### Phase 5: Enhanced UI Panels (Day 17-20)
*All remaining UI modules from the spec*

---

#### D. Bot Activity Timeline (UPGRADE from Algorithmic Feed)

##### [NEW] frontend/src/components/ActivityTimeline.jsx
- Replaces the basic terminal log
- Each entry is an expandable card showing:
  - Timestamp + Event type icon
  - Confidence score badge
  - Decision reasoning text
  - Expandable JSON details (indicator values, risk check results)
- Virtualized list (react-window) for performance with 1000+ events
- Color-coded by event type (Signal=blue, Risk=yellow, Fill=green, Error=red)

---

#### E. Signal Intelligence Panel (UPGRADE)

##### [NEW] frontend/src/components/SignalIntelligence.jsx
- Signal type identification (Golden Cross, RSI Divergence, Band Touch, etc.)
- Strength score with animated gauge
- Supporting indicators breakdown
- Historical accuracy: % of past signals of this type that were profitable
- Last N occurrences timeline with outcomes (profit/loss per signal)

##### [NEW] src/tradingbot/analytics/signal_tracker.py
- Tracks signal → fill → outcome chain
- Computes per-signal-type accuracy over time
- Stores in database for persistence

---

#### K. System Health Panel (DEVOPS-LEVEL)

##### [MODIFY] frontend/src/components/ — enhance existing Health section
- Add: API latency (measured round-trip from frontend)
- Add: Order execution latency (from OrderManager metrics)
- Add: WebSocket reconnect count
- Add: Error rate (errors / total events)
- Add: Retry queue size (from OrderManager.pending_count)
- All values update in real-time via heartbeat events

##### [MODIFY] HeartbeatEvent details
- Include additional metrics: order_latency_ms, error_rate, retry_queue_size

---

#### G. Trade Ledger (UPGRADE)

##### [NEW] frontend/src/components/TradeLedger.jsx
- Full-featured trade table with:
  - All fields (symbol, entry/exit price, size, PnL, strategy, timestamp)
  - Column sorting
  - Filters: by strategy, by symbol, by date range
  - Pagination for large datasets
  - Export to CSV

##### [MODIFY] routes.py → `/api/trades`
- Add query params: `?strategy=rsi&symbol=BTC/USDT&from=2026-01-01&to=2026-05-01`

---

#### H. Open Positions Panel (UPGRADE)

##### [MODIFY] Existing positions table in App.jsx
- Add visual PnL bar (green/red horizontal bar proportional to PnL %)
- Add risk exposure column (position value / portfolio value %)
- Add SL/TP indicators if set

---

#### L. Market Context Panel (NEW)

##### [NEW] frontend/src/components/MarketContext.jsx
- BTC dominance (fetched from free CoinGecko API)
- Fear & Greed Index (from alternative.me API)
- Volume spike detection (computed from market_data events)
- Top movers among tracked symbols

##### [NEW] routes.py → `/api/market/context`
- Proxy endpoint for external APIs (avoids CORS issues from frontend)
- Caches results for 5 minutes

---

#### M. Manual Trade Console (UPGRADE)

##### [MODIFY] ManualTradeTerminal component
- Add order type selector (Market / Limit / Stop-Loss)
- Position sizing: % of portfolio slider
- Auto SL/TP calculation based on risk config
- Order preview before execution
- Support limit price input

##### [MODIFY] routes.py → `/api/trade/manual`
- Support additional order types (limit, stop)
- Accept SL/TP parameters

---

### Phase 6: Polish & Deployment (Day 21-24)
*Performance optimization, testing, deployment config*

---

#### Performance Optimization

##### Frontend
- Lazy load heavy components (BacktestPanel, TradeLedger) with `React.lazy`
- Virtualized lists for logs (react-window or @tanstack/virtual)
- Web Worker for indicator calculations if needed
- Memoize expensive chart computations

##### Backend
- Add in-memory caching for frequently-accessed endpoints (portfolio, health)
- Batch portfolio history snapshots (every 30s instead of every tick)
- Optimize trade query with proper indexing

---

#### Deployment

##### [MODIFY] docker-compose.yml
- Keep current Docker Compose setup (proven working)
- Add environment variable for deployment mode selection
- Document Fly.io deployment as alternative

##### [NEW] .github/workflows/deploy.yml (optional)
- CI/CD pipeline for Docker image build + push
- Auto-deploy to target platform on main branch push

---

#### Testing

- Backend: pytest unit tests for new analytics, backtesting, and strategy state
- Frontend: Manual browser verification via browser tool
- Integration: End-to-end WebSocket flow verification

---

## Verification Plan

### Automated Tests
```bash
# Backend
cd j:\tradingapp
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Frontend build check
cd frontend
npm run build
```

### Browser Verification
- Launch `docker compose up` and verify at `http://localhost:3000`:
  1. TradingView chart renders with live candlesticks
  2. Strategy Brain shows real-time indicator values
  3. System Health, Signal Analysis, and Algorithmic Feed are populated
  4. Trade markers appear on chart when fills occur
  5. Risk dashboard kill switch works
  6. Backtest runs and displays results

### Manual Verification
- Verify WebSocket connection stability over 30+ minutes
- Verify chart performance with 1000+ candles
- Verify all stat cards update in real-time

---

## Phase Summary

| Phase | Scope | Duration | Impact |
|---|---|---|---|
| **1** | Bug fixes + Zustand + TailwindCSS + foundation | 2 days | 🟢 Fixes current issues |
| **2** | TradingView Chart + Strategy Brain | 4 days | 🔴 Highest visual impact |
| **3** | Analytics + Backtesting Engine | 5 days | 🔴 Critical feature |
| **4** | Risk Dashboard + Multi-Strategy | 4 days | 🔴 Critical operational |
| **5** | All remaining UI panels | 4 days | 🟡 Feature completeness |
| **6** | Polish + Deployment + Testing | 3 days | 🟢 Production readiness |

**Total: ~22 working days**
