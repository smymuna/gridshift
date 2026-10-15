import { formatDuration, formatTime } from '@/lib/format'

/** Fresh data is at most 15 minutes old (the provider's update interval) plus the cache. */
const STALE_AFTER_MS = 45 * 60_000

interface Props {
  fetchedAt: string[]
  nowMs: number | null
}

/** Says when the chart and recommendation use the API's saved copy because the data
 *  provider is down, so an old forecast is never presented as live. */
export function DataAgeNotice({ fetchedAt, nowMs }: Props) {
  const times = fetchedAt.map((t) => Date.parse(t)).filter(Number.isFinite)
  if (!times.length || !nowMs) return null
  const oldest = Math.min(...times)
  if (nowMs - oldest < STALE_AFTER_MS) return null
  return (
    <p role="status" className="rounded-2xl border border-line bg-surface p-4 text-sm text-ink-2">
      <span className="font-semibold text-ink">
        Using saved grid data from {formatTime(new Date(oldest), new Date(nowMs))} (
        {formatDuration((nowMs - oldest) / 60_000)} ago).
      </span>{' '}
      Energy-Charts isn&apos;t responding, so GridShift is planning with its last saved copy of the
      forecast. It switches back to live data as soon as the provider answers.
    </p>
  )
}
