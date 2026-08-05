---
name: testing-share-price-dashboard
description: How to run and end-to-end test the FastAPI + Chart.js share price predictor dashboard in this repo (local server, synthetic-data fallback, API invariants, deterministic expected values).
---

# Testing the share price predictor dashboard

## Running it locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # .venv usually already exists
.venv/bin/uvicorn app.main:app --port 8000
```
Dashboard: http://localhost:8000 · API: `/api/predict`, `/api/health` · OpenAPI: `/docs`.
No credentials or secrets are required. **Devin Secrets Needed:** none.

## Expect synthetic data, not live quotes
Yahoo Finance answers HTTP 429 from Devin VMs, so `app/data.py` falls back to a deterministic
per-symbol synthetic series and sets `data_source="synthetic"`. In the UI the top-right badge then
reads **"demo data (provider offline)"** instead of "live market data". This is correct behaviour —
assert on the badge rather than treating it as a failure. If you ever do get `data_source="yahoo"`,
the numeric expectations below will not hold.

## Getting expected values before touching the UI
The synthetic series is seeded from the ticker (`sha256(symbol)`), and the Ridge model is
deterministic, so `curl` the API first and use those exact numbers as pass/fail criteria for the
KPI cards. Values depend on both ticker **and** `period`, so query the same period the UI select
will use.

## Proving determinism (beware the cache)
`app/data.py` caches results for `SPP_CACHE_TTL_SECONDS` (default 900s), so re-running the same
ticker in the UI may just be a cache hit. To prove real determinism, start a **second uvicorn
process on another port** (fresh cache) and compare payload hashes:
```bash
.venv/bin/uvicorn app.main:app --port 8001 &
for p in 8000 8001; do curl -s "localhost:$p/api/predict?ticker=MSFT&horizon=30&period=5y" \
  | python3 -c "import json,sys,hashlib;d=json.load(sys.stdin);print(hashlib.sha256(json.dumps(d['forecast'],sort_keys=True).encode()).hexdigest()[:16])"; done
```

## Payload invariants worth asserting
- `len(backtest) == metrics.holdout_days`
- `lower < predicted_close < upper` for every forecast point
- forecast dates strictly increasing weekdays, all after `last_date`
- `sum(feature_importance.values()) ≈ 1.0`
- `expected_change_pct == (target_price/last_close - 1)*100`, and `trend` is bullish/bearish only
  when |change| > 1%, else neutral
- band spread grows like σ·√step, so day-N spread must be clearly larger than day-1

## UI interaction gotchas
- The `<select>` dropdowns (`#horizon`, `#period`) do not visibly open under xdotool clicks; click
  the select, then use `Down`/`Return` keys and confirm via `selectedindex` in the DOM.
- Quick-pick buttons only change the ticker — the currently selected horizon/period stay in effect.
- An empty ticker never reaches the API: the input has `required`, so Chrome shows
  "Please fill out this field." Test the empty-string API path with curl instead.
- Errors: invalid ticker → 400 with `detail` string shown in the red `#error` banner and badge
  text "error"; out-of-range `horizon`/`period` → FastAPI 422 with a `detail` **array** (the UI's
  `payload.detail` would then stringify oddly, so exercise those via the URL bar, not the form).
