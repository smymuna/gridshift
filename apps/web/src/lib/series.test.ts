import { type Sample, valueAt, windowAverage } from './series'

const Q = 15 * 60_000
const T0 = Date.UTC(2026, 9, 6, 0, 0)
const samples: Sample[] = [100, 400, 200].map((v, i) => ({ t: T0 + i * Q, v, forecast: i > 0 }))

describe('valueAt', () => {
  it('returns the interval containing the time', () => {
    expect(valueAt(samples, T0 + 5 * 60_000, Q)?.v).toBe(100)
    expect(valueAt(samples, T0 + Q, Q)?.v).toBe(400)
  })

  it('is undefined outside the data', () => {
    expect(valueAt(samples, T0 - 1, Q)).toBeUndefined()
    expect(valueAt(samples, T0 + 3 * Q, Q)).toBeUndefined()
  })
})

describe('windowAverage', () => {
  it('weights partial intervals by time, like the API', () => {
    // start 5 min into the 100 g interval: 10 min at 100, 5 min at 400
    expect(windowAverage(samples, T0 + 5 * 60_000, Q, Q)).toBeCloseTo((100 * 10 + 400 * 5) / 15)
  })

  it('is undefined when the job would run past the data', () => {
    expect(windowAverage(samples, T0 + 2 * Q, Q * 2, Q)).toBeUndefined()
  })
})
