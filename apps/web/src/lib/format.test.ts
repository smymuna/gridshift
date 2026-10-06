import { formatDelay, formatDuration, formatMass } from './format'

describe('format', () => {
  it('formats durations', () => {
    expect(formatDuration(45)).toBe('45 min')
    expect(formatDuration(120)).toBe('2 h')
    expect(formatDuration(150)).toBe('2 h 30 min')
    expect(formatDelay(0)).toBe('now')
    expect(formatDelay(344)).toBe('in 5 h 44 min')
  })

  it('picks a readable mass unit', () => {
    expect(formatMass(37.5)).toBe('38 g')
    expect(formatMass(1520)).toBe('1.5 kg')
    expect(formatMass(3_400_000)).toBe('3.4 t')
  })
})
