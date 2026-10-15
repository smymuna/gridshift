import { render, screen } from '@testing-library/react'
import { DataAgeNotice } from './DataAgeNotice'

const NOW = Date.parse('2026-10-15T12:00:00Z')
const ago = (min: number) => new Date(NOW - min * 60_000).toISOString()

describe('DataAgeNotice', () => {
  it('is silent while the data is live', () => {
    render(<DataAgeNotice fetchedAt={[ago(5), ago(20)]} nowMs={NOW} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('names the age of the oldest saved copy', () => {
    render(<DataAgeNotice fetchedAt={[ago(5), ago(150)]} nowMs={NOW} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      /Using saved grid data from .*2 h 30 min ago/,
    )
  })
})
