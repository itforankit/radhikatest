# Running the app on your local machine

Step-by-step guide to get the AI Share Price Predictor running locally. Total time: ~3 minutes.

## 0. Prerequisites

| Requirement | Check |
| --- | --- |
| Python 3.10 or newer | `python3 --version` |
| pip + venv | `python3 -m venv --help` |
| git | `git --version` |
| Internet access | Needed for pip, Yahoo Finance data, and the Chart.js/Google Fonts CDN |

No database, Docker, or API key is required.

## 1. Get the code

```bash
git clone https://github.com/itforankit/radhikatest.git
cd radhikatest
```

## 2. Create a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now be prefixed with `(.venv)`. Everything below assumes the venv is active — if
you'd rather not activate it, prefix commands with `.venv/bin/` (macOS/Linux) or `.venv\Scripts\`
(Windows), e.g. `.venv/bin/uvicorn ...`.

## 3. Install dependencies

```bash
pip install -r requirements-dev.txt
```

This installs the runtime stack (FastAPI, uvicorn, pandas, numpy, scikit-learn, yfinance) plus the dev
tools (pytest, httpx, ruff). For runtime only, use `pip install -r requirements.txt`.

## 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

Leave this terminal running. `--reload` restarts the server whenever you edit a file.

## 5. Open the app

| URL | What it is |
| --- | --- |
| http://localhost:8000 | Dashboard (auto-runs a prediction for AAPL on load) |
| http://localhost:8000/docs | Interactive OpenAPI docs |
| http://localhost:8000/api/health | Health probe — should return `{"status":"ok",...}` |

Using the dashboard: type a ticker (or use a quick-pick button), choose a forecast horizon and
training window, then click **Run prediction**. You get four KPI cards (last close, target price,
expected change, directional accuracy), a history + forecast chart with an 80% confidence band, a
backtest chart of predicted vs actual over unseen sessions, and the top signal drivers.

## 6. Verify from the command line (optional)

```bash
curl "http://localhost:8000/api/health"
curl "http://localhost:8000/api/predict?ticker=MSFT&horizon=7&period=2y"
```

Check the `data_source` field in the response:

- `"yahoo"` — live market data.
- `"synthetic"` — Yahoo Finance was unreachable or rate-limited, so deterministic demo data was used
  instead. The dashboard shows a **"demo data (provider offline)"** badge in this case. This is
  expected behaviour, not a crash; see troubleshooting below.

## 7. Run the checks

```bash
pytest                      # 15 tests, no network access needed
ruff check .                # lint
ruff format --check .       # formatting
```

## 8. Stop the server

Press `Ctrl+C` in the terminal running uvicorn. Deactivate the venv with `deactivate`.

## Configuration (optional)

All settings are environment variables, read at startup:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPP_DEFAULT_TICKER` | `AAPL` | Ticker used when none is supplied |
| `SPP_DEFAULT_PERIOD` | `2y` | Default training window |
| `SPP_MAX_HORIZON` | `30` | Upper bound for `horizon` |
| `SPP_CACHE_TTL_SECONDS` | `900` | Price-history cache TTL |
| `SPP_ALLOW_SYNTHETIC_FALLBACK` | `1` | Set to `0` to return HTTP 502 instead of demo data |

Example:

```bash
SPP_DEFAULT_TICKER=NVDA SPP_ALLOW_SYNTHETIC_FALLBACK=0 uvicorn app.main:app --port 8000
```

## Troubleshooting

**Badge says "demo data (provider offline)" / `data_source` is `"synthetic"`.** Yahoo Finance
rejected the request — usually HTTP 429 (rate limiting), common on cloud IPs and VPNs. Wait a few
minutes, try from a home network, or set `SPP_ALLOW_SYNTHETIC_FALLBACK=0` to surface the error
instead of demo data.

**`ModuleNotFoundError: No module named 'app'`.** Run commands from the repo root (the directory
containing `app/`), not from inside `app/` or `tests/`.

**`Address already in use` on port 8000.** Another process holds the port. Use a different one
(`uvicorn app.main:app --port 8001`) or free it: `lsof -ti:8000 | xargs kill` (macOS/Linux).

**Charts don't render but KPI cards do.** Chart.js is loaded from `cdn.jsdelivr.net`; a blocked CDN or
offline machine prevents chart rendering. Check the browser console.

**`Not enough history to train a model` (HTTP 422).** The symbol has fewer than ~200 usable sessions
(newly listed or delisted). Pick a longer `period` or a different ticker.

**`Ticker '...' is not a valid symbol` (HTTP 400).** Only letters, digits and `. - ^ =` are accepted,
max 15 characters — e.g. `AAPL`, `RELIANCE.NS`, `^GSPC`.
