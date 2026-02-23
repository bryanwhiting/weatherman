# Weatherman

Weatherman is an open-source forecasting project with **two separate parts in one repo**:

- `weatherman/` → Python forecasting engine (Nixtla StatsForecast first)
- `site/` → Astro + Tailwind web app (submit payloads, track jobs, view reports)

## Architecture

### 1) Python forecasting package (`weatherman/`)
Input payload is compact:
- `run_name_root`
- `start_datetime`
- `granularity`
- `horizon`
- `series_names` (list)
- `series` (single list or list-of-lists)
- `n_series`
- `backtest_windows`

The engine builds continuous timestamps (no gaps), trains models, and forecasts after the last point.

Current backend: **Nixtla StatsForecast** (AutoARIMA + AutoETS) with rolling backtesting + SMAPE.

### 2) Astro website (`site/`)
- Landing page (`/`) for payload submission + run status
- Forecast pages (`/forecasts/[slug]`) generated from JSON artifacts
- Per-series charts + backfill accuracy views

---

## Environment setup

Create local env file from template:

```bash
cp .env.example .env.local
```

Fill values in `.env.local` (never commit real secrets).

---

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

---

## Deploy (GitHub + Cloudflare Pages)

### 1) Push repo
```bash
git push origin main
```

### 2) Create Cloudflare Pages project
Project name used here: `weatherman`

### 3) Set GitHub repo secrets
In `bryanwhiting/weatherman` → Settings → Secrets and variables → Actions:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

### 4) Set Cloudflare Pages Function secrets
In Cloudflare Pages project (`weatherman`) → Settings → Environment variables / secrets:

- `GITHUB_TOKEN` (PAT with repo/workflow permissions)
- `ALLOWED_REPO` (e.g. `bryanwhiting/weatherman`)

### 5) Enable workflows
Workflows used:
- `Forecast Request` (build artifacts + commit + deploy)
- `Deploy Astro site to GitHub Pages` (optional if you keep GH Pages as mirror)

### 6) Trigger a forecast
Use app UI or run workflow dispatch with payload.

---

## Notes

- `demo_mode_m5` is reserved for demo runs.
- Backtests require enough history (`horizon * windows + train span`).
- For concurrent runs, workflow uses retry + rebase push logic.
