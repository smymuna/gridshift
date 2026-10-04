"""Core domain types. Pure data, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class IntensityPoint:
    """Average grid carbon intensity over one interval starting at ``start`` (UTC)."""

    start: datetime
    gco2_per_kwh: float
    is_forecast: bool


@dataclass(frozen=True, slots=True)
class IntensitySeries:
    """A time-ordered series of carbon intensity points for one bidding zone / country."""

    zone: str
    resolution: timedelta
    points: tuple[IntensityPoint, ...]
    fetched_at: datetime

    def __post_init__(self) -> None:
        starts = [p.start for p in self.points]
        if starts != sorted(starts):
            raise ValueError("points must be sorted by start time")
        if any(s.tzinfo is None for s in starts):
            raise ValueError("point timestamps must be timezone-aware")

    @property
    def horizon_end(self) -> datetime | None:
        """End of the last interval covered by the series."""
        if not self.points:
            return None
        return self.points[-1].start + self.resolution


@dataclass(frozen=True, slots=True)
class Window:
    """A contiguous run window and its average carbon intensity."""

    zone: str
    start: datetime
    end: datetime
    avg_gco2_per_kwh: float
    uses_forecast: bool


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Best window for a job, compared to running it immediately."""

    best: Window
    baseline: Window | None
    """Starting now in the first requested zone. None if there is not enough data to run now."""

    @property
    def savings_pct(self) -> float | None:
        if self.baseline is None or self.baseline.avg_gco2_per_kwh <= 0:
            return None
        saved = self.baseline.avg_gco2_per_kwh - self.best.avg_gco2_per_kwh
        return round(100 * saved / self.baseline.avg_gco2_per_kwh, 1)
