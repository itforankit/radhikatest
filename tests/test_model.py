import pandas as pd
import pytest

from app.model import ModelError, forecast


def test_forecast_shapes_and_bands(sample_frame):
    result = forecast(sample_frame, horizon=7)
    assert len(result.horizon_prices) == 7
    assert len(result.horizon_dates) == 7
    bands = zip(result.lower, result.horizon_prices, result.upper, strict=True)
    assert all(low < price < high for low, price, high in bands)
    # Bands widen with the forecast horizon.
    widths = [high - low for low, high in zip(result.lower, result.upper, strict=True)]
    assert widths == sorted(widths)


def test_forecast_dates_are_future_business_days(sample_frame):
    result = forecast(sample_frame, horizon=5)
    dates = [pd.Timestamp(d) for d in result.horizon_dates]
    assert dates[0] > pd.Timestamp(sample_frame.index[-1])
    assert dates == sorted(dates)
    assert all(d.weekday() < 5 for d in dates)


def test_metrics_are_reported_on_unseen_holdout(sample_frame):
    result = forecast(sample_frame, horizon=3)
    metrics = result.metrics
    assert metrics.holdout_days > 10
    assert metrics.mae > 0
    assert metrics.rmse >= metrics.mae
    assert 0.0 <= metrics.directional_accuracy <= 100.0
    assert len(result.backtest.actual) == metrics.holdout_days


def test_feature_importance_is_normalized(sample_frame):
    weights = forecast(sample_frame, horizon=2).feature_importance
    assert pytest.approx(sum(weights.values()), abs=1e-3) == 1.0
    assert list(weights.values()) == sorted(weights.values(), reverse=True)


def test_short_history_raises_model_error(sample_frame):
    with pytest.raises(ModelError):
        forecast(sample_frame.head(90), horizon=3)


def test_invalid_horizon_raises(sample_frame):
    with pytest.raises(ValueError):
        forecast(sample_frame, horizon=0)
