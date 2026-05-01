"""CLI commands — command-line interface for the trading bot."""

from __future__ import annotations

import asyncio
import sys

import click
from dotenv import load_dotenv

# Automatically load API keys from .env if present
load_dotenv()


@click.group()
@click.version_option(version="0.1.0", prog_name="TradingBot")
def cli() -> None:
    """TradingBot — Autonomous Trading Engine."""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file (YAML/JSON)",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["paper", "live"]),
    default="paper",
    help="Trading mode",
)
def run(config: str | None, mode: str) -> None:
    """Start the trading bot."""
    from tradingbot.config.loader import load_config
    from tradingbot.core.engine import Engine
    from tradingbot.core.event_bus import EventBus
    from tradingbot.monitoring.logger import setup_logging

    # Load config
    overrides = {"bot": {"mode": mode}} if mode else {}
    bot_config = load_config(config_path=config, extra_overrides=overrides)

    # Setup logging
    setup_logging(
        level=bot_config.bot.log_level,
        log_format=bot_config.monitoring.log_format,
    )

    click.echo(f"Starting {bot_config.bot.name} in {bot_config.bot.mode} mode...")

    # Create engine
    event_bus = EventBus()
    engine = Engine(config=bot_config, event_bus=event_bus)

    # Run
    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        click.echo("\nShutdown requested...")
        sys.exit(0)


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), default=None)
def validate(config: str | None) -> None:
    """Validate a configuration file."""
    from tradingbot.config.loader import load_config

    try:
        bot_config = load_config(config_path=config)
        click.echo("✅ Configuration is valid!")
        click.echo(f"   Mode: {bot_config.bot.mode}")
        click.echo(f"   Strategy: {bot_config.strategy.name}")
        click.echo(f"   Symbols: {', '.join(bot_config.data.symbols)}")
        click.echo(f"   Risk - Max Daily Loss: ${bot_config.risk.max_daily_loss}")
        click.echo(f"   Risk - Max Position: {bot_config.risk.max_position_size * 100}%")
    except Exception as exc:
        click.echo(f"❌ Configuration error: {exc}", err=True)
        sys.exit(1)


@cli.command()
def strategies() -> None:
    """List available trading strategies."""
    # Import builtins to trigger registration
    import tradingbot.strategy.builtin.bollinger
    import tradingbot.strategy.builtin.rsi_strategy
    import tradingbot.strategy.builtin.sma_crossover  # noqa: F401
    from tradingbot.strategy.registry import list_strategies

    available = list_strategies()
    if not available:
        click.echo("No strategies registered.")
        return
        
    click.echo("\nRegistered Strategies:")
    for name in available:
        click.echo(f"  - {name}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8000, help="Port to bind")
def dashboard(host: str, port: int):
    """Run the trading bot dashboard API server."""
    import uvicorn
    click.echo(f"Starting Trading Bot Dashboard on http://{host}:{port}")
    uvicorn.run("tradingbot.api.main:app", host=host, port=port, reload=False)


@cli.command()
def version() -> None:
    """Show version information."""
    from tradingbot import __version__

    click.echo(f"TradingBot v{__version__}")


if __name__ == "__main__":
    cli()
