# AI Share Price Predictor

Machine learning forecasts of equity closing prices — a Python/FastAPI backend that trains a model
per request and a professional dashboard frontend that visualises the forecast, its confidence band,
a backtest against unseen sessions, and the signals driving the prediction.

> Educational project. Forecasts are statistical extrapolations of historical prices and are **not**
> investment advice.

## How it works

1. **Data** (`app/data.py`) — daily adjusted closes are pulled from Yahoo Finance via `yfinance` and
   cached in-process for 15 minutes. When the provider is unreachable or rate-limited, a
   deterministic synthetic series (seeded from the ticker) is used instead so the app stays
   demoable; the response labels this via `data_source: "synthetic"` and the UI shows a
   "demo data" badge.
2. **Features** (`app/features.py`) — 14 technical features: multi-horizon log returns, SMA ratios
   (5/10/20/50), rolling volatility, RSI(14), MACD histogram, Bollinger position, volume ratio.
3. **Model** (`app/model.py`) — a `StandardScaler` + `Ridge` pipeline predicts the **next-day log
   return** (stationary target). The last 20% of sessions are held out chronologically for
   backtesting (MAE, RMSE, MAPE, directional accuracy, R²); the final model is refit on all rows and
   rolled forward recursively for the requested horizon. The 80% band is the residual sigma widened
   by `sqrt(horizon)`.
4. **API + UI** (`app/main.py`, `frontend/`) — one JSON endpoint feeds a Chart.js dashboard with
   KPI cards, forecast chart, backtest chart, and feature-importance chart.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 for the dashboard, or http://localhost:8000/docs for the OpenAPI UI.

For a step-by-step walkthrough (prerequisites, Windows commands, verification, troubleshooting) see
[docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/health` | Liveness probe. |
| `GET /api/predict` | Forecast for a ticker. Query params: `ticker` (default `AAPL`), `horizon` (1–30 sessions, default 7), `period` (`6mo`/`1y`/`2y`/`5y`/`10y`/`max`, default `2y`), `history_points` (30–2520). |

```bash
curl "http://localhost:8000/api/predict?ticker=MSFT&horizon=7&period=2y"
```

Response (trimmed):

```json
{
  "ticker": "MSFT",
  "data_source": "yahoo",
  "horizon": 7,
  "last_close": 421.31,
  "target_price": 428.94,
  "expected_change_pct": 1.81,
  "trend": "bullish",
  "metrics": { "mae": 3.42, "rmse": 4.61, "mape": 0.87, "directional_accuracy": 53.2, "holdout_days": 78 },
  "history": [{ "date": "2024-01-02", "close": 370.87 }],
  "forecast": [{ "date": "2025-02-03", "predicted_close": 422.7, "lower": 415.1, "upper": 430.4 }],
  "backtest": [{ "date": "2024-10-01", "actual": 420.69, "predicted": 419.8 }],
  "feature_importance": { "rsi_14": 0.18 }
}
```

Errors: `400` invalid ticker, `422` history too short for training, `502` no data and synthetic
fallback disabled.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPP_DEFAULT_TICKER` | `AAPL` | Ticker used when none is supplied. |
| `SPP_DEFAULT_PERIOD` | `2y` | Default training window. |
| `SPP_MAX_HORIZON` | `30` | Upper bound for `horizon`. |
| `SPP_CACHE_TTL_SECONDS` | `900` | Price-history cache TTL. |
| `SPP_ALLOW_SYNTHETIC_FALLBACK` | `1` | Set to `0` to fail with `502` instead of serving demo data. |

## Development

```bash
ruff check .        # lint
ruff format .       # format
pytest              # tests (network-free: the provider is patched out)
```

## Layout

```
app/        FastAPI service: config, data access, features, model, schemas
frontend/   Dashboard (index.html, styles.css, app.js — Chart.js via CDN)
tests/      Feature, model and API tests
```
