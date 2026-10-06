/** Minimal linear scale and "nice" ticks: all these charts need, without a chart library. */

export type Scale = ((v: number) => number) & { invert: (px: number) => number }

export function linearScale(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain
  const [r0, r1] = range
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  const f = ((v: number) => r0 + (v - d0) * k) as Scale
  f.invert = (px: number) => (k === 0 ? d0 : d0 + (px - r0) / k)
  return f
}

/** Round step sizes: 1, 2, 2.5, 5 × 10^n, giving about `count` ticks. */
export function niceStep(span: number, count: number): number {
  if (span <= 0 || !Number.isFinite(span)) return 1
  const raw = span / Math.max(1, count)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / mag
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10
  return nice * mag
}

export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return niceTicks(min - (Math.abs(min) || 1), max + (Math.abs(max) || 1), count)
  const step = niceStep(max - min, count)
  const start = Math.floor(min / step) * step
  const end = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Number(v.toFixed(10)))
  return ticks
}

const HOUR = 3_600_000

/** Hour ticks on round local hours, spaced so labels don't crowd. */
export function timeTicks(startMs: number, endMs: number, maxTicks: number): number[] {
  const spanH = (endMs - startMs) / HOUR
  const stepH = [1, 2, 3, 6, 12, 24].find((s) => spanH / s <= maxTicks) ?? 24
  const first = new Date(startMs)
  first.setMinutes(0, 0, 0)
  if (first.getTime() < startMs) first.setHours(first.getHours() + 1)
  while (first.getHours() % stepH !== 0) first.setHours(first.getHours() + 1)
  const ticks: number[] = []
  for (let t = first.getTime(); t <= endMs; t += stepH * HOUR) ticks.push(t)
  return ticks
}
