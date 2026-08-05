"""Feature engineering for next-day return prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "sma_5_ratio",
    "sma_10_ratio",
    "sma_20_ratio",
    "sma_50_ratio",
    "volatility_10",
    "volatility_20",
    "rsi_14",
    "macd_hist",
    "bollinger_pct",
    "volume_ratio",
]
TARGET_COLUMN = "target_log_return"


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return indicator columns derived from ``close``/``volume``.

    The result is indexed like ``frame``; rows whose indicators need more
    history than is available contain ``NaN`` and are dropped by callers.
    """
    close = frame["close"].astype(float)
    volume = frame.get("volume", pd.Series(0.0, index=frame.index)).astype(float)
    log_close = np.log(close)

    out = pd.DataFrame(index=frame.index)
    out["ret_1"] = log_close.diff(1)
    out["ret_5"] = log_close.diff(5)
    out["ret_10"] = log_close.diff(10)
    out["ret_20"] = log_close.diff(20)
    for window in (5, 10, 20, 50):
        out[f"sma_{window}_ratio"] = close / close.rolling(window).mean() - 1.0
    out["volatility_10"] = out["ret_1"].rolling(10).std()
    out["volatility_20"] = out["ret_1"].rolling(20).std()
    out["rsi_14"] = _rsi(close, 14)
    out["macd_hist"] = _macd_histogram(close)
    out["bollinger_pct"] = _bollinger_pct(close, 20)
    rolling_volume = volume.rolling(20).mean()
    out["volume_ratio"] = np.where(rolling_volume > 0, volume / rolling_volume - 1.0, 0.0)
    return out[FEATURE_COLUMNS]


def build_training_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Features joined with the next-day log return target, NaNs removed."""
    features = build_features(frame)
    log_close = np.log(frame["close"].astype(float))
    features[TARGET_COLUMN] = log_close.shift(-1) - log_close
    return features.dropna()


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def _macd_histogram(close: pd.Series) -> pd.Series:
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    return (macd - macd.ewm(span=9, adjust=False).mean()) / close


def _bollinger_pct(close: pd.Series, window: int) -> pd.Series:
    mean = close.rolling(window).mean()
    std = close.rolling(window).std()
    width = (2.0 * std).replace(0.0, np.nan)
    return ((close - (mean - 2.0 * std)) / (2.0 * width)).clip(-1.0, 2.0)
