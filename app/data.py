"""Market data access with an in-process TTL cache and offline fallback."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app import config

_PERIOD_TO_DAYS = {
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
    "10y": 2520,
    "max": 2520,
}

_cache: dict[tuple[str, str], tuple[float, PriceHistory]] = {}


class DataUnavailableError(RuntimeError):
    """Raised when no price history could be produced for a ticker."""


@dataclass(frozen=True)
class PriceHistory:
    """Daily close prices for a single ticker."""

    ticker: str
    period: str
    frame: pd.DataFrame
    source: str

    @property
    def last_close(self) -> float:
        return float(self.frame["close"].iloc[-1])

    @property
    def last_date(self) -> pd.Timestamp:
        return pd.Timestamp(self.frame.index[-1])


def get_price_history(ticker: str, period: str | None = None) -> PriceHistory:
    """Return daily history for ``ticker``, cached for ``CACHE_TTL_SECONDS``."""
    symbol = normalize_ticker(ticker)
    window = period or config.DEFAULT_PERIOD
    key = (symbol, window)
    cached = _cache.get(key)
    now = time.time()
    if cached is not None and now - cached[0] < config.CACHE_TTL_SECONDS:
        return cached[1]

    history = _download(symbol, window)
    if history is None:
        if not config.ALLOW_SYNTHETIC_FALLBACK:
            raise DataUnavailableError(
                f"No market data available for {symbol}. "
                "The upstream provider did not return any rows."
            )
        history = _synthetic(symbol, window)

    _cache[key] = (now, history)
    return history


def clear_cache() -> None:
    _cache.clear()


def normalize_ticker(ticker: str) -> str:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        raise ValueError("Ticker must not be empty.")
    if len(symbol) > 15 or not all(c.isalnum() or c in ".-^=" for c in symbol):
        raise ValueError(f"Ticker {ticker!r} is not a valid symbol.")
    return symbol


def _download(symbol: str, period: str) -> PriceHistory | None:
    """Fetch history from Yahoo Finance; ``None`` when unavailable."""
    try:
        import yfinance as yf

        raw = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    except Exception:
        return None
    if raw is None or raw.empty or "Close" not in raw:
        return None

    frame = pd.DataFrame(
        {
            "close": pd.to_numeric(raw["Close"], errors="coerce"),
            "volume": pd.to_numeric(raw.get("Volume", 0), errors="coerce").fillna(0.0),
        },
        index=pd.DatetimeIndex(raw.index).tz_localize(None).normalize(),
    ).dropna(subset=["close"])
    if len(frame) < 120:
        return None
    return PriceHistory(ticker=symbol, period=period, frame=frame, source="yahoo")


def _synthetic(symbol: str, period: str) -> PriceHistory:
    """Deterministic geometric-random-walk series, seeded from the symbol.

    Keeps the product demoable when the live provider is blocked, while making
    the substitution explicit through ``PriceHistory.source``.
    """
    days = _PERIOD_TO_DAYS.get(period, 504)
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    start_price = 40.0 + (seed % 260)
    drift = 0.0003 + ((seed % 7) - 3) * 0.00005
    volatility = 0.012 + (seed % 5) * 0.002
    shocks = rng.normal(drift, volatility, days)
    # Mild momentum so the series has learnable structure rather than pure noise.
    momentum = pd.Series(shocks).ewm(span=10).mean().to_numpy() * 0.35
    closes = start_price * np.exp(np.cumsum(shocks + momentum))

    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    frame = pd.DataFrame(
        {
            "close": closes,
            "volume": rng.integers(1_000_000, 9_000_000, days).astype(float),
        },
        index=index,
    )
    return PriceHistory(ticker=symbol, period=period, frame=frame, source="synthetic")
