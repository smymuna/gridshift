# ADR 0002: Window search with a prefix integral

- Status: accepted
- Date: 2026-10-04

## Context

Given a series of n intensity values at fixed resolution (15 min), a job of duration d, an
earliest start and a deadline, find the start time with the lowest average intensity.

Details that make the naive version wrong:

1. "Now" is rarely on a 15-minute boundary. A job starting at 10:07 runs 8 minutes in the
   10:00 interval, not 15.
2. Durations are not always multiples of the resolution (a 20-minute job).
3. The series can have gaps (missing values). A window must not silently bridge a gap.

## Decision

- Split the series into gap-free runs.
- For each run, build a prefix integral `P[i] = sum(v[j] * step for j < i)`. The integral up
  to any time t inside the run is `P[i] + v[i] * (t - start_i)`, so the **time-weighted**
  average over any interval `[s, e)` costs O(1).
- Only a small set of start times can be optimal. Intensity is constant inside an
  interval, so while neither the start nor the end of the window crosses a boundary, the
  average changes **linearly** with the start time, and a linear function is smallest at
  an end of its range. The candidates are therefore:
  - the earliest allowed start and the latest one (`deadline - duration`),
  - every interval boundary (window *starts* on a boundary),
  - every boundary minus the duration (window *ends* on a boundary).
- Ties go to the earliest start, so a job is never delayed for no gain.

Total cost is O(n log n) per zone because of sorting the candidates. With 2 days of
15-minute data, n is about 200, so speed is not the issue. The reason for this design is
correctness on unaligned starts, partial intervals and deadlines.

### A mistake caught on the way

The first version only tried starts on interval boundaries. That is wrong when the
duration is not a multiple of the resolution: for intensities `[800, 100, 900]` and a
20-minute job, starting at 0:10 (ending on the 0:30 boundary) averages 275 g, while the
best boundary start averages 300 g. The end-aligned candidates fix this, and a test now
checks this exact case.

## Verification

`tests/test_scheduler.py` checks hand-written edge cases (gaps, unaligned start,
non-multiple duration, end-aligned optimum, unaligned deadline, ties). It also compares
results against two brute-force searches on random series with gaps: one over interval
starts (200 cases) and one over every whole-minute start with random durations, earliest
starts and deadlines (300 cases).
