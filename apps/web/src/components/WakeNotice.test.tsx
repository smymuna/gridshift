import { act, render, screen } from '@testing-library/react'
import { WakeNotice } from './WakeNotice'

describe('WakeNotice', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('stays quiet for a normal, fast first load', () => {
    const { rerender } = render(<WakeNotice waiting />)
    act(() => vi.advanceTimersByTime(3000))
    rerender(<WakeNotice waiting={false} />)
    act(() => vi.advanceTimersByTime(5000))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('explains a slow first load, and goes away when the data arrives', () => {
    const { rerender } = render(<WakeNotice waiting />)
    act(() => vi.advanceTimersByTime(4000))
    expect(screen.getByRole('status')).toHaveTextContent(/Waking up the server/)
    rerender(<WakeNotice waiting={false} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
