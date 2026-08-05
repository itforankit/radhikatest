import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    """A trending price series long enough to train and backtest on."""
    rng = np.random.default_rng(7)
    days = 400
    shocks = rng.normal(0.0006, 0.011, days)
    closes = 100.0 * np.exp(np.cumsum(shocks))
    index = pd.bdate_range(end=pd.Timestamp("2025-01-31"), periods=days)
    return pd.DataFrame(
        {"close": closes, "volume": rng.integers(1_000_000, 5_000_000, days).astype(float)},
        index=index,
    )
