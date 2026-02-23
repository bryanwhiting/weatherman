from typing import Literal

from pydantic import BaseModel, Field, field_validator

Granularity = Literal["15m", "30m", "1h", "4h", "1d", "1w"]


class ForecastRequest(BaseModel):
    start_datetime: str = Field(..., description="ISO datetime for first observation")
    granularity: Granularity = Field(..., description="Frequency of series")
    series: list[float] = Field(..., min_length=10, description="Observed values")
    horizon: int = Field(24, ge=1, le=1000)
    model: Literal["nixtla", "autogluon", "auto"] = "auto"
    series_name: str = "series_1"

    @field_validator("series")
    @classmethod
    def no_nulls(cls, v: list[float]) -> list[float]:
        if any(x is None for x in v):
            raise ValueError("series cannot contain nulls")
        return v
