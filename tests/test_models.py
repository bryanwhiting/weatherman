from weatherman.models import ForecastRequest


def test_request_valid():
    req = ForecastRequest(
        start_datetime="2026-01-01T17:15:00",
        granularity="1h",
        series=[1.0] * 12,
        horizon=12,
    )
    assert req.horizon == 12
