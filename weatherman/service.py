from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, AutoETS

from .models import ForecastRequest

FREQ_MAP = {
    "15m": "15min",
    "30m": "30min",
    "1h": "h",
    "4h": "4h",
    "1d": "D",
    "1w": "W",
}

MODEL_NAMES = ["AutoARIMA", "AutoETS"]


def _default_season_length(granularity: str) -> int:
    # Practical defaults. Daily data often has weekly seasonality.
    return {
        "15m": 96,
        "30m": 48,
        "1h": 24,
        "4h": 6,
        "1d": 7,
        "1w": 52,
    }.get(granularity, 7)


@dataclass
class ForecastResult:
    history: pd.DataFrame
    forecast: pd.DataFrame
    backend: str
    backtest: pd.DataFrame
    backtest_points: pd.DataFrame


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = (np.abs(y_true) + np.abs(y_pred))
    mask = denom != 0
    if not mask.any():
        return 0.0
    return float(200 * np.mean(np.abs(y_true[mask] - y_pred[mask]) / denom[mask]))


def _build_history(req: ForecastRequest) -> pd.DataFrame:
    start = datetime.fromisoformat(req.start_datetime)
    freq = FREQ_MAP[req.granularity]

    if len(req.series_data) == 0:
        return pd.DataFrame(columns=["unique_id", "ds", "y"])

    # Multi-series payload: series_data is list[list[number]]
    if isinstance(req.series_data[0], list):
        rows = []
        for idx, series_values in enumerate(req.series_data, start=1):
            ds = pd.date_range(start=start, periods=len(series_values), freq=freq)
            uid = req.series_names[idx - 1] if idx - 1 < len(req.series_names) else f"series_{idx}"
            rows.extend({"unique_id": uid, "ds": d, "y": float(y)} for d, y in zip(ds, series_values))
        return pd.DataFrame(rows)

    # Single-series payload
    ds = pd.date_range(start=start, periods=len(req.series_data), freq=freq)
    uid = req.series_names[0] if req.series_names else "series_1"
    return pd.DataFrame({"unique_id": uid, "ds": ds, "y": req.series_data})


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
    season_length: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    models = [AutoARIMA(season_length=season_length), AutoETS(season_length=season_length)]

    backtest_df = pd.DataFrame(columns=["unique_id", "window", "model", "smape", "horizon", "holdout_start", "holdout_end"])
    backtest_points_df = pd.DataFrame(columns=["unique_id", "window", "model", "ds", "y", "yhat"])
    if do_backtest:
        min_len = int(df.groupby("unique_id").size().min())
        max_possible_windows = max(0, (min_len // horizon) - 1)
        windows = max(1, min(backtest_windows, max_possible_windows)) if max_possible_windows > 0 else 0

        scores = []
        backtest_points = []
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

            for uid, uid_df in merged.groupby("unique_id"):
                holdout_start = str(uid_df["ds"].min())
                holdout_end = str(uid_df["ds"].max())

                for model_name in MODEL_NAMES:
                    if model_name in uid_df.columns:
                        score = _smape(uid_df["y"].to_numpy(dtype=float), uid_df[model_name].to_numpy(dtype=float))
                        scores.append(
                            {
                                "unique_id": uid,
                                "window": w + 1,
                                "model": model_name,
                                "smape": round(score, 4),
                                "horizon": horizon,
                                "holdout_start": holdout_start,
                                "holdout_end": holdout_end,
                            }
                        )
                        for _, r in uid_df.iterrows():
                            backtest_points.append(
                                {
                                    "unique_id": uid,
                                    "window": w + 1,
                                    "model": model_name,
                                    "ds": r["ds"],
                                    "y": float(r["y"]),
                                    "yhat": float(r[model_name]),
                                }
                            )
        backtest_df = pd.DataFrame(scores)
        backtest_points_df = pd.DataFrame(backtest_points)

    sf = StatsForecast(models=models, freq=freq, n_jobs=1)
    fcst = sf.forecast(df=df, h=horizon)

    cols = [c for c in MODEL_NAMES if c in fcst.columns]
    long_fcst = fcst.melt(id_vars=["unique_id", "ds"], value_vars=cols, var_name="model", value_name="yhat")
    return long_fcst, backtest_df, backtest_points_df


def _forecast_autogluon(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    try:
        from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("AutoGluon not installed. Install with: pip install 'forecastingapi[autogluon]'") from exc

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
        base_period = _default_season_length("1d")
    else:
        freq = FREQ_MAP[req.granularity]
        base_period = _default_season_length(req.granularity)

    # Cap season length so models always have enough points.
    min_len = int(history.groupby("unique_id").size().min()) if len(history) else 2
    season_length = req.seasonal_period or base_period
    season_length = max(2, min(int(season_length), max(2, min_len - 1)))

    backend = req.model
    if backend == "auto":
        backend = "nixtla"

    if backend == "autogluon":
        forecast = _forecast_autogluon(history, req.horizon)
        backtest = pd.DataFrame(columns=["model", "smape", "horizon"])
        backtest_points = pd.DataFrame(columns=["unique_id", "window", "model", "ds", "y", "yhat"])
    else:
        forecast, backtest, backtest_points = _forecast_nixtla_compare(
            history,
            req.horizon,
            freq,
            req.backtest,
            req.backtest_windows,
            season_length,
        )
        backend = "nixtla"

    return ForecastResult(history=history, forecast=forecast, backend=backend, backtest=backtest, backtest_points=backtest_points)
