'use client'

import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query'
import { useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { assignSlots, DEFAULT_PLAN, type Plan, parsePlan, planToParams } from '@/lib/planner'
import { toSamples } from '@/lib/series'
import { useDebounced } from './useDebounced'

const MINUTE = 60_000

export function usePlanner() {
  const router = useRouter()
  const params = useSearchParams()

  const zonesQuery = useQuery({ queryKey: ['zones'], queryFn: api.zones, staleTime: Infinity })

  // React state is the source of truth; the URL mirrors it. Building each change from
  // the URL instead would lose edits made in quick succession, because router.replace
  // updates the search params asynchronously (found while testing: a slider change
  // followed by a click dropped the slider change).
  const [state, setState] = useState<Plan>(() => parsePlan(new URLSearchParams(params.toString())))
  const setPlan = useCallback((update: Partial<Plan>) => setState((p) => ({ ...p, ...update })), [])

  useEffect(() => {
    const next = planToParams(state).toString()
    if (next !== window.location.search.slice(1)) router.replace(`?${next}`, { scroll: false })
  }, [state, router])

  // Drop codes the API doesn't know (e.g. a typo in a shared link).
  const plan = useMemo(() => {
    if (!zonesQuery.data) return state
    const known = new Set(zonesQuery.data.map((z) => z.code))
    const zones = state.zones.filter((z) => known.has(z))
    return zones.length ? { ...state, zones } : { ...state, zones: DEFAULT_PLAN.zones }
  }, [state, zonesQuery.data])

  // Stable colour per zone while it stays selected.
  const slotsRef = useRef<Record<string, number>>({})
  const slots = useMemo(() => {
    slotsRef.current = assignSlots(plan.zones, slotsRef.current)
    return slotsRef.current
  }, [plan.zones])

  const intensity = useQueries({
    queries: plan.zones.map((zone) => ({
      queryKey: ['intensity', zone],
      queryFn: () => api.intensity(zone),
      staleTime: 5 * MINUTE,
      refetchInterval: 15 * MINUTE, // the data updates every 15 minutes
      select: (r: Awaited<ReturnType<typeof api.intensity>>) => ({
        zone: r.zone,
        resolutionMs: r.resolution_minutes * MINUTE,
        fetchedAt: r.fetched_at,
        samples: toSamples(r.points),
      }),
    })),
  })

  // Dragging the duration slider shouldn't fire a request per pixel.
  const request = useDebounced(plan, 250)
  const schedule = useQuery({
    queryKey: ['schedule', request],
    queryFn: () =>
      api.schedule({
        zones: request.zones,
        duration_minutes: request.durationMin,
        deadline: request.deadlineH
          ? new Date(Date.now() + request.deadlineH * 60 * MINUTE).toISOString()
          : null,
        power_kw: request.powerKw,
      }),
    placeholderData: keepPreviousData, // keep the last answer on screen while recomputing
    staleTime: MINUTE,
    retry: 1,
  })

  return {
    plan,
    setPlan,
    slots,
    zones: zonesQuery,
    intensity,
    schedule,
    pending: schedule.isFetching || request !== plan,
  }
}

export type PlannerState = ReturnType<typeof usePlanner>
