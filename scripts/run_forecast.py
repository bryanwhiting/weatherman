from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _load_index(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_index(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, help="JSON payload string")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--use-m5", action="store_true")
    parser.add_argument("--m5-series-count", type=int, default=3)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    tmp_dir = root / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    request_obj = json.loads(args.payload) if args.payload.strip() else {}
    if args.use_m5:
        request_obj["use_m5"] = True
        request_obj.setdefault("m5_series_count", args.m5_series_count)
        request_obj.setdefault("series_name", "m5_sample")
        request_obj.setdefault("granularity", "1d")
    request_obj.setdefault("compare_algorithms", True)
    request_obj.setdefault("backtest", True)
    request_path = tmp_dir / f"{args.slug}.request.json"
    output_path = root / "site" / "src" / "data" / "forecasts" / f"{args.slug}.json"
    index_path = root / "site" / "src" / "data" / "forecast-index.json"

    request_path.write_text(json.dumps(request_obj, indent=2), encoding="utf-8")

    subprocess.run(
        [
            "python",
            "-m",
            "weatherman.cli",
            "--input",
            str(request_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    run_at = datetime.now(timezone.utc).isoformat()
    result["meta"] = {
        "slug": args.slug,
        "created_at": run_at,
        "github": {
            "repo": args.repo,
            "run_id": args.run_id,
            "actor": args.actor,
            "sha": args.sha,
            "run_url": f"https://github.com/{args.repo}/actions/runs/{args.run_id}" if args.repo and args.run_id else "",
        },
        "history_points": len(result.get("history", [])),
        "forecast_points": len(result.get("forecast", [])),
    }
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    index = _load_index(index_path)
    index = [x for x in index if x.get("slug") != args.slug]
    index.append(
        {
            "slug": args.slug,
            "title": result["request"].get("series_name", args.slug),
            "created_at": run_at,
            "granularity": result["request"].get("granularity"),
            "horizon": result["request"].get("horizon"),
            "history_points": len(result.get("history", [])),
            "forecast_points": len(result.get("forecast", [])),
            "backend": result.get("backend", "nixtla"),
            "run_url": result["meta"]["github"].get("run_url", ""),
            "path": f"/forecasts/{args.slug}",
        }
    )
    index.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    _save_index(index_path, index)


if __name__ == "__main__":
    main()
