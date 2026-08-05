"""Runtime configuration, read from environment variables."""

import os

DEFAULT_TICKER = os.getenv("SPP_DEFAULT_TICKER", "AAPL")
DEFAULT_PERIOD = os.getenv("SPP_DEFAULT_PERIOD", "2y")
MAX_HORIZON = int(os.getenv("SPP_MAX_HORIZON", "30"))
CACHE_TTL_SECONDS = int(os.getenv("SPP_CACHE_TTL_SECONDS", "900"))
# When the market data provider is unreachable (offline demo, rate limits) the
# service falls back to a deterministic synthetic series instead of failing.
ALLOW_SYNTHETIC_FALLBACK = os.getenv("SPP_ALLOW_SYNTHETIC_FALLBACK", "1") == "1"
