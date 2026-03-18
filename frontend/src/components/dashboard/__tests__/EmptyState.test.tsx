import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { EmptyState } from '../EmptyState'

describe('EmptyState', () => {
  it('renders "Your watchlist is empty" heading', () => {
    render(<EmptyState onAddTicker={vi.fn()} />)
    expect(screen.getByText('Your watchlist is empty')).toBeInTheDocument()
  })

  it('renders 5 quick-add buttons (VNM, FPT, HPG, GLD, MWG)', () => {
    render(<EmptyState onAddTicker={vi.fn()} />)
    const tickers = ['VNM', 'FPT', 'HPG', 'GLD', 'MWG']
    for (const ticker of tickers) {
      expect(screen.getByText(ticker)).toBeInTheDocument()
    }
  })

  it('each button has aria-label "Add {SYMBOL} to watchlist"', () => {
    render(<EmptyState onAddTicker={vi.fn()} />)
    const tickers = ['VNM', 'FPT', 'HPG', 'GLD', 'MWG']
    for (const ticker of tickers) {
      expect(screen.getByRole('button', { name: `Add ${ticker} to watchlist` })).toBeInTheDocument()
    }
  })

  it('calls onAddTicker with correct symbol when quick-add button clicked', async () => {
    const user = userEvent.setup()
    const mockOnAddTicker = vi.fn()
    render(<EmptyState onAddTicker={mockOnAddTicker} />)

    await user.click(screen.getByRole('button', { name: 'Add VNM to watchlist' }))
    expect(mockOnAddTicker).toHaveBeenCalledWith('VNM')

    await user.click(screen.getByRole('button', { name: 'Add FPT to watchlist' }))
    expect(mockOnAddTicker).toHaveBeenCalledWith('FPT')
  })
})
