/** Planner settings and their URL encoding (so any plan can be shared as a link). */

export const MAX_ZONES = 4
export const DURATION_MIN = 15
export const DURATION_MAX = 12 * 60
export const DEADLINES = [6, 12, 24, 0] as const // hours from now; 0 = end of forecast
export type DeadlineHours = (typeof DEADLINES)[number]

export interface PowerPreset {
  label: string
  kw: number
}
/** Rough example draws, so savings can be shown in grams. Users can type their own. */
export const POWER_PRESETS: PowerPreset[] = [
  { label: 'Laptop', kw: 0.05 },
  { label: 'Server', kw: 0.5 },
  { label: 'GPU node', kw: 3 },
]

export interface Plan {
  zones: string[] // first = where the job would run by default (the baseline)
  durationMin: number
  deadlineH: DeadlineHours
  powerKw: number | null
}

export const DEFAULT_PLAN: Plan = {
  zones: ['de', 'fr', 'pl'],
  durationMin: 120,
  deadlineH: 24,
  powerKw: 0.5,
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export function parsePlan(params: URLSearchParams, known?: Set<string>): Plan {
  const zones = (params.get('zones') ?? '')
    .split(',')
    .map((z) => z.trim().toLowerCase())
    .filter((z) => /^[a-z]{2}$/.test(z) && (!known || known.has(z)))
  const unique = [...new Set(zones)].slice(0, MAX_ZONES)

  const duration = Number(params.get('duration'))
  // Number(null) is 0, a valid option ("any time"); only read `by` when it is present.
  const deadline = params.has('by') ? Number(params.get('by')) : Number.NaN
  const kwRaw = params.get('kw')
  let powerKw: number | null
  if (kwRaw === null)
    powerKw = DEFAULT_PLAN.powerKw // not in the URL: use the default
  else if (kwRaw === '')
    powerKw = null // explicitly switched off
  else {
    const kw = Number(kwRaw)
    powerKw = Number.isFinite(kw) && kw > 0 ? clamp(kw, 0.001, 100_000) : null
  }

  return {
    zones: unique.length ? unique : DEFAULT_PLAN.zones,
    durationMin:
      Number.isFinite(duration) && duration > 0
        ? clamp(Math.round(duration / 15) * 15, DURATION_MIN, DURATION_MAX)
        : DEFAULT_PLAN.durationMin,
    deadlineH: (DEADLINES as readonly number[]).includes(deadline)
      ? (deadline as DeadlineHours)
      : DEFAULT_PLAN.deadlineH,
    powerKw,
  }
}

export function planToParams(plan: Plan): URLSearchParams {
  const p = new URLSearchParams()
  p.set('zones', plan.zones.join(','))
  p.set('duration', String(plan.durationMin))
  p.set('by', String(plan.deadlineH))
  p.set('kw', plan.powerKw === null ? '' : String(plan.powerKw))
  return p
}

/** Colour slots stay with a zone while it is selected: removing one never repaints the others. */
export function assignSlots(
  zones: string[],
  previous: Record<string, number>,
): Record<string, number> {
  const next: Record<string, number> = {}
  const used = new Set<number>()
  for (const z of zones) {
    const slot = previous[z]
    if (slot && !used.has(slot)) {
      next[z] = slot
      used.add(slot)
    }
  }
  for (const z of zones) {
    if (next[z]) continue
    const free = [1, 2, 3, 4].find((s) => !used.has(s)) ?? 1
    next[z] = free
    used.add(free)
  }
  return next
}
