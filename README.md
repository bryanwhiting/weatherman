# Weatherman

Weatherman is an open-source forecasting project with **two separate parts in one repo**:

- `weatherman/` → Python forecasting library (Nixtla StatsForecast first)
- `site/` → Astro website for landing page + per-run HTML reports

## Architecture

### 1) Python forecasting package (`weatherman/`)
Input payload stays small:
- `start_datetime` (first point timestamp)
- `granularity` (`15m`, `1h`, `1d`, ...)
- `series` (numeric values only)
- `horizon`

The library builds a continuous datetime index (no gaps), maps values to generated dates, trains models, and forecasts future points.

Initial backend: **Nixtla StatsForecast** (AutoARIMA + ETS), including **rolling backtests** with SMAPE.

### 2) Astro website (`site/`)
- Landing page (`/`) lists all submitted forecast requests from `site/src/data/forecast-index.json`
- Report page (`/forecasts/[slug]`) renders each run from `site/src/data/forecasts/<slug>.json`
- Report shows actual vs forecast chart (Chart.js) + run metadata

## GitHub Actions submission flow

Run workflow: **Forecast Request** (`workflow_dispatch`) with:
- `slug`
- `payload` (JSON)

The action:
1. Runs Python forecast generation
2. Writes `site/src/data/forecasts/<slug>.json`
3. Updates `site/src/data/forecast-index.json`
4. Commits and pushes

Astro then builds static pages from those artifacts.

## Example payload

```json
{
  "start_datetime": "2026-01-01T17:15:00",
  "granularity": "1h",
  "series_name": "demo_hourly",
  "horizon": 24,
  "model": "nixtla",
  "series": [100, 102, 99, 101, 103, 104, 106, 108, 110, 111]
}
```

## Local usage

### Python
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m weatherman.cli --input workflows/example_payload.json --output site/src/data/forecasts/demo.json
```

### Site
```bash
cd site
npm install
npm run build
```
