"""Quantitative & Statistical Models module."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class QuantModels:
    """
    Implements statistical and quantitative models for market analysis.
    """

    @staticmethod
    def calculate_zscore(series: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate rolling Z-score for mean reversion strategies.
        Z = (X - μ) / σ
        """
        rolling_mean = series.rolling(window=window).mean()
        rolling_std = series.rolling(window=window).std()
        return (series - rolling_mean) / rolling_std

    @staticmethod
    def calculate_rolling_correlation(
        series1: pd.Series, series2: pd.Series, window: int = 30
    ) -> pd.Series:
        """
        Calculate rolling correlation between two assets (e.g., BTC and ETH).
        Useful for statistical arbitrage or pairs trading.
        """
        return series1.rolling(window=window).corr(series2)

    @staticmethod
    def detect_regime(returns: pd.Series, window: int = 20) -> pd.Series:
        """
        Detect market regime based on realized volatility.
        Returns 1 for High Volatility, 0 for Low Volatility regime.
        """
        # Calculate annualized volatility
        vol = returns.rolling(window=window).std() * np.sqrt(365 * 24 * 60) # Assuming 1m data
        
        # Simple clustering: if current vol is > 75th percentile of rolling vol, high vol
        threshold = vol.rolling(window=window * 5).quantile(0.75)
        
        regime = pd.Series(0, index=returns.index)
        regime[vol > threshold] = 1
        return regime

    @staticmethod
    def calculate_hurst_exponent(ts: list[float] | np.ndarray) -> float:
        """
        Calculate Hurst Exponent to determine if series is trending, 
        mean-reverting, or random walk.
        H < 0.5: Mean Reverting
        H = 0.5: Random Walk
        H > 0.5: Trending
        """
        ts = np.array(ts)
        if len(ts) < 100:
            return 0.5
            
        lags = range(2, 20)
        
        # Calculate the array of the variances of the lagged differences
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        
        # Use a linear fit to estimate the Hurst Exponent
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        
        return poly[0] * 2.0
        
    @staticmethod
    def get_statistical_features(df: pd.DataFrame) -> dict[str, Any]:
        """
        Extracts key quantitative features from an OHLCV dataframe.
        """
        if df.empty or len(df) < 50:
            return {}
            
        close = df['close']
        returns = close.pct_change().dropna()
        
        # Latest Z-score
        zscore = QuantModels.calculate_zscore(close).iloc[-1]
        
        # Regime (0 or 1)
        regime = QuantModels.detect_regime(returns).iloc[-1]
        
        # Hurst Exponent (use last 200 closes)
        hurst = QuantModels.calculate_hurst_exponent(close.tail(200).values)
        
        # Return asymmetry (Skewness)
        skew = returns.tail(100).skew()
        
        # Fat tails (Kurtosis)
        kurt = returns.tail(100).kurtosis()
        
        return {
            "zscore": float(zscore) if not pd.isna(zscore) else 0.0,
            "high_vol_regime": bool(regime == 1),
            "hurst_exponent": float(hurst) if not pd.isna(hurst) else 0.5,
            "skewness": float(skew) if not pd.isna(skew) else 0.0,
            "kurtosis": float(kurt) if not pd.isna(kurt) else 0.0,
        }
