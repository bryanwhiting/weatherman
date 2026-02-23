# Weatherman

Weatherman is an open-source forecasting package that provides a single interface over Nixtla and AutoGluon tooling.

## Core idea

You submit:
- `start_datetime` (first timestamp)
- `granularity` (`15m`, `1h`, `1d`, ...)
- `series` (numeric values only)

Weatherman generates a continuous datetime index with no gaps, maps each value to that index, and forecasts after the last observed point.

## Install

```bash
pip install -e .
# optional AutoGluon backend
pip install -e '.[autogluon]'
```

## Run locally

```bash
python -m weatherman.cli \
  --input workflows/example_payload.json \
  --output site/src/data/forecasts/demo.json
```

## GitHub Actions API

Use **Actions → Forecast Request → Run workflow** and pass:
- `slug`: output page slug
- `payload`: JSON blob

Example payload:

```json
{
  "start_datetime": "2026-01-01T17:15:00",
  "granularity": "1h",
  "series_name": "demo_hourly",
  "horizon": 24,
  "model": "nixtla",
  "series": [100, 102, 99, 101]
}
```

The workflow writes:
- `site/src/data/forecasts/<slug>.json`
- `site/src/pages/forecasts/<slug>.astro`

Then commits to `main`.

## Astro site

```bash
cd site
npm install
npm run build
```

Forecast page shows actual vs predicted values using Chart.js.
