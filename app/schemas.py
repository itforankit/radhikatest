"""Response models for the prediction API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HistoryPoint(BaseModel):
    date: str
    close: float


class ForecastPoint(BaseModel):
    date: str
    predicted_close: float
    lower: float
    upper: float


class BacktestPoint(BaseModel):
    date: str
    actual: float
    predicted: float


class MetricsModel(BaseModel):
    mae: float
    rmse: float
    mape: float
    directional_accuracy: float
    r2: float
    holdout_days: int


class PredictionResponse(BaseModel):
    ticker: str
    period: str
    data_source: str = Field(description="'yahoo' for live data, 'synthetic' for offline demo data")
    horizon: int
    last_close: float
    last_date: str
    target_price: float
    expected_change_pct: float
    trend: str
    model_name: str
    metrics: MetricsModel
    history: list[HistoryPoint]
    forecast: list[ForecastPoint]
    backtest: list[BacktestPoint]
    feature_importance: dict[str, float]


class HealthResponse(BaseModel):
    status: str
    version: str
