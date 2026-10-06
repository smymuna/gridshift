'use client'

import { useEffect, useMemo, useState } from 'react'
import { usePlanner } from '@/hooks/usePlanner'
import { localTimeZoneName } from '@/lib/format'
import { DeadlinePicker, DurationSlider, PowerPicker, ZonePicker } from './Controls'
import { IntensityChart } from './IntensityChart'
import { NowStrip, type ZoneSeries } from './NowStrip'
import { Recommendation } from './Recommendation'

/** "Now" for drawing, refreshed every minute so the chart's now-line keeps moving. */
function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState<number | null>(null)
  useEffect(() => {
    setNow(Date.now())
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

export function Planner() {
  const { plan, setPlan, slots, zones, intensity, schedule, pending } = usePlanner()
  const nowMs = useNow()
  const names = useMemo(
    () => Object.fromEntries((zones.data ?? []).map((z) => [z.code, z.name])),
    [zones.data],
  )

  const series: ZoneSeries[] = plan.zones.flatMap((zone, i) => {
    const d = intensity[i]?.data
    return d?.samples.length
      ? [
          {
            zone,
            name: names[zone] ?? zone.toUpperCase(),
            slot: slots[zone],
            samples: d.samples,
            resolutionMs: d.resolutionMs,
          },
        ]
      : []
  })
  const loadingSeries = intensity.some((q) => q.isLoading)
  const failed = plan.zones.filter((_, i) => intensity[i]?.isError)

  const best = schedule.data?.recommended
  const deadlineMs = plan.deadlineH && nowMs ? nowMs + plan.deadlineH * 3_600_000 : null

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <aside className="flex flex-col gap-6 rounded-2xl border border-line bg-surface p-5 lg:sticky lg:top-6 lg:self-start">
        {zones.data ? (
          <ZonePicker
            all={zones.data}
            selected={plan.zones}
            slots={slots}
            onChange={(z) => setPlan({ zones: z })}
          />
        ) : (
          <div className="skeleton h-24" />
        )}
        <DurationSlider value={plan.durationMin} onChange={(v) => setPlan({ durationMin: v })} />
        <DeadlinePicker value={plan.deadlineH} onChange={(v) => setPlan({ deadlineH: v })} />
        <PowerPicker value={plan.powerKw} onChange={(v) => setPlan({ powerKw: v })} />
        <p className="text-xs text-muted">
          Settings are saved in the address bar, so you can share this plan as a link.
        </p>
      </aside>

      <div className="flex min-w-0 flex-col gap-6">
        <Recommendation
          data={schedule.data}
          error={schedule.error}
          loading={pending}
          stale={pending && schedule.isPlaceholderData}
          names={names}
        />

        <section className="rounded-2xl border border-line bg-surface p-5">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Grid carbon intensity</h2>
            <p className="text-xs text-muted">g CO₂e per kWh · times in {localTimeZoneName()}</p>
          </div>
          {failed.length > 0 && (
            <p role="alert" className="mb-3 text-sm text-bad">
              No data right now for {failed.map((z) => names[z] ?? z).join(', ')}. The provider may
              be rate limiting; it will retry.
            </p>
          )}
          {series.length && nowMs ? (
            <IntensityChart
              series={series}
              nowMs={nowMs}
              deadlineMs={deadlineMs}
              durationMs={plan.durationMin * 60_000}
              best={
                best
                  ? {
                      zone: best.zone,
                      startMs: Date.parse(best.start),
                      endMs: Date.parse(best.end),
                    }
                  : null
              }
            />
          ) : loadingSeries ? (
            <div className="skeleton h-[340px]" aria-busy="true" />
          ) : (
            <p className="py-12 text-center text-sm text-ink-2">No intensity data to show.</p>
          )}
          <p className="mt-3 text-xs text-muted">
            Forecasts more than a day ahead are less reliable; some countries' day-two forecasts
            look unusually flat. Prefer a deadline within 24 hours for important jobs.
          </p>
        </section>

        {series.length > 0 && nowMs && (
          <section>
            <h2 className="mb-3 text-lg font-semibold">Right now</h2>
            <NowStrip series={series} nowMs={nowMs} />
          </section>
        )}
      </div>
    </div>
  )
}
