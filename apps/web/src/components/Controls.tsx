'use client'

import type { Zone } from '@gridshift/api-client'
import { formatDuration } from '@/lib/format'
import {
  DEADLINES,
  type DeadlineHours,
  DURATION_MAX,
  DURATION_MIN,
  MAX_ZONES,
  type Plan,
  POWER_PRESETS,
} from '@/lib/planner'

const label = 'text-xs font-semibold uppercase tracking-wide text-muted'

interface ZonePickerProps {
  all: Zone[]
  selected: string[]
  slots: Record<string, number>
  onChange: (zones: string[]) => void
}

export function ZonePicker({ all, selected, slots, onChange }: ZonePickerProps) {
  const names = Object.fromEntries(all.map((z) => [z.code, z.name]))
  const available = all.filter((z) => !selected.includes(z.code))
  const full = selected.length >= MAX_ZONES

  return (
    <fieldset>
      <legend className={label}>Where can the job run?</legend>
      <ul className="mt-2 flex flex-wrap gap-2" aria-label="Selected countries">
        {selected.map((code, i) => (
          <li
            key={code}
            className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-1 pl-3 text-sm"
          >
            <span
              aria-hidden="true"
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: `var(--series-${slots[code]})` }}
            />
            <span className="font-medium">{names[code] ?? code.toUpperCase()}</span>
            {i === 0 ? (
              <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs text-ink-2">
                runs here now
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onChange([code, ...selected.filter((z) => z !== code)])}
                className="rounded-full px-2 py-0.5 text-xs text-muted hover:bg-accent-soft hover:text-ink"
                title={`Make ${names[code] ?? code} the place the job runs by default`}
              >
                set as current
              </button>
            )}
            <button
              type="button"
              onClick={() => onChange(selected.filter((z) => z !== code))}
              disabled={selected.length === 1}
              aria-label={`Remove ${names[code] ?? code}`}
              className="grid h-6 w-6 place-items-center rounded-full text-muted hover:bg-grid hover:text-ink disabled:opacity-30"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <label className="mt-3 flex items-center gap-2 text-sm text-ink-2">
        <span className="sr-only">Add a country</span>
        <select
          value=""
          disabled={full || available.length === 0}
          onChange={(e) => e.target.value && onChange([...selected, e.target.value])}
          className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm disabled:opacity-50 sm:w-64"
        >
          <option value="">{full ? `Up to ${MAX_ZONES} countries` : '+ Add a country'}</option>
          {available.map((z) => (
            <option key={z.code} value={z.code}>
              {z.name}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  )
}

export function DurationSlider({
  value,
  onChange,
}: {
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label htmlFor="duration" className={label}>
          Job length
        </label>
        <output htmlFor="duration" className="tabular text-sm font-semibold">
          {formatDuration(value)}
        </output>
      </div>
      <input
        id="duration"
        type="range"
        min={DURATION_MIN}
        max={DURATION_MAX}
        step={15}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-3 w-full accent-[var(--accent)]"
      />
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>15 min</span>
        <span>12 h</span>
      </div>
    </div>
  )
}

function Segmented<T extends string | number>({
  name,
  options,
  value,
  onChange,
}: {
  name: string
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div
      role="radiogroup"
      aria-label={name}
      className="mt-2 flex flex-wrap gap-1 rounded-lg border border-line bg-page p-1"
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors ${
              active
                ? 'bg-accent font-semibold text-accent-ink shadow-sm'
                : 'text-ink-2 hover:bg-surface'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function DeadlinePicker({
  value,
  onChange,
}: {
  value: DeadlineHours
  onChange: (v: DeadlineHours) => void
}) {
  return (
    <div>
      <span className={label}>Must finish within</span>
      <Segmented
        name="Deadline"
        value={value}
        onChange={onChange}
        options={DEADLINES.map((h) => ({ value: h, label: h === 0 ? 'Any time' : `${h} h` }))}
      />
    </div>
  )
}

export function PowerPicker({
  value,
  onChange,
}: {
  value: Plan['powerKw']
  onChange: (v: Plan['powerKw']) => void
}) {
  const preset = POWER_PRESETS.find((p) => p.kw === value)
  return (
    <div>
      <span className={label}>Power draw (optional)</span>
      <Segmented
        name="Power draw"
        value={value === null ? 'off' : preset ? String(preset.kw) : 'custom'}
        onChange={(v) => onChange(v === 'off' ? null : v === 'custom' ? (value ?? 1) : Number(v))}
        options={[
          ...POWER_PRESETS.map((p) => ({ value: String(p.kw), label: p.label })),
          { value: 'custom', label: 'Custom' },
          { value: 'off', label: 'Off' },
        ]}
      />
      {value !== null && (
        <label className="mt-2 flex items-center gap-2 text-sm text-ink-2">
          <input
            type="number"
            min={0.001}
            step={0.05}
            value={value}
            onChange={(e) => {
              const v = Number(e.target.value)
              if (Number.isFinite(v) && v > 0) onChange(v)
            }}
            className="tabular w-24 rounded-lg border border-line bg-surface px-2 py-1 text-right"
            aria-label="Power draw in kilowatts"
          />
          kW average. Used to show CO₂ in grams.
        </label>
      )}
    </div>
  )
}
