"""FastAPI application exposing share price predictions and the dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__, config
from app.data import DataUnavailableError, get_price_history
from app.model import ModelError, forecast
from app.schemas import HealthResponse, PredictionResponse

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
MODEL_NAME = "Ridge regression on lagged returns + technical indicators"

app = FastAPI(
    title="AI Share Price Predictor",
    version=__version__,
    description="Technical-indicator machine learning forecasts for equity closing prices.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/api/predict", response_model=PredictionResponse)
def predict(
    ticker: str = Query(config.DEFAULT_TICKER, description="Equity symbol, e.g. AAPL or TCS.NS"),
    horizon: int = Query(7, ge=1, le=config.MAX_HORIZON, description="Sessions to forecast"),
    period: str = Query(config.DEFAULT_PERIOD, pattern="^(6mo|1y|2y|5y|10y|max)$"),
    history_points: int = Query(180, ge=30, le=2520),
) -> PredictionResponse:
    """Train on the requested window and return the forecast plus its backtest."""
    try:
        history = get_price_history(ticker, period)
        result = forecast(history.frame, horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ModelError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    last_close = history.last_close
    target = result.target_price
    change_pct = (target / last_close - 1.0) * 100.0
    recent = history.frame.tail(history_points)

    return PredictionResponse(
        ticker=history.ticker,
        period=history.period,
        data_source=history.source,
        horizon=horizon,
        last_close=round(last_close, 4),
        last_date=history.last_date.strftime("%Y-%m-%d"),
        target_price=round(target, 4),
        expected_change_pct=round(change_pct, 3),
        trend=_trend(change_pct),
        model_name=MODEL_NAME,
        metrics=result.metrics.as_dict(),
        history=[
            {"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 4)}
            for date, close in recent["close"].items()
        ],
        forecast=[
            {"date": date, "predicted_close": price, "lower": low, "upper": high}
            for date, price, low, high in zip(
                result.horizon_dates,
                result.horizon_prices,
                result.lower,
                result.upper,
                strict=True,
            )
        ],
        backtest=[
            {"date": date, "actual": actual, "predicted": predicted}
            for date, actual, predicted in zip(
                result.backtest.dates,
                result.backtest.actual,
                result.backtest.predicted,
                strict=True,
            )
        ],
        feature_importance=result.feature_importance,
    )


def _trend(change_pct: float) -> str:
    if change_pct > 1.0:
        return "bullish"
    if change_pct < -1.0:
        return "bearish"
    return "neutral"


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
