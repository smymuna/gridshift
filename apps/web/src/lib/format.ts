const timeFmt = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
const dayTimeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

/** "2 h 30 min", "45 min", "12 h". */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

/** Local clock time; adds the weekday when the time is not today. */
export function formatTime(iso: string | Date, now: Date = new Date()): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return d.toDateString() === now.toDateString() ? timeFmt.format(d) : dayTimeFmt.format(d)
}

/** "in 5 h 44 min", "now". */
export function formatDelay(minutes: number): string {
  return minutes < 1 ? 'now' : `in ${formatDuration(minutes)}`
}

export function formatIntensity(g: number): string {
  return `${Math.round(g).toLocaleString()} g`
}

/** Grams of CO2 with a sensible unit: 37 g, 1.2 kg, 3.4 t. */
export function formatMass(grams: number): string {
  if (Math.abs(grams) >= 1_000_000) return `${(grams / 1_000_000).toFixed(1)} t`
  if (Math.abs(grams) >= 1_000) return `${(grams / 1_000).toFixed(1)} kg`
  return `${Math.round(grams)} g`
}

export function localTimeZoneName(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}
