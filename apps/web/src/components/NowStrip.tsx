'use client'

import { formatIntensity } from '@/lib/format'
import { type Sample, valueAt } from '@/lib/series'

export interface ZoneSeries {
  zone: string
  name: string
  slot: number
  samples: Sample[]
  resolutionMs: number
}

/** Current grid intensity per selected country, cleanest first. */
export function NowStrip({ series, nowMs }: { series: ZoneSeries[]; nowMs: number }) {
  const rows = series
    .map((s) => ({ s, cur: valueAt(s.samples, nowMs, s.resolutionMs) }))
    .sort((a, b) => (a.cur?.v ?? Infinity) - (b.cur?.v ?? Infinity))

  return (
    <ul
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
      aria-label="Grid carbon intensity right now"
    >
      {rows.map(({ s, cur }) => (
        <li key={s.zone} className="rounded-xl border border-line bg-surface px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-ink-2">
            <span
              aria-hidden="true"
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: `var(--series-${s.slot})` }}
            />
            {s.name}
          </div>
          <div className="tabular mt-1 text-xl font-semibold">
            {cur ? formatIntensity(cur.v) : '–'}
            <span className="text-sm font-normal text-ink-2"> CO₂/kWh</span>
          </div>
          <div className="text-xs text-muted">
            {cur ? (cur.forecast ? 'forecast for now' : 'measured') : 'no data for now'}
          </div>
        </li>
      ))}
    </ul>
  )
}
