# TradingBot 🤖📈

**Production-level autonomous trading bot** supporting crypto (CCXT), US stocks (Alpaca), and multiple strategies with comprehensive risk management.

[![CI](https://github.com/yourusername/tradingbot/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/tradingbot/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-%3E90%25-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](.)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **Multi-Exchange Support** — Trade on 100+ crypto exchanges (CCXT) and US stocks (Alpaca)
- **Event-Driven Architecture** — AsyncIO pub/sub engine for decoupled, modular design
- **Built-in Strategies** — SMA Crossover, RSI, Bollinger Bands (extensible)
- **Risk Management** — Daily loss limits, position sizing, circuit breakers
- **Paper Trading** — Full simulation mode with realistic slippage
- **Monitoring** — Prometheus metrics, structured JSON logs, Telegram/Email alerts
- **Docker Ready** — Multi-stage Docker build with Compose stack (bot + Prometheus + Grafana)
- **CI/CD** — GitHub Actions with lint, test, coverage, and security scanning
- **>90% Test Coverage** — Comprehensive unit, integration, and e2e tests

## Quick Start

```bash
# Clone
git clone https://github.com/yourusername/tradingbot.git
cd tradingbot

# Setup
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e ".[dev,alerts]"

# Validate config
tradingbot validate

# Run paper trading
tradingbot run --mode paper
```

## Configuration

Copy `.env.example` to `.env` and fill in your API keys. Config files are in `config/`.

```yaml
# config/default.yaml
bot:
  mode: "paper"  # paper | live
risk:
  max_daily_loss: 500.0
  max_position_size: 0.05
  stop_loss_pct: 0.02
strategy:
  name: "sma_crossover"
```

## Testing

```bash
pytest tests/ -v --cov=src/tradingbot --cov-report=term-missing --cov-fail-under=90
```

## Docker

```bash
cd docker
docker-compose up -d
```

## Architecture

```
MarketData → Strategy → RiskManager → OrderManager → Broker → Portfolio
     ↑                      ↑                              ↓
     └──────── EventBus (AsyncIO Pub/Sub) ←────────────────┘
```

## License

MIT — See [LICENSE](LICENSE)
