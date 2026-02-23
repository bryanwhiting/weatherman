from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, help="JSON payload string")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    tmp_dir = root / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    request_path = tmp_dir / f"{args.slug}.request.json"
    output_path = root / "site" / "src" / "data" / "forecasts" / f"{args.slug}.json"

    request_path.write_text(json.dumps(json.loads(args.payload), indent=2), encoding="utf-8")

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

    page_path = root / "site" / "src" / "pages" / "forecasts" / f"{args.slug}.astro"
    page_path.write_text(
        f"---\nimport ForecastPage from '../../layouts/ForecastPage.astro';\nimport data from '../../data/forecasts/{args.slug}.json';\n---\n<ForecastPage data={{data}} />\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
