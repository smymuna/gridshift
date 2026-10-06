import type { IntensityPoint } from '@gridshift/api-client'

export interface Sample {
  t: number // epoch ms, start of the interval
  v: number // gCO2/kWh
  forecast: boolean
}

export function toSamples(points: IntensityPoint[]): Sample[] {
  return points
    .map((p) => ({ t: Date.parse(p.start), v: p.gco2_per_kwh, forecast: p.is_forecast }))
    .sort((a, b) => a.t - b.t)
}

/** Value of the interval containing `t` (step function), or undefined outside the data. */
export function valueAt(samples: Sample[], t: number, resolutionMs: number): Sample | undefined {
  // samples are sorted; binary search for the last start <= t
  let lo = 0
  let hi = samples.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (samples[mid].t <= t) {
      found = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  if (found < 0) return undefined
  const s = samples[found]
  return t < s.t + resolutionMs ? s : undefined
}

/**
 * Time-weighted average intensity of a job running [start, start + duration).
 * Mirrors the API's calculation, so the chart's what-if tooltip agrees with the
 * recommendation. Returns undefined when the data doesn't cover the whole window.
 */
export function windowAverage(
  samples: Sample[],
  startMs: number,
  durationMs: number,
  resolutionMs: number,
): number | undefined {
  const end = startMs + durationMs
  let t = startMs
  let sum = 0
  while (t < end) {
    const s = valueAt(samples, t, resolutionMs)
    if (!s) return undefined
    const next = Math.min(end, s.t + resolutionMs)
    sum += s.v * (next - t)
    t = next
  }
  return sum / durationMs
}
