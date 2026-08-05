import numpy as np
import pytest

from app.features import FEATURE_COLUMNS, TARGET_COLUMN, build_features, build_training_frame


def test_build_features_returns_all_columns(sample_frame):
    features = build_features(sample_frame)
    assert list(features.columns) == FEATURE_COLUMNS
    assert len(features) == len(sample_frame)


def test_features_are_finite_after_warmup(sample_frame):
    features = build_features(sample_frame).dropna()
    assert len(features) > 300
    assert np.isfinite(features.to_numpy()).all()


def test_training_target_is_next_day_log_return(sample_frame):
    training = build_training_frame(sample_frame)
    closes = sample_frame["close"]
    first_date = training.index[0]
    position = closes.index.get_loc(first_date)
    expected = np.log(closes.iloc[position + 1] / closes.iloc[position])
    assert training[TARGET_COLUMN].iloc[0] == pytest.approx(float(expected))
    assert not training.isna().to_numpy().any()
