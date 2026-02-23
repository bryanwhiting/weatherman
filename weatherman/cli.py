from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ForecastRequest
from .service import forecast_from_request


def _save_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="ForecastingAPI forecast runner")
    parser.add_argument("--input", required=True, help="Path to request JSON")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    args = parser.parse_args()

    req_data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    req = ForecastRequest(**req_data)
    result = forecast_from_request(req)

    payload = {
        "request": req.model_dump(),
        "backend": result.backend,
        "history": result.history.to_dict(orient="records"),
        "forecast": result.forecast.to_dict(orient="records"),
        "backtest": result.backtest.to_dict(orient="records"),
        "backtest_points": result.backtest_points.to_dict(orient="records"),
    }
    _save_payload(Path(args.output), payload)


if __name__ == "__main__":
    main()
