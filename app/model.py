"""Model training, backtesting and recursive multi-day forecasting."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.features import FEATURE_COLUMNS, TARGET_COLUMN, build_features, build_training_frame

MIN_TRAINING_ROWS = 80
HOLDOUT_FRACTION = 0.2
# 80% band around the recursive path (normal quantile).
BAND_Z = 1.2816


class ModelError(RuntimeError):
    """Raised when a model cannot be trained from the given history."""


@dataclass
class Metrics:
    """Backtest quality on a chronological holdout the model never saw."""

    mae: float
    rmse: float
    mape: float
    directional_accuracy: float
    r2: float
    holdout_days: int

    def as_dict(self) -> dict[str, float]:
        return {
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "mape": round(self.mape, 4),
            "directional_accuracy": round(self.directional_accuracy, 4),
            "r2": round(self.r2, 4),
            "holdout_days": self.holdout_days,
        }


@dataclass
class Backtest:
    """Predicted vs. actual closes over the holdout window."""

    dates: list[str]
    actual: list[float]
    predicted: list[float]


@dataclass
class ForecastResult:
    horizon_dates: list[str]
    horizon_prices: list[float]
    lower: list[float]
    upper: list[float]
    metrics: Metrics
    backtest: Backtest
    feature_importance: dict[str, float] = field(default_factory=dict)
    residual_sigma: float = 0.0

    @property
    def target_price(self) -> float:
        return self.horizon_prices[-1]


def _new_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("ridge", Ridge(alpha=1.0)),
        ]
    )


def forecast(frame: pd.DataFrame, horizon: int) -> ForecastResult:
    """Train on ``frame`` and roll the model forward ``horizon`` sessions."""
    if horizon < 1:
        raise ValueError("Horizon must be at least 1 day.")

    training = build_training_frame(frame)
    if len(training) < MIN_TRAINING_ROWS:
        raise ModelError(
            "Not enough history to train a model: "
            f"{len(training)} usable rows, {MIN_TRAINING_ROWS} required."
        )

    x_all = training[FEATURE_COLUMNS].to_numpy()
    y_all = training[TARGET_COLUMN].to_numpy()
    split = max(MIN_TRAINING_ROWS // 2, int(len(training) * (1.0 - HOLDOUT_FRACTION)))
    split = min(split, len(training) - 5)

    holdout_model = _new_pipeline().fit(x_all[:split], y_all[:split])
    holdout_pred_returns = holdout_model.predict(x_all[split:])
    metrics, backtest = _evaluate(
        frame=frame,
        dates=training.index[split:],
        predicted_returns=holdout_pred_returns,
        actual_returns=y_all[split:],
    )

    model = _new_pipeline().fit(x_all, y_all)
    residual_sigma = float(np.std(y_all - model.predict(x_all), ddof=1))
    dates, prices = _roll_forward(model, frame, horizon)

    steps = np.arange(1, horizon + 1)
    spread = BAND_Z * residual_sigma * np.sqrt(steps)
    prices_array = np.asarray(prices)

    return ForecastResult(
        horizon_dates=[d.strftime("%Y-%m-%d") for d in dates],
        horizon_prices=[round(p, 4) for p in prices],
        lower=[round(p, 4) for p in prices_array * np.exp(-spread)],
        upper=[round(p, 4) for p in prices_array * np.exp(spread)],
        metrics=metrics,
        backtest=backtest,
        feature_importance=_importance(model),
        residual_sigma=residual_sigma,
    )


def _roll_forward(
    model: Pipeline, frame: pd.DataFrame, horizon: int
) -> tuple[list[pd.Timestamp], list[float]]:
    """Predict one day ahead, append it to history, and repeat."""
    working = frame[["close", "volume"]].copy() if "volume" in frame else frame[["close"]].copy()
    dates: list[pd.Timestamp] = []
    prices: list[float] = []

    for _ in range(horizon):
        latest = build_features(working).dropna()
        if latest.empty:
            raise ModelError("Feature window is too short to forecast.")
        step_return = float(model.predict(latest.iloc[[-1]].to_numpy())[0])
        next_close = float(working["close"].iloc[-1] * np.exp(step_return))
        next_date = _next_business_day(pd.Timestamp(working.index[-1]))

        row = {"close": next_close}
        if "volume" in working:
            row["volume"] = float(working["volume"].iloc[-20:].mean())
        working.loc[next_date] = row

        dates.append(next_date)
        prices.append(next_close)

    return dates, prices


def _evaluate(
    frame: pd.DataFrame,
    dates: pd.DatetimeIndex,
    predicted_returns: np.ndarray,
    actual_returns: np.ndarray,
) -> tuple[Metrics, Backtest]:
    """Turn predicted next-day returns into price-space error metrics."""
    base_close = frame["close"].reindex(dates).astype(float).to_numpy()
    predicted_prices = base_close * np.exp(predicted_returns)
    actual_prices = base_close * np.exp(actual_returns)

    errors = predicted_prices - actual_prices
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    mape = float(np.mean(np.abs(errors / actual_prices)) * 100.0)
    direction = float(np.mean(np.sign(predicted_returns) == np.sign(actual_returns)) * 100.0)
    variance = float(np.sum((actual_prices - actual_prices.mean()) ** 2))
    r2 = float(1.0 - np.sum(errors**2) / variance) if variance > 0 else 0.0

    metrics = Metrics(
        mae=mae,
        rmse=rmse,
        mape=mape,
        directional_accuracy=direction,
        r2=r2,
        holdout_days=len(dates),
    )
    backtest = Backtest(
        dates=[pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates],
        actual=[round(p, 4) for p in actual_prices],
        predicted=[round(p, 4) for p in predicted_prices],
    )
    return metrics, backtest


def _importance(model: Pipeline) -> dict[str, float]:
    """Absolute standardized coefficients, normalized to sum to 1."""
    coefficients = np.abs(model.named_steps["ridge"].coef_)
    total = float(coefficients.sum())
    if total == 0.0:
        return {name: 0.0 for name in FEATURE_COLUMNS}
    weights = zip(FEATURE_COLUMNS, coefficients / total, strict=True)
    ranked = sorted(weights, key=lambda item: item[1], reverse=True)
    return {name: round(float(weight), 4) for name, weight in ranked}


def _next_business_day(date: pd.Timestamp) -> pd.Timestamp:
    nxt = date + pd.Timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    return nxt
