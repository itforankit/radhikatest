import pytest
from fastapi.testclient import TestClient

from app import data
from app.main import app


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    """Force the deterministic synthetic provider so tests never hit the network."""
    data.clear_cache()
    monkeypatch.setattr(data, "_download", lambda symbol, period: None)
    yield
    data.clear_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_returns_full_payload(client):
    response = client.get("/api/predict", params={"ticker": "aapl", "horizon": 5, "period": "2y"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["ticker"] == "AAPL"
    assert payload["data_source"] == "synthetic"
    assert len(payload["forecast"]) == 5
    assert payload["history"]
    assert payload["backtest"]
    assert payload["trend"] in {"bullish", "bearish", "neutral"}
    assert payload["metrics"]["holdout_days"] > 0
    assert payload["target_price"] == payload["forecast"][-1]["predicted_close"]


def test_predict_is_deterministic_for_a_symbol(client):
    first = client.get("/api/predict", params={"ticker": "MSFT", "horizon": 3}).json()
    data.clear_cache()
    second = client.get("/api/predict", params={"ticker": "MSFT", "horizon": 3}).json()
    assert first["forecast"] == second["forecast"]


def test_horizon_out_of_range_is_rejected(client):
    assert client.get("/api/predict", params={"horizon": 999}).status_code == 422
    assert client.get("/api/predict", params={"horizon": 0}).status_code == 422


def test_invalid_ticker_is_rejected(client):
    response = client.get("/api/predict", params={"ticker": "not a ticker!"})
    assert response.status_code == 400


def test_dashboard_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Share Price Predictor" in response.text
