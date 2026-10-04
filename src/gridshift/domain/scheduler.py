"""Window search: find the lowest-carbon time (and zone) to run a job.

The series is split into gap-free runs. Over each run a prefix sum of
``intensity x time`` is built, so the time-weighted average intensity of any interval
is computed in O(1). Only O(n) candidate start times can be optimal (see
``_candidate_starts``), so a search is O(n log n) in the number of points.
See docs/adr/0002-window-search.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from gridshift.domain.models import IntensityPoint, IntensitySeries, Recommendation, Window


class NoFeasibleWindowError(Exception):
    """No window of the requested length fits between earliest start and deadline."""


@dataclass(frozen=True, slots=True)
class _Run:
    """Gap-free stretch of points with a prefix integral (gCO2/kWh x seconds)."""

    points: Sequence[IntensityPoint]
    resolution: timedelta
    prefix: Sequence[float]

    @classmethod
    def build(cls, points: Sequence[IntensityPoint], resolution: timedelta) -> _Run:
        step = resolution.total_seconds()
        prefix = [0.0]
        for p in points:
            prefix.append(prefix[-1] + p.gco2_per_kwh * step)
        return cls(points, resolution, prefix)

    @property
    def start(self) -> datetime:
        return self.points[0].start

    @property
    def end(self) -> datetime:
        return self.points[-1].start + self.resolution

    def _index(self, ts: datetime) -> tuple[int, float]:
        offset = (ts - self.start).total_seconds()
        step = self.resolution.total_seconds()
        i = int(offset // step)
        return i, offset - i * step

    def integral_to(self, ts: datetime) -> float:
        """Integral of intensity from the run start to ``ts`` (start <= ts <= end)."""
        i, frac = self._index(ts)
        if i >= len(self.points):
            return self.prefix[-1]
        return self.prefix[i] + self.points[i].gco2_per_kwh * frac

    def average(self, start: datetime, end: datetime) -> float:
        return (self.integral_to(end) - self.integral_to(start)) / (end - start).total_seconds()

    def any_forecast(self, start: datetime, end: datetime) -> bool:
        first, _ = self._index(start)
        last, frac = self._index(end)
        if frac == 0:
            last -= 1
        return any(p.is_forecast for p in self.points[first : last + 1])


def _runs(series: IntensitySeries) -> list[_Run]:
    groups: list[list[IntensityPoint]] = []
    for p in series.points:
        if groups and p.start - groups[-1][-1].start == series.resolution:
            groups[-1].append(p)
        else:
            groups.append([p])
    return [_Run.build(g, series.resolution) for g in groups]


def _candidate_starts(
    run: _Run, first: datetime, last: datetime, duration: timedelta
) -> list[datetime]:
    """Start times where the window average can be minimal, sorted.

    Intensity is constant inside each interval, so while neither the window start nor
    its end crosses an interval boundary, the average changes linearly with the start
    time. A linear function is smallest at an end of its range, so only these starts
    need checking: the bounds themselves, any start on a boundary, and any start whose
    *end* is on a boundary.
    """
    boundaries = [p.start for p in run.points] + [run.end]
    starts = {first, last}
    starts.update(b for b in boundaries if first <= b <= last)
    starts.update(b - duration for b in boundaries if first <= b - duration <= last)
    return sorted(starts)


def best_window(
    series: IntensitySeries,
    *,
    duration: timedelta,
    earliest_start: datetime,
    deadline: datetime,
) -> Window:
    """Lowest time-weighted average intensity window in one zone.

    Ties go to the earliest start, so the job is not delayed for no gain.
    """
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")

    best: Window | None = None
    for run in _runs(series):
        first = max(earliest_start, run.start)
        last = min(run.end, deadline) - duration
        if last < first:
            continue
        for start in _candidate_starts(run, first, last, duration):
            end = start + duration
            avg = run.average(start, end)
            if best is None or avg < best.avg_gco2_per_kwh - 1e-9:
                best = Window(
                    zone=series.zone,
                    start=start,
                    end=end,
                    avg_gco2_per_kwh=avg,
                    uses_forecast=run.any_forecast(start, end),
                )

    if best is None:
        raise NoFeasibleWindowError(
            f"no {duration} window in zone {series.zone!r} between "
            f"{earliest_start.isoformat()} and {deadline.isoformat()}"
        )
    return best


def run_now_window(series: IntensitySeries, *, duration: timedelta, now: datetime) -> Window | None:
    """The window you get by starting immediately, or None if the data does not cover it."""
    try:
        return best_window(series, duration=duration, earliest_start=now, deadline=now + duration)
    except NoFeasibleWindowError:
        return None


def recommend(
    series_by_zone: Iterable[IntensitySeries],
    *,
    duration: timedelta,
    now: datetime,
    deadline: datetime,
) -> Recommendation:
    """Best window across all zones (shifting in time and location).

    The baseline is "run now in the first zone given", which is normally where the job
    would run by default.
    """
    series_list = list(series_by_zone)
    if not series_list:
        raise ValueError("at least one zone is required")
    if deadline - now < duration:
        raise NoFeasibleWindowError("deadline is too close to fit the job")

    candidates: list[Window] = []
    for s in series_list:
        try:
            candidates.append(
                best_window(s, duration=duration, earliest_start=now, deadline=deadline)
            )
        except NoFeasibleWindowError:
            continue
    if not candidates:
        zones = ", ".join(s.zone for s in series_list)
        raise NoFeasibleWindowError(f"no feasible window in any zone ({zones})")

    best = min(candidates, key=lambda w: (round(w.avg_gco2_per_kwh, 6), w.start))
    baseline = run_now_window(series_list[0], duration=duration, now=now)
    return Recommendation(best=best, baseline=baseline)
