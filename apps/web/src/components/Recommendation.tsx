'use client'

import { ApiError, type ScheduleResponse } from '@gridshift/api-client'
import { formatDelay, formatIntensity, formatMass, formatTime } from '@/lib/format'

interface Props {
  data: ScheduleResponse | undefined
  error: unknown
  loading: boolean
  stale: boolean
  names: Record<string, string>
}

function explain(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422 && error.title === 'No feasible window')
      return 'No window fits: the job is longer than the time left before the deadline in the available forecast. Try a shorter job or a later deadline.'
    if (error.status === 503)
      return 'The grid data provider is busy right now. GridShift retries automatically; try again in a minute.'
    if (error.status === 0)
      return 'Could not reach the GridShift API. If you are running it locally, start it with npm run dev.'
    return error.message
  }
  return 'Something went wrong while planning. Please try again.'
}

export function Recommendation({ data, error, loading, stale, names }: Props) {
  if (error && !data) {
    return (
      <div role="alert" className="rounded-2xl border border-line bg-surface p-6">
        <p className="font-semibold">Couldn&apos;t plan this job</p>
        <p className="mt-1 text-sm text-ink-2">{explain(error)}</p>
      </div>
    )
  }
  if (!data) {
    return (
      <div className="skeleton h-[188px]" role="status">
        <span className="sr-only">Finding the best time…</span>
      </div>
    )
  }

  const best = data.recommended
  const now = data.run_now
  const name = (z: string) => names[z] ?? z.toUpperCase()
  const startNow = data.delay_minutes < 1 && (!now || now.zone === best.zone)
  const savings = data.savings_pct ?? 0

  return (
    <section
      aria-live="polite"
      aria-busy={loading}
      className={`rounded-2xl border border-line bg-surface p-6 shadow-sm transition-opacity ${stale ? 'opacity-60' : ''}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Recommendation</p>
      <h2 className="mt-1 text-2xl leading-tight font-semibold sm:text-3xl">
        {startNow ? (
          <>Start now in {name(best.zone)}</>
        ) : (
          <>
            Run in {name(best.zone)} at {formatTime(best.start)}
          </>
        )}
      </h2>
      <p className="mt-1 text-ink-2">
        {startNow
          ? 'Right now is already the cleanest time before your deadline.'
          : `${formatDelay(data.delay_minutes)}, finishing ${formatTime(best.end)}`}
        {best.uses_forecast && ' · based on the forecast'}
      </p>

      <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted">Recommended</dt>
          <dd className="tabular text-lg font-semibold">
            {formatIntensity(best.avg_gco2_per_kwh)}
            <span className="text-sm font-normal text-ink-2"> CO₂/kWh</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Starting now in {now ? name(now.zone) : '–'}</dt>
          <dd className="tabular text-lg font-semibold">
            {now ? formatIntensity(now.avg_gco2_per_kwh) : '–'}
            <span className="text-sm font-normal text-ink-2"> CO₂/kWh</span>
          </dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-xs text-muted">Less CO₂</dt>
          <dd className="tabular text-lg font-semibold text-good">
            {data.savings_pct === null ? '–' : `${savings.toFixed(0)}%`}
            {data.emissions_saved_g !== null && data.emissions_saved_g > 0 && (
              <span className="text-sm font-normal text-ink-2">
                {' '}
                · {formatMass(data.emissions_saved_g)} saved
              </span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  )
}
