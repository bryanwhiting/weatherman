from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Granularity = Literal["15m", "30m", "1h", "4h", "1d", "1w"]


class ForecastRequest(BaseModel):
    start_datetime: str = Field("2026-01-01T00:00:00", description="ISO datetime for first observation")
    granularity: Granularity = Field("1d", description="Frequency of series")
    series: list[float] | list[list[float]] = Field(default_factory=list, description="Observed values")
    horizon: int = Field(24, ge=1, le=1000)
    model: Literal["nixtla", "autogluon", "auto"] = "auto"
    series_name: str = "series_1"

    use_m5: bool = False
    m5_series_count: int = Field(3, ge=1, le=20)
    compare_algorithms: bool = True
    backtest: bool = True
    backtest_windows: int = Field(3, ge=1, le=20)

    @field_validator("series")
    @classmethod
    def no_nulls(cls, v):
        if not isinstance(v, list):
            raise ValueError("series must be a list")
        for item in v:
            if item is None:
                raise ValueError("series cannot contain nulls")
            if isinstance(item, list):
                if any(x is None for x in item):
                    raise ValueError("series cannot contain nulls")
        return v

    @model_validator(mode="after")
    def validate_source(self) -> "ForecastRequest":
        if self.use_m5:
            self.series_name = "demo_mode_m5"
        else:
            if self.series_name == "demo_mode_m5":
                raise ValueError('series_name "demo_mode_m5" is reserved for demo mode')
            if len(self.series) == 0:
                raise ValueError("series must contain values when use_m5=false")
            if isinstance(self.series[0], list):
                for idx, ser in enumerate(self.series, start=1):
                    if len(ser) < 10:
                        raise ValueError(f"series[{idx}] must contain at least 10 points")
            else:
                if len(self.series) < 10:
                    raise ValueError("series must contain at least 10 points when use_m5=false")
        return self
