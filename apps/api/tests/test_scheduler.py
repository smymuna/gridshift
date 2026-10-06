from __future__ import annotations

import random
from datetime import timedelta

import pytest

from gridshift.domain.scheduler import (
    NoFeasibleWindowError,
    best_window,
    recommend,
    run_now_window,
)
from tests.conftest import QUARTER, T0, make_series

HOUR = timedelta(hours=1)


def test_picks_lowest_average_window() -> None:
    s = make_series([500, 400, 100, 120, 300, 600])
    w = best_window(
        s, duration=30 * timedelta(minutes=1), earliest_start=T0, deadline=T0 + HOUR * 2
    )
    assert w.start == T0 + 2 * QUARTER
    assert w.end == T0 + 4 * QUARTER
    assert w.avg_gco2_per_kwh == pytest.approx(110)


def test_ties_prefer_earliest_start() -> None:
    s = make_series([200, 100, 100, 200, 100, 100])
    w = best_window(s, duration=2 * QUARTER, earliest_start=T0, deadline=T0 + 6 * QUARTER)
    assert w.start == T0 + QUARTER


def test_respects_deadline() -> None:
    s = make_series([300, 300, 300, 50, 50])
    w = best_window(s, duration=2 * QUARTER, earliest_start=T0, deadline=T0 + 3 * QUARTER)
    assert w.end <= T0 + 3 * QUARTER
    assert w.avg_gco2_per_kwh == pytest.approx(300)


def test_window_never_spans_a_data_gap() -> None:
    # The two lowest values sit on either side of a gap; that window must be rejected.
    s = make_series([400, 10, None, 10, 400, 400])
    w = best_window(s, duration=2 * QUARTER, earliest_start=T0, deadline=T0 + 6 * QUARTER)
    assert w.avg_gco2_per_kwh == pytest.approx(205)


def test_unaligned_start_is_time_weighted() -> None:
    # Start 5 min into a 100 g interval; the 15 min job spends 10 min there and 5 min at 400 g.
    s = make_series([100, 400])
    now = T0 + timedelta(minutes=5)
    w = run_now_window(s, duration=QUARTER, now=now)
    assert w is not None
    assert w.start == now
    assert w.avg_gco2_per_kwh == pytest.approx((100 * 10 + 400 * 5) / 15)


def test_duration_not_multiple_of_resolution() -> None:
    s = make_series([100, 100, 400])
    w = best_window(s, duration=timedelta(minutes=20), earliest_start=T0, deadline=T0 + HOUR)
    assert w.start == T0
    assert w.avg_gco2_per_kwh == pytest.approx(100)


def test_uses_forecast_flag() -> None:
    s = make_series([500, 500, 100, 100], forecast_from=2)
    w = best_window(s, duration=2 * QUARTER, earliest_start=T0, deadline=T0 + HOUR)
    assert w.uses_forecast is True
    now = run_now_window(s, duration=2 * QUARTER, now=T0)
    assert now is not None
    assert now.uses_forecast is False


def test_infeasible_raises() -> None:
    s = make_series([100, 100])
    with pytest.raises(NoFeasibleWindowError):
        best_window(s, duration=HOUR, earliest_start=T0, deadline=T0 + 2 * HOUR)


def test_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="positive"):
        best_window(make_series([1, 2]), duration=timedelta(0), earliest_start=T0, deadline=T0)


def test_recommend_shifts_across_zones_and_reports_savings() -> None:
    de = make_series([700, 650, 600, 600], zone="de")
    fr = make_series([60, 55, 50, 70], zone="fr")
    rec = recommend([de, fr], duration=2 * QUARTER, now=T0, deadline=T0 + HOUR)
    assert rec.best.zone == "fr"
    assert rec.best.start == T0 + QUARTER
    assert rec.baseline is not None
    assert rec.baseline.zone == "de"
    assert rec.savings_pct == pytest.approx(round(100 * (675 - 52.5) / 675, 1))


def test_recommend_skips_zones_without_coverage() -> None:
    short = make_series([10], zone="nl")
    de = make_series([300, 200, 100, 100], zone="de")
    rec = recommend([de, short], duration=2 * QUARTER, now=T0, deadline=T0 + HOUR)
    assert rec.best.zone == "de"


def test_recommend_baseline_none_when_now_not_covered() -> None:
    s = make_series([100, 100, 100], start=T0 + HOUR)
    rec = recommend([s], duration=QUARTER, now=T0, deadline=T0 + 2 * HOUR)
    assert rec.baseline is None
    assert rec.savings_pct is None


def test_recommend_deadline_too_close() -> None:
    with pytest.raises(NoFeasibleWindowError):
        recommend([make_series([1, 1])], duration=HOUR, now=T0, deadline=T0 + QUARTER)


def test_matches_brute_force_on_random_series() -> None:
    rng = random.Random(42)
    for _ in range(200):
        n = rng.randint(4, 40)
        values = [rng.choice([None] + [rng.uniform(20, 800)] * 6) for _ in range(n)]
        s = make_series(values)
        k = rng.randint(1, 4)
        duration = k * QUARTER
        deadline = T0 + n * QUARTER
        brute = [
            sum(values[i : i + k]) / k  # type: ignore[arg-type]
            for i in range(n - k + 1)
            if all(v is not None for v in values[i : i + k])
        ]
        if not brute:
            with pytest.raises(NoFeasibleWindowError):
                best_window(s, duration=duration, earliest_start=T0, deadline=deadline)
            continue
        w = best_window(s, duration=duration, earliest_start=T0, deadline=deadline)
        assert w.avg_gco2_per_kwh == pytest.approx(min(brute))


def test_best_start_can_be_end_aligned() -> None:
    # 20 min job: starting at 0:10 (ending on the 0:30 boundary) gives
    # (800*5 + 100*15) / 20 = 275, better than any boundary-aligned start (best is 300).
    s = make_series([800, 100, 900])
    w = best_window(s, duration=timedelta(minutes=20), earliest_start=T0, deadline=T0 + HOUR)
    assert w.start == T0 + timedelta(minutes=10)
    assert w.avg_gco2_per_kwh == pytest.approx(275)


def test_best_window_can_end_exactly_at_an_unaligned_deadline() -> None:
    s = make_series([900, 100, 900, 900])
    deadline = T0 + timedelta(minutes=25)
    w = best_window(s, duration=timedelta(minutes=10), earliest_start=T0, deadline=deadline)
    assert w.end == deadline
    assert w.avg_gco2_per_kwh == pytest.approx(100)


def _minute_brute_force(
    values: list[float | None], duration_min: int, earliest_min: int, deadline_min: int
) -> float | None:
    """Try every whole-minute start. Exact here because all inputs are whole minutes."""
    per_minute = [v for v in values for _ in range(15)]
    best = None
    for s in range(earliest_min, deadline_min - duration_min + 1):
        chunk = per_minute[s : s + duration_min]
        if len(chunk) < duration_min or any(v is None for v in chunk):
            continue
        avg = sum(chunk) / duration_min  # type: ignore[arg-type]
        best = avg if best is None else min(best, avg)
    return best


def test_matches_minute_level_brute_force_with_unaligned_inputs() -> None:
    rng = random.Random(7)
    for _ in range(300):
        n = rng.randint(2, 16)
        values: list[float | None] = [
            None if rng.random() < 0.1 else float(rng.randint(20, 900)) for _ in range(n)
        ]
        duration_min = rng.randint(1, 50)
        earliest_min = rng.randint(0, 20)
        deadline_min = rng.randint(earliest_min, n * 15 + 10)
        expected = _minute_brute_force(values, duration_min, earliest_min, deadline_min)
        args = {
            "duration": timedelta(minutes=duration_min),
            "earliest_start": T0 + timedelta(minutes=earliest_min),
            "deadline": T0 + timedelta(minutes=deadline_min),
        }
        if expected is None:
            with pytest.raises(NoFeasibleWindowError):
                best_window(make_series(values), **args)  # type: ignore[arg-type]
        else:
            w = best_window(make_series(values), **args)  # type: ignore[arg-type]
            assert w.avg_gco2_per_kwh == pytest.approx(expected)
