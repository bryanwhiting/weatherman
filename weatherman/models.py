from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Granularity = Literal["15m", "30m", "1h", "4h", "1d", "1w"]


class ForecastRequest(BaseModel):
    run_name_root: str = Field("my-forecast-run", min_length=1)
    start_datetime: str = Field("2026-01-01T00:00:00", description="ISO datetime for first observation")
    granularity: Granularity = Field("1d", description="Frequency of series")
    seasonal_period: int | None = Field(None, ge=2, le=366, description="Optional seasonal cycle length")
    backtest_windows: int = Field(3, ge=1, le=20)
    horizon: int = Field(24, ge=1, le=1000)

    series_names: list[str] = Field(default_factory=lambda: ["series_1"])
    series_data: list[float] | list[list[float]] = Field(default_factory=list, description="Observed values")

    # Backward compatibility with older payload keys.
    series: list[float] | list[list[float]] | None = None
    series_name: str | None = None

    model: Literal["nixtla", "autogluon", "auto"] = "auto"
    use_m5: bool = False
    m5_series_count: int = Field(3, ge=1, le=20)
    compare_algorithms: bool = True
    backtest: bool = True

    @field_validator("series_data")
    @classmethod
    def no_nulls(cls, v):
        if not isinstance(v, list):
            raise ValueError("series_data must be a list")

        def is_real_number(x):
            return isinstance(x, (int, float)) and not isinstance(x, bool)

        for item in v:
            if item is None:
                raise ValueError("series_data cannot contain nulls")
            if isinstance(item, list):
                for x in item:
                    if x is None:
                        raise ValueError("series_data cannot contain nulls")
                    if not is_real_number(x):
                        raise ValueError("series_data must contain only real numeric datapoints")
            else:
                if not is_real_number(item):
                    raise ValueError("series_data must contain only real numeric datapoints")
        return v

    @model_validator(mode="after")
    def validate_source(self) -> "ForecastRequest":
        # normalize legacy keys
        if (not self.series_data) and self.series is not None:
            self.series_data = self.series
        if self.series_name and not self.series_names:
            self.series_names = [self.series_name]

        if self.use_m5:
            self.series_names = ["demo_mode_m5"]
            return self

        if any(name == "demo_mode_m5" for name in self.series_names):
            raise ValueError('series_names cannot include "demo_mode_m5" outside demo mode')

        if len(self.series_data) == 0:
            raise ValueError("series_data must contain values when use_m5=false")

        if isinstance(self.series_data[0], list):
            for idx, ser in enumerate(self.series_data, start=1):
                if len(ser) < 10:
                    raise ValueError(f"series_data[{idx}] must contain at least 10 points")
            if len(self.series_names) != len(self.series_data):
                raise ValueError("len(series_names) must equal len(series_data)")
        else:
            if len(self.series_data) < 10:
                raise ValueError("series_data must contain at least 10 points")
            if len(self.series_names) != 1:
                raise ValueError("single-series payload must provide exactly one series_name")

        return self
