import { fireEvent, render, screen, within } from '@testing-library/react'
import type { Sample } from '@/lib/series'
import { IntensityChart } from './IntensityChart'
import type { ZoneSeries } from './NowStrip'

const Q = 15 * 60_000
const NOW = Date.UTC(2026, 9, 6, 6, 0)
const mk = (zone: string, name: string, slot: number, values: number[]): ZoneSeries => ({
  zone,
  name,
  slot,
  resolutionMs: Q,
  samples: values.map((v, i): Sample => ({ t: NOW + i * Q, v, forecast: i > 0 })),
})
const series = [
  mk('de', 'Germany', 1, [600, 500, 400, 300]),
  mk('fr', 'France', 2, [60, 50, 40, 30]),
]

describe('IntensityChart', () => {
  it('shows a legend with every country and the forecast style', () => {
    render(
      <IntensityChart series={series} nowMs={NOW} deadlineMs={null} durationMs={Q} best={null} />,
    )
    const legend = screen.getByLabelText('Legend')
    expect(within(legend).getByText('Germany')).toBeInTheDocument()
    expect(within(legend).getByText('France')).toBeInTheDocument()
    expect(within(legend).getByText('forecast')).toBeInTheDocument()
  })

  it('labels the best window with its country', () => {
    render(
      <IntensityChart
        series={series}
        nowMs={NOW}
        deadlineMs={null}
        durationMs={Q}
        best={{ zone: 'fr', startMs: NOW + 3 * Q, endMs: NOW + 4 * Q }}
      />,
    )
    expect(screen.getByText('Best: France')).toBeInTheDocument()
  })

  it('reads values and the job average with the time slider (keyboard access)', () => {
    render(
      <IntensityChart
        series={series}
        nowMs={NOW}
        deadlineMs={null}
        durationMs={2 * Q}
        best={null}
      />,
    )
    fireEvent.change(screen.getByLabelText('Explore a start time'), {
      target: { value: String(NOW + Q) },
    })
    const tip = screen.getByRole('status')
    expect(tip).toHaveTextContent('Germany')
    expect(tip).toHaveTextContent('500 g') // value at that time
    expect(tip).toHaveTextContent('450 g') // a 30-minute job: (500 + 400) / 2
  })

  it('offers the data as a table', () => {
    render(
      <IntensityChart series={series} nowMs={NOW} deadlineMs={null} durationMs={Q} best={null} />,
    )
    expect(screen.getByRole('table')).toBeInTheDocument()
  })
})
