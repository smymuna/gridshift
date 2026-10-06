import { ApiError, type ScheduleResponse } from '@gridshift/api-client'
import { render, screen } from '@testing-library/react'
import { Recommendation } from './Recommendation'

const names = { de: 'Germany', fr: 'France' }
const runNow: ScheduleResponse['recommended'] = {
  zone: 'de',
  start: '2026-10-06T05:00:00Z',
  end: '2026-10-06T07:00:00Z',
  avg_gco2_per_kwh: 695.7,
  uses_forecast: true,
  emissions_g: 556.5,
}

const base: ScheduleResponse = {
  recommended: {
    zone: 'fr',
    start: '2026-10-06T10:45:00Z',
    end: '2026-10-06T12:45:00Z',
    avg_gco2_per_kwh: 46.9,
    uses_forecast: true,
    emissions_g: 37.5,
  },
  run_now: runNow,
  savings_pct: 93.3,
  emissions_saved_g: 519,
  delay_minutes: 345,
  attribution: 'Energy-Charts',
}

describe('Recommendation', () => {
  it('names the zone, the saving and the grams saved', () => {
    render(<Recommendation data={base} error={null} loading={false} stale={false} names={names} />)
    expect(screen.getByRole('heading')).toHaveTextContent(/Run in France at/)
    expect(screen.getByText('93%')).toBeInTheDocument()
    expect(screen.getByText(/519 g saved/)).toBeInTheDocument()
    expect(screen.getByText(/in 5 h 45 min/)).toBeInTheDocument()
  })

  it('says "start now" when now is already best', () => {
    const now = {
      ...base,
      recommended: runNow,
      delay_minutes: 0,
      savings_pct: 0,
    }
    render(<Recommendation data={now} error={null} loading={false} stale={false} names={names} />)
    expect(screen.getByRole('heading')).toHaveTextContent('Start now in Germany')
  })

  it('explains an infeasible job in plain words', () => {
    const error = new ApiError({ title: 'No feasible window', status: 422, detail: 'x' })
    render(
      <Recommendation data={undefined} error={error} loading={false} stale={false} names={names} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/Try a shorter job or a later deadline/)
  })

  it('explains a provider outage', () => {
    const error = new ApiError({ title: 'Data provider unavailable', status: 503 })
    render(
      <Recommendation data={undefined} error={error} loading={false} stale={false} names={names} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/provider is busy/)
  })
})
