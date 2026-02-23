from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, ETS

from .models import ForecastRequest

FREQ_MAP = {
    "15m": "15min",
    "30m": "30min",
    "1h": "H",
    "4h": "4H",
    "1d": "D",
    "1w": "W",
}


@dataclass
class ForecastResult:
    history: pd.DataFrame
    forecast: pd.DataFrame
    backend: str


def _build_history(req: ForecastRequest) -> pd.DataFrame:
    start = datetime.fromisoformat(req.start_datetime)
    freq = FREQ_MAP[req.granularity]
    ds = pd.date_range(start=start, periods=len(req.series), freq=freq)
    return pd.DataFrame({"unique_id": req.series_name, "ds": ds, "y": req.series})


def _forecast_nixtla(df: pd.DataFrame, horizon: int, freq: str) -> pd.DataFrame:
    sf = StatsForecast(models=[AutoARIMA(season_length=1), ETS(season_length=1)], freq=freq, n_jobs=1)
    fcst = sf.forecast(df=df, h=horizon)
    # Use AutoARIMA as primary prediction column for now
    value_col = "AutoARIMA" if "AutoARIMA" in fcst.columns else fcst.columns[-1]
    return fcst[["unique_id", "ds", value_col]].rename(columns={value_col: "yhat"})


def _forecast_autogluon(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    try:
        from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("AutoGluon not installed. Install with: pip install 'weatherman[autogluon]'") from exc

    ag_df = TimeSeriesDataFrame.from_data_frame(df, id_column="unique_id", timestamp_column="ds")
    predictor = TimeSeriesPredictor(prediction_length=horizon, target="y", eval_metric="MASE")
    predictor.fit(ag_df, presets="fast_training", time_limit=120)
    pred = predictor.predict(ag_df).reset_index()

    value_col = "mean" if "mean" in pred.columns else pred.columns[-1]
    pred = pred.rename(columns={"item_id": "unique_id", "timestamp": "ds", value_col: "yhat"})
    return pred[["unique_id", "ds", "yhat"]]


def forecast_from_request(req: ForecastRequest) -> ForecastResult:
    history = _build_history(req)
    freq = FREQ_MAP[req.granularity]

    backend = req.model
    if backend == "auto":
        backend = "nixtla"

    if backend == "autogluon":
        forecast = _forecast_autogluon(history, req.horizon)
    else:
        forecast = _forecast_nixtla(history, req.horizon, freq)
        backend = "nixtla"

    return ForecastResult(history=history, forecast=forecast, backend=backend)
