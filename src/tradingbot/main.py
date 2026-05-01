"""Main entry point for the trading bot."""

from __future__ import annotations


def main() -> None:
    """Main entry point."""
    from tradingbot.cli.commands import cli

    cli()


if __name__ == "__main__":
    main()
