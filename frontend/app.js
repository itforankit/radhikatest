const els = {
  form: document.getElementById("controls"),
  ticker: document.getElementById("ticker"),
  horizon: document.getElementById("horizon"),
  period: document.getElementById("period"),
  submit: document.getElementById("submit"),
  error: document.getElementById("error"),
  badge: document.getElementById("source-badge"),
  modelName: document.getElementById("model-name"),
  metricsLine: document.getElementById("metrics-line"),
  last: document.getElementById("kpi-last"),
  lastDate: document.getElementById("kpi-last-date"),
  target: document.getElementById("kpi-target"),
  targetDate: document.getElementById("kpi-target-date"),
  change: document.getElementById("kpi-change"),
  trend: document.getElementById("kpi-trend"),
  direction: document.getElementById("kpi-direction"),
  holdout: document.getElementById("kpi-holdout"),
};

const charts = {};
const COLORS = {
  accent: "#4f7cff",
  accentSoft: "rgba(79, 124, 255, 0.18)",
  up: "#2fd08a",
  down: "#ff6b7d",
  amber: "#ffca6b",
  grid: "rgba(140, 158, 200, 0.14)",
  text: "#9aa8c7",
};

if (window.Chart) {
  Chart.defaults.color = COLORS.text;
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.maintainAspectRatio = false;
}

const money = (value) =>
  new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    value,
  );

function baseScales(yTitle) {
  return {
    x: { grid: { color: COLORS.grid }, ticks: { maxTicksLimit: 9, maxRotation: 0 } },
    y: {
      grid: { color: COLORS.grid },
      title: { display: Boolean(yTitle), text: yTitle },
      ticks: { callback: (value) => money(value) },
    },
  };
}

function render(id, config) {
  charts[id]?.destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

function renderForecastChart(data) {
  const labels = [...data.history.map((p) => p.date), ...data.forecast.map((p) => p.date)];
  const pad = new Array(data.history.length - 1).fill(null);
  const lastClose = data.history.at(-1).close;
  const line = (values) => [...pad, lastClose, ...values];

  render("chart-forecast", {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Actual close",
          data: data.history.map((p) => p.close),
          borderColor: COLORS.accent,
          backgroundColor: COLORS.accentSoft,
          borderWidth: 2,
          fill: true,
          pointRadius: 0,
          tension: 0.25,
        },
        {
          label: "Forecast",
          data: line(data.forecast.map((p) => p.predicted_close)),
          borderColor: data.expected_change_pct >= 0 ? COLORS.up : COLORS.down,
          borderWidth: 2.5,
          borderDash: [6, 4],
          pointRadius: 2,
          spanGaps: true,
        },
        {
          label: "Lower band",
          data: line(data.forecast.map((p) => p.lower)),
          borderColor: "rgba(154, 168, 199, 0.5)",
          borderWidth: 1,
          pointRadius: 0,
          spanGaps: true,
        },
        {
          label: "Upper band (80% interval)",
          data: line(data.forecast.map((p) => p.upper)),
          borderColor: "rgba(154, 168, 199, 0.5)",
          backgroundColor: "rgba(154, 168, 199, 0.12)",
          borderWidth: 1,
          pointRadius: 0,
          fill: "-1",
          spanGaps: true,
        },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { boxWidth: 12, usePointStyle: true } } },
      scales: baseScales("Price"),
    },
  });
}

function renderBacktestChart(data) {
  render("chart-backtest", {
    type: "line",
    data: {
      labels: data.backtest.map((p) => p.date),
      datasets: [
        {
          label: "Actual",
          data: data.backtest.map((p) => p.actual),
          borderColor: COLORS.accent,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
        },
        {
          label: "Predicted",
          data: data.backtest.map((p) => p.predicted),
          borderColor: COLORS.amber,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
        },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { boxWidth: 12, usePointStyle: true } } },
      scales: baseScales("Price"),
    },
  });
}

function renderFeatureChart(data) {
  const entries = Object.entries(data.feature_importance).slice(0, 8);
  render("chart-features", {
    type: "bar",
    data: {
      labels: entries.map(([name]) => name),
      datasets: [
        {
          label: "Weight",
          data: entries.map(([, weight]) => weight),
          backgroundColor: COLORS.accent,
          borderRadius: 6,
          barThickness: 16,
        },
      ],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { color: COLORS.grid },
          ticks: { callback: (value) => `${Math.round(value * 100)}%` },
        },
        y: { grid: { display: false } },
      },
    },
  });
}

function paintSummary(data) {
  const up = data.expected_change_pct >= 0;
  els.badge.textContent =
    data.data_source === "yahoo" ? "live market data" : "demo data (provider offline)";
  els.badge.className = `badge ${data.data_source === "yahoo" ? "badge-live" : "badge-demo"}`;
  els.modelName.textContent = `${data.ticker} · ${data.model_name}`;

  els.last.textContent = money(data.last_close);
  els.lastDate.textContent = `as of ${data.last_date}`;
  els.target.textContent = money(data.target_price);
  els.targetDate.textContent = `${data.horizon} sessions ahead · ${data.forecast.at(-1).date}`;
  els.change.textContent = `${up ? "+" : ""}${data.expected_change_pct.toFixed(2)}%`;
  els.change.className = `kpi-value ${up ? "up" : "down"}`;
  els.trend.textContent = `signal: ${data.trend}`;
  els.direction.textContent = `${data.metrics.directional_accuracy.toFixed(1)}%`;
  els.holdout.textContent = `${data.metrics.holdout_days} unseen sessions`;
  els.metricsLine.textContent = `MAE ${money(data.metrics.mae)} · RMSE ${money(
    data.metrics.rmse,
  )} · MAPE ${data.metrics.mape.toFixed(2)}%`;
}

async function runPrediction() {
  const params = new URLSearchParams({
    ticker: els.ticker.value.trim(),
    horizon: els.horizon.value,
    period: els.period.value,
  });
  els.error.hidden = true;
  els.submit.disabled = true;
  els.submit.textContent = "Predicting…";
  document.body.classList.add("loading");

  try {
    const response = await fetch(`/api/predict?${params}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed (${response.status})`);
    }
    paintSummary(payload);
    renderForecastChart(payload);
    renderBacktestChart(payload);
    renderFeatureChart(payload);
  } catch (error) {
    els.error.textContent = error.message;
    els.error.hidden = false;
    els.badge.textContent = "error";
    els.badge.className = "badge badge-demo";
  } finally {
    els.submit.disabled = false;
    els.submit.textContent = "Run prediction";
    document.body.classList.remove("loading");
  }
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  runPrediction();
});

document.querySelectorAll(".presets button").forEach((button) => {
  button.addEventListener("click", () => {
    els.ticker.value = button.dataset.ticker;
    runPrediction();
  });
});

runPrediction();
