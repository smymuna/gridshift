import { assignSlots, DEFAULT_PLAN, parsePlan, planToParams } from './planner'

const parse = (q: string, known?: string[]) =>
  parsePlan(new URLSearchParams(q), known ? new Set(known) : undefined)

describe('parsePlan', () => {
  it('uses defaults for an empty URL (missing `by` is not "any time")', () => {
    expect(parse('')).toEqual(DEFAULT_PLAN)
  })

  it('round-trips through the URL', () => {
    const plan = { zones: ['no', 'de'], durationMin: 240, deadlineH: 6 as const, powerKw: 3 }
    expect(parse(planToParams(plan).toString())).toEqual(plan)
  })

  it('keeps an explicit "any time" deadline and power switched off', () => {
    const p = parse('by=0&kw=')
    expect(p.deadlineH).toBe(0)
    expect(p.powerKw).toBeNull()
  })

  it('cleans up hand-edited links', () => {
    const p = parse('zones=DE,de,xx,fr,es,it,nl&duration=50&by=7&kw=-1', [
      'de',
      'fr',
      'es',
      'it',
      'nl',
    ])
    expect(p.zones).toEqual(['de', 'fr', 'es', 'it']) // lower-cased, deduped, unknown dropped, max 4
    expect(p.durationMin).toBe(45) // snapped to 15-minute steps
    expect(p.deadlineH).toBe(DEFAULT_PLAN.deadlineH) // 7 h is not an option
    expect(p.powerKw).toBeNull()
  })

  it('clamps the duration to the slider range', () => {
    expect(parse('duration=5').durationMin).toBe(15)
    expect(parse('duration=10000').durationMin).toBe(720)
  })
})

describe('assignSlots', () => {
  it('keeps colours with their country when another is removed', () => {
    const first = assignSlots(['de', 'fr', 'pl'], {})
    expect(first).toEqual({ de: 1, fr: 2, pl: 3 })
    const after = assignSlots(['de', 'pl'], first)
    expect(after).toEqual({ de: 1, pl: 3 }) // Poland stays slot 3, not repainted to 2
    expect(assignSlots(['de', 'pl', 'no'], after)).toEqual({ de: 1, pl: 3, no: 2 })
  })
})
