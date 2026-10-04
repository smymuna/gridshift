from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from gridshift.domain.models import IntensityPoint, IntensitySeries

FIXTURES = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
QUARTER = timedelta(minutes=15)


def make_series(
    values: Sequence[float | None],
    *,
    zone: str = "de",
    start: datetime = T0,
    resolution: timedelta = QUARTER,
    forecast_from: int | None = None,
) -> IntensitySeries:
    """Build a series; ``None`` values become gaps."""
    points = tuple(
        IntensityPoint(
            start=start + i * resolution,
            gco2_per_kwh=v,
            is_forecast=forecast_from is not None and i >= forecast_from,
        )
        for i, v in enumerate(values)
        if v is not None
    )
    return IntensitySeries(zone=zone, resolution=resolution, points=points, fetched_at=start)


@pytest.fixture
def fr_payload() -> dict[str, Any]:
    """Real /co2eq?country=fr response captured on 2026-10-04."""
    data: dict[str, Any] = json.loads((FIXTURES / "co2eq_fr.json").read_text())
    return data
