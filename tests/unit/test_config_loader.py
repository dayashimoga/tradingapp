"""Unit tests for configuration loader and schema."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tradingbot.config.loader import (
    _parse_env_value,
    deep_merge,
    load_config,
    load_env_overrides,
    load_yaml_file,
)
from tradingbot.config.schema import BotConfig, DataConfig, RiskConfig, TradingBotConfig


class TestDeepMerge:
    def test_simple_merge(self):
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override(self):
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_merge(self):
        result = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3, "d": 4}})
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_empty(self):
        assert deep_merge({}, {"a": 1}) == {"a": 1}
        assert deep_merge({"a": 1}, {}) == {"a": 1}

    def test_nested_override_non_dict(self):
        assert deep_merge({"a": {"b": 1}}, {"a": "string"}) == {"a": "string"}


class TestParseEnvValue:
    def test_bool(self):
        assert _parse_env_value("true") is True
        assert _parse_env_value("false") is False
        assert _parse_env_value("yes") is True
        assert _parse_env_value("no") is False

    def test_numbers(self):
        assert _parse_env_value("42") == 42
        assert _parse_env_value("3.14") == 3.14
        assert _parse_env_value("-10") == -10

    def test_string(self):
        assert _parse_env_value("hello") == "hello"


class TestLoadYamlFile:
    def test_valid(self, tmp_path):
        f = tmp_path / "t.yaml"
        f.write_text("bot:\n  name: TestBot\n")
        assert load_yaml_file(f)["bot"]["name"] == "TestBot"

    def test_missing(self):
        with pytest.raises(FileNotFoundError):
            load_yaml_file(Path("/nonexistent.yaml"))

    def test_empty(self, tmp_path):
        f = tmp_path / "e.yaml"
        f.write_text("")
        assert load_yaml_file(f) == {}

    def test_invalid_type(self, tmp_path):
        f = tmp_path / "i.yaml"
        f.write_text("- a\n- b\n")
        with pytest.raises(ValueError):
            load_yaml_file(f)


class TestLoadConfig:
    def test_defaults(self):
        c = load_config()
        assert isinstance(c, TradingBotConfig)
        assert c.bot.mode == "paper"

    def test_from_file(self, tmp_path):
        f = tmp_path / "c.yaml"
        f.write_text(yaml.dump({"bot": {"name": "MyBot"}, "risk": {"max_daily_loss": 1000.0}}))
        c = load_config(config_path=f)
        assert c.bot.name == "MyBot"
        assert c.risk.max_daily_loss == 1000.0

    def test_overrides(self):
        c = load_config(extra_overrides={"bot": {"name": "OBot"}})
        assert c.bot.name == "OBot"

    def test_env(self, monkeypatch):
        monkeypatch.setenv("TRADINGBOT_BOT_MODE", "paper")
        o = load_env_overrides()
        assert o["bot"]["mode"] == "paper"


class TestSchema:
    def test_valid_bot(self):
        assert BotConfig(mode="paper").mode == "paper"

    def test_invalid_mode(self):
        with pytest.raises(Exception):  # noqa: B017
            BotConfig(mode="bad")

    def test_invalid_log(self):
        with pytest.raises(Exception):  # noqa: B017
            BotConfig(log_level="BAD")

    def test_log_case(self):
        assert BotConfig(log_level="debug").log_level == "DEBUG"

    def test_empty_symbols(self):
        with pytest.raises(Exception):  # noqa: B017
            DataConfig(symbols=[])

    def test_invalid_tf(self):
        with pytest.raises(Exception):  # noqa: B017
            DataConfig(timeframe="2h")

    def test_risk_bounds(self):
        with pytest.raises(Exception):  # noqa: B017
            RiskConfig(max_position_size=1.5)

    def test_full_defaults(self):
        c = TradingBotConfig()
        assert c.execution.retry_attempts == 3
