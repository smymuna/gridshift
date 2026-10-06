'use client'

import { type ChangeEvent, type PointerEvent, useMemo, useState } from 'react'
import { useWidth } from '@/hooks/useWidth'
import { formatIntensity, formatTime } from '@/lib/format'
import { linearScale, niceTicks, timeTicks } from '@/lib/scale'
import { type Sample, valueAt, windowAverage } from '@/lib/series'
import type { ZoneSeries } from './NowStrip'

interface Props {
  series: ZoneSeries[]
  nowMs: number
  deadlineMs: number | null
  durationMs: number
  best: { zone: string; startMs: number; endMs: number } | null
  height?: number
}

const M = { top: 28, right: 96, bottom: 30, left: 48 }
const PAST_MS = 3 * 3_600_000 // show the last three hours for context
const LABEL_GAP = 14

/** Line paths through interval starts, split into measured and forecast parts; gaps break the line. */
function paths(
  samples: Sample[],
  resolutionMs: number,
  x: (t: number) => number,
  y: (v: number) => number,
) {
  const out = { measured: '', forecast: '' }
  const pt = (s: Sample) => `${x(s.t).toFixed(1)},${y(s.v).toFixed(1)}`
  let prev: Sample | null = null
  for (const s of samples) {
    const key = s.forecast ? 'forecast' : 'measured'
    const consecutive = prev !== null && s.t - prev.t === resolutionMs
    if (consecutive && prev && prev.forecast === s.forecast) out[key] += `L${pt(s)}`
    else if (consecutive && prev)
      out[key] += `M${pt(prev)}L${pt(s)}` // join measured to forecast
    else out[key] += `M${pt(s)}`
    prev = s
  }
  return out
}

export function IntensityChart({
  series,
  nowMs,
  deadlineMs,
  durationMs,
  best,
  height = 340,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(760)
  const [hoverT, setHoverT] = useState<number | null>(null)
  const narrow = width < 560
  const margin = { ...M, right: narrow ? 16 : M.right, left: narrow ? 40 : M.left }

  const geo = useMemo(() => {
    const all = series.flatMap((s) => s.samples)
    const t0 = Math.max(Math.min(...all.map((s) => s.t)), nowMs - PAST_MS)
    const t1 = Math.max(...series.map((s) => (s.samples.at(-1)?.t ?? t0) + s.resolutionMs))
    const vMax = Math.max(1, ...all.filter((s) => s.t >= t0).map((s) => s.v))
    const yTicks = niceTicks(0, vMax, 4)
    const x = linearScale([t0, t1], [margin.left, width - margin.right])
    const y = linearScale([0, yTicks.at(-1) ?? vMax], [height - M.bottom, M.top])
    return { t0, t1, x, y, yTicks, xTicks: timeTicks(t0, t1, narrow ? 4 : 8) }
  }, [series, nowMs, width, height, margin.left, margin.right, narrow])

  const { t0, t1, x, y, yTicks, xTicks } = geo
  const step = Math.min(...series.map((s) => s.resolutionMs))

  const snap = (t: number) => Math.min(t1 - step, Math.max(t0, Math.round(t / step) * step))
  const onPointer = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    setHoverT(snap(x.invert(e.clientX - box.left)))
  }
  // Keyboard and screen-reader users explore time with a real slider, not a focusable image.
  const onScrub = (e: ChangeEvent<HTMLInputElement>) => setHoverT(snap(Number(e.target.value)))

  // End labels only where they don't collide; the legend always carries identity.
  const ends = useMemo(() => {
    if (narrow) return []
    const items = series
      .map((s) => {
        const last = s.samples.at(-1)
        return last ? { s, py: y(last.v), px: x(last.t) } : null
      })
      .filter((v): v is NonNullable<typeof v> => v !== null)
      .sort((a, b) => a.py - b.py)
    return items.every((it, i) => i === 0 || it.py - items[i - 1].py >= LABEL_GAP) ? items : []
  }, [series, x, y, narrow])

  const hover =
    hoverT === null
      ? []
      : series.map((s) => ({
          s,
          at: valueAt(s.samples, hoverT, s.resolutionMs),
          job: windowAverage(s.samples, hoverT, durationMs, s.resolutionMs),
        }))
  const tipX = hoverT === null ? 0 : x(hoverT)
  const tipLeft = tipX > width - 260 ? tipX - 250 : tipX + 14
  const plotBottom = height - margin.bottom

  return (
    <div ref={ref} className="relative">
      <ul
        className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2"
        aria-label="Legend"
      >
        {series.map((s) => (
          <li key={s.zone} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-[3px] w-4 rounded"
              style={{ background: `var(--series-${s.slot})` }}
            />
            {s.name}
          </li>
        ))}
        <li className="flex items-center gap-1.5 text-muted">
          <svg width="22" height="6" aria-hidden="true">
            <line
              x1="0"
              x2="22"
              y1="3"
              y2="3"
              stroke="var(--muted)"
              strokeWidth="2"
              strokeDasharray="4 3"
            />
          </svg>
          forecast
        </li>
        {best && (
          <li className="flex items-center gap-1.5 text-muted">
            <span
              aria-hidden="true"
              className="h-3 w-4 rounded-sm"
              style={{ background: 'var(--band)' }}
            />
            best window
          </li>
        )}
      </ul>

      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Grid carbon intensity over time per country"
        onPointerMove={onPointer}
        onPointerLeave={() => setHoverT(null)}
        className="block touch-pan-y overflow-visible"
      >
        {/* after the deadline: not available for this job */}
        {deadlineMs !== null && deadlineMs < t1 && (
          <rect
            x={x(Math.max(deadlineMs, t0))}
            y={margin.top}
            width={Math.max(0, x(t1) - x(Math.max(deadlineMs, t0)))}
            height={plotBottom - margin.top}
            fill="var(--grid)"
            opacity={0.45}
          />
        )}
        {best && (
          <g>
            <rect
              x={x(best.startMs)}
              y={margin.top}
              width={Math.max(2, x(best.endMs) - x(best.startMs))}
              height={plotBottom - margin.top}
              fill="var(--band)"
            />
            <text
              x={x(best.startMs) + 4}
              y={margin.top - 8}
              fontSize={12}
              fontWeight={600}
              fill="var(--ink)"
            >
              Best: {series.find((s) => s.zone === best.zone)?.name ?? best.zone.toUpperCase()}
            </text>
          </g>
        )}

        <g fontSize={11} fill="var(--muted)" className="tabular">
          {yTicks.map((t) => (
            <g key={t}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y(t)}
                y2={y(t)}
                stroke={t === 0 ? 'var(--axis)' : 'var(--grid)'}
              />
              <text x={margin.left - 8} y={y(t)} dy="0.32em" textAnchor="end">
                {t.toLocaleString()}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} x={x(t)} y={plotBottom + 18} textAnchor="middle">
              {formatTime(new Date(t), new Date(nowMs))}
            </text>
          ))}
        </g>

        {nowMs > t0 && nowMs < t1 && (
          <g>
            <line
              x1={x(nowMs)}
              x2={x(nowMs)}
              y1={margin.top}
              y2={plotBottom}
              stroke="var(--ink-2)"
              strokeWidth={1}
            />
            <text
              x={x(nowMs)}
              y={margin.top - 8}
              textAnchor="middle"
              fontSize={11}
              fill="var(--ink-2)"
            >
              now
            </text>
          </g>
        )}
        {deadlineMs !== null && deadlineMs > t0 && deadlineMs < t1 && (
          <text x={x(deadlineMs) + 4} y={margin.top + 12} fontSize={11} fill="var(--muted)">
            deadline
          </text>
        )}

        {series.map((s) => {
          const visible = s.samples.filter((p) => p.t >= t0)
          const p = paths(visible, s.resolutionMs, x, y)
          const color = `var(--series-${s.slot})`
          return (
            <g
              key={s.zone}
              fill="none"
              stroke={color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            >
              <path d={p.measured} />
              <path d={p.forecast} strokeDasharray="5 4" />
            </g>
          )
        })}

        {ends.map(({ s, px, py }) => (
          <g key={s.zone}>
            <circle
              cx={px}
              cy={py}
              r={4}
              fill={`var(--series-${s.slot})`}
              stroke="var(--surface)"
              strokeWidth={2}
            />
            <text x={px + 10} y={py} dy="0.32em" fontSize={12} fill="var(--ink-2)">
              {s.name}
            </text>
          </g>
        ))}

        {hoverT !== null && (
          <g pointerEvents="none">
            <line x1={tipX} x2={tipX} y1={margin.top} y2={plotBottom} stroke="var(--axis)" />
            {hover.map(({ s, at }) =>
              at ? (
                <circle
                  key={s.zone}
                  cx={tipX}
                  cy={y(at.v)}
                  r={4.5}
                  fill={`var(--series-${s.slot})`}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
              ) : null,
            )}
          </g>
        )}
      </svg>

      {hoverT !== null && (
        <div
          role="status"
          className="pointer-events-none absolute z-10 w-[236px] rounded-lg border border-line bg-surface p-3 text-xs shadow-lg"
          style={{ top: 40, left: Math.max(0, tipLeft) }}
        >
          <div className="mb-1.5 font-semibold">
            {formatTime(new Date(hoverT), new Date(nowMs))}
          </div>
          <div className="mb-1 grid grid-cols-[1fr_auto_auto] gap-x-3 text-muted">
            <span />
            <span>at time</span>
            <span>job avg</span>
          </div>
          {hover.map(({ s, at, job }) => (
            <div
              key={s.zone}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-x-3 py-0.5"
            >
              <span className="flex items-center gap-1.5 truncate text-ink-2">
                <span
                  aria-hidden="true"
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: `var(--series-${s.slot})` }}
                />
                {s.name}
              </span>
              <span className="tabular text-right">{at ? formatIntensity(at.v) : '–'}</span>
              <span className="tabular text-right font-semibold">
                {job === undefined ? '–' : formatIntensity(job)}
              </span>
            </div>
          ))}
          <p className="mt-1.5 text-muted">“job avg”: if your job started at this time.</p>
        </div>
      )}

      <label className="mt-2 flex items-center gap-3 text-xs text-muted">
        <span className="shrink-0">Explore a start time</span>
        <input
          type="range"
          min={t0}
          max={t1 - step}
          step={step}
          value={hoverT ?? snap(nowMs)}
          onChange={onScrub}
          onBlur={() => setHoverT(null)}
          aria-valuetext={formatTime(new Date(hoverT ?? snap(nowMs)), new Date(nowMs))}
          className="w-full accent-[var(--accent)]"
        />
      </label>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-accent">Show data table</summary>
        <div className="mt-2 max-h-72 overflow-auto">
          <table className="tabular w-full text-left text-xs">
            <thead className="sticky top-0 bg-surface text-ink-2">
              <tr>
                <th className="py-1 pr-3 font-semibold">Time</th>
                {series.map((s) => (
                  <th key={s.zone} className="py-1 pr-3 text-right font-semibold">
                    {s.name} (g/kWh)
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xTicks.length > 0 &&
                Array.from({ length: Math.ceil((t1 - t0) / 3_600_000) }, (_, i) => {
                  const t = Math.ceil(t0 / 3_600_000) * 3_600_000 + i * 3_600_000
                  return t < t1 ? (
                    <tr key={t} className="border-t border-grid">
                      <td className="py-1 pr-3">{formatTime(new Date(t), new Date(nowMs))}</td>
                      {series.map((s) => {
                        const v = valueAt(s.samples, t, s.resolutionMs)
                        return (
                          <td key={s.zone} className="py-1 pr-3 text-right">
                            {v ? Math.round(v.v) : '–'}
                            {v?.forecast ? '*' : ''}
                          </td>
                        )
                      })}
                    </tr>
                  ) : null
                })}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-muted">* forecast</p>
        </div>
      </details>
    </div>
  )
}
