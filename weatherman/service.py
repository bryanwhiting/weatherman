from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, ETS

from .models import ForecastRequest

FREQ_MAP = {
    "15m": "15min",
    "30m": "30min",
    "1h": "h",
    "4h": "4h",
    "1d": "D",
    "1w": "W",
}

MODEL_NAMES = ["AutoARIMA", "ETS"]


@dataclass
class ForecastResult:
    history: pd.DataFrame
    forecast: pd.DataFrame
    backend: str
    backtest: pd.DataFrame


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = (np.abs(y_true) + np.abs(y_pred))
    mask = denom != 0
    if not mask.any():
        return 0.0
    return float(200 * np.mean(np.abs(y_true[mask] - y_pred[mask]) / denom[mask]))


def _build_history(req: ForecastRequest) -> pd.DataFrame:
    start = datetime.fromisoformat(req.start_datetime)
    freq = FREQ_MAP[req.granularity]
    ds = pd.date_range(start=start, periods=len(req.series), freq=freq)
    return pd.DataFrame({"unique_id": req.series_name, "ds": ds, "y": req.series})


def _load_m5_history(req: ForecastRequest) -> pd.DataFrame:
    from datasetsforecast.m5 import M5

    m5_dir = "./.cache/m5"
    y_df, *_ = M5.load(directory=m5_dir)
    if not {"unique_id", "ds", "y"}.issubset(set(y_df.columns)):
        raise RuntimeError("Unexpected M5 schema from datasetsforecast")

    ids = y_df["unique_id"].drop_duplicates().head(req.m5_series_count)
    df = y_df[y_df["unique_id"].isin(ids)].copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df = df.sort_values(["unique_id", "ds"])
    return df[["unique_id", "ds", "y"]]


def _forecast_nixtla_compare(
    df: pd.DataFrame,
    horizon: int,
    freq: str,
    do_backtest: bool,
    backtest_windows: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    models = [AutoARIMA(season_length=1), ETS(season_length=1)]

    backtest_df = pd.DataFrame(columns=["window", "model", "smape", "horizon", "holdout_start", "holdout_end"])
    if do_backtest:
        min_len = int(df.groupby("unique_id").size().min())
        max_possible_windows = max(0, (min_len // horizon) - 1)
        windows = max(1, min(backtest_windows, max_possible_windows)) if max_possible_windows > 0 else 0

        scores = []
        for w in range(windows):
            # Rolling holdout from older to newer windows
            offset = horizon * (windows - w)

            train_df = df.groupby("unique_id", group_keys=False).apply(lambda g: g.iloc[: len(g) - offset])
            holdout_df = df.groupby("unique_id", group_keys=False).apply(
                lambda g: g.iloc[len(g) - offset : len(g) - offset + horizon]
            )

            sf_bt = StatsForecast(models=models, freq=freq, n_jobs=1)
            bt_pred = sf_bt.forecast(df=train_df, h=horizon)
            merged = holdout_df.merge(bt_pred, on=["unique_id", "ds"], how="inner")
            if merged.empty:
                continue

            holdout_start = str(merged["ds"].min())
            holdout_end = str(merged["ds"].max())

            for model_name in MODEL_NAMES:
                if model_name in merged.columns:
                    score = _smape(merged["y"].to_numpy(dtype=float), merged[model_name].to_numpy(dtype=float))
                    scores.append(
                        {
                            "window": w + 1,
                            "model": model_name,
                            "smape": round(score, 4),
                            "horizon": horizon,
                            "holdout_start": holdout_start,
                            "holdout_end": holdout_end,
                        }
                    )
        backtest_df = pd.DataFrame(scores)

    sf = StatsForecast(models=models, freq=freq, n_jobs=1)
    fcst = sf.forecast(df=df, h=horizon)

    cols = [c for c in MODEL_NAMES if c in fcst.columns]
    long_fcst = fcst.melt(id_vars=["unique_id", "ds"], value_vars=cols, var_name="model", value_name="yhat")
    return long_fcst, backtest_df


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
    pred["model"] = "AutoGluon"
    return pred[["unique_id", "ds", "model", "yhat"]]


def forecast_from_request(req: ForecastRequest) -> ForecastResult:
    history = _load_m5_history(req) if req.use_m5 else _build_history(req)

    # infer frequency from history for M5, otherwise from request granularity
    if req.use_m5:
        first_id = history["unique_id"].iloc[0]
        first_series = history[history["unique_id"] == first_id].sort_values("ds")["ds"]
        freq = pd.infer_freq(first_series.iloc[: min(10, len(first_series))]) or "D"
    else:
        freq = FREQ_MAP[req.granularity]

    backend = req.model
    if backend == "auto":
        backend = "nixtla"

    if backend == "autogluon":
        forecast = _forecast_autogluon(history, req.horizon)
        backtest = pd.DataFrame(columns=["model", "smape", "horizon"])
    else:
        forecast, backtest = _forecast_nixtla_compare(
            history,
            req.horizon,
            freq,
            req.backtest,
            req.backtest_windows,
        )
        backend = "nixtla"

    return ForecastResult(history=history, forecast=forecast, backend=backend, backtest=backtest)
