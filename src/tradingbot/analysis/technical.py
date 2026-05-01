"""Technical Analysis Engine — Vectorized indicators using `ta` library."""

import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, SMAIndicator, MACD, IchimokuIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.volatility import AverageTrueRange, BollingerBands, KeltnerChannel
from ta.volume import OnBalanceVolumeIndicator, VolumePriceTrendIndicator

class TechnicalEngine:
    """Computes technical indicators for a given DataFrame of OHLCV data."""

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all standard technical indicators to the DataFrame inplace."""
        if df.empty or len(df) < 200:
            return df # Need sufficient data

        # Trend Indicators
        df['ema_9'] = EMAIndicator(close=df['close'], window=9).ema_indicator()
        df['ema_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
        df['ema_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['ema_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        df['sma_50'] = SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['sma_200'] = SMAIndicator(close=df['close'], window=200).sma_indicator()

        # MACD
        macd = MACD(close=df['close'])
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()

        # Ichimoku
        ichimoku = IchimokuIndicator(high=df['high'], low=df['low'])
        df['ichimoku_base'] = ichimoku.ichimoku_base_line()
        df['ichimoku_conversion'] = ichimoku.ichimoku_conversion_line()
        df['ichimoku_a'] = ichimoku.ichimoku_a()
        df['ichimoku_b'] = ichimoku.ichimoku_b()

        # Momentum Indicators
        df['rsi_14'] = RSIIndicator(close=df['close'], window=14).rsi()
        df['rsi_21'] = RSIIndicator(close=df['close'], window=21).rsi()
        
        stoch = StochasticOscillator(high=df['high'], low=df['low'], close=df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        df['roc_10'] = ROCIndicator(close=df['close'], window=10).roc()

        # Volatility Indicators
        df['atr_14'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close']).average_true_range()
        
        bb = BollingerBands(close=df['close'])
        df['bb_high'] = bb.bollinger_hband()
        df['bb_mid'] = bb.bollinger_mavg()
        df['bb_low'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()

        kc = KeltnerChannel(high=df['high'], low=df['low'], close=df['close'])
        df['kc_high'] = kc.keltner_channel_hband()
        df['kc_mid'] = kc.keltner_channel_mband()
        df['kc_low'] = kc.keltner_channel_lband()

        # Volume Indicators
        df['obv'] = OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
        df['vpt'] = VolumePriceTrendIndicator(close=df['close'], volume=df['volume']).volume_price_trend()

        # Derived: Volatility Regime
        # Simple definition: BB width vs its own 20-period moving average
        df['bb_width_sma'] = df['bb_width'].rolling(window=20).mean()
        df['volatility_regime'] = np.where(
            df['bb_width'] > df['bb_width_sma'] * 1.2, 'Expansion',
            np.where(df['bb_width'] < df['bb_width_sma'] * 0.8, 'Compression', 'Normal')
        )

        # Derived: Trend Alignment
        df['trend_aligned_bull'] = (df['ema_9'] > df['ema_21']) & (df['ema_21'] > df['ema_50']) & (df['close'] > df['ema_200'])
        df['trend_aligned_bear'] = (df['ema_9'] < df['ema_21']) & (df['ema_21'] < df['ema_50']) & (df['close'] < df['ema_200'])

        return df

    @staticmethod
    def extract_state(df: pd.DataFrame) -> dict:
        """Extract the latest indicator state from the DataFrame."""
        if df.empty or len(df) < 200:
            return {}
            
        latest = df.iloc[-1]
        
        # Determine Trend
        trend = "NEUTRAL"
        if latest['trend_aligned_bull']:
            trend = "STRONG_BULLISH"
        elif latest['trend_aligned_bear']:
            trend = "STRONG_BEARISH"
        elif latest['close'] > latest['ema_50']:
            trend = "BULLISH"
        elif latest['close'] < latest['ema_50']:
            trend = "BEARISH"

        # Determine Momentum
        momentum = "NEUTRAL"
        if latest['rsi_14'] > 70:
            momentum = "OVERBOUGHT"
        elif latest['rsi_14'] < 30:
            momentum = "OVERSOLD"
        elif latest['macd_hist'] > 0 and latest['macd_line'] > 0:
            momentum = "STRONG_UP"
        elif latest['macd_hist'] < 0 and latest['macd_line'] < 0:
            momentum = "STRONG_DOWN"

        return {
            "trend": trend,
            "momentum": momentum,
            "volatility": str(latest.get('volatility_regime', 'Normal')),
            "rsi": float(latest.get('rsi_14', 50)),
            "macd": float(latest.get('macd_hist', 0)),
            "atr": float(latest.get('atr_14', 0)),
            "ema_9": float(latest.get('ema_9', 0)),
            "ema_21": float(latest.get('ema_21', 0)),
            "ema_50": float(latest.get('ema_50', 0)),
            "bb_high": float(latest.get('bb_high', 0)),
            "bb_low": float(latest.get('bb_low', 0)),
        }
