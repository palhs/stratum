import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TickerCard } from '../TickerCard'
import type { TickerData, StepStatus } from '@/lib/types'

const baseTicker: TickerData = {
  symbol: 'VNM',
  name: 'Vinamilk',
  asset_type: 'equity',
  ohlcv: [{ time: 1000, close: 10 }, { time: 2000, close: 15 }],
  lastReport: { tier: 'Favorable', generated_at: '2026-03-15T10:00:00Z' },
}

describe('TickerCard', () => {
  it('shows Generate Report button when not generating', () => {
    render(
      <TickerCard
        ticker={baseTicker}
        isGenerating={false}
        steps={null}
        onGenerate={() => {}}
      />
    )
    expect(screen.getByRole('button', { name: 'Generate Report' })).toBeInTheDocument()
    expect(screen.getByText('VNM')).toBeInTheDocument()
  })

  it('shows StepList when generating', () => {
    const steps = new Map<string, StepStatus>([
      ['macro_regime', 'completed'],
      ['valuation', 'in_progress'],
    ])
    render(
      <TickerCard
        ticker={baseTicker}
        isGenerating={true}
        steps={steps}
        onGenerate={() => {}}
      />
    )
    // StepList visible
    expect(screen.getByText('Macro Analysis')).toBeInTheDocument()
    expect(screen.getByText('Valuation')).toBeInTheDocument()
    // Generate button NOT visible
    expect(screen.queryByRole('button', { name: 'Generate Report' })).not.toBeInTheDocument()
  })

  it('calls onGenerate with symbol and asset_type when button clicked', () => {
    const onGenerate = vi.fn()
    render(
      <TickerCard
        ticker={baseTicker}
        isGenerating={false}
        steps={null}
        onGenerate={onGenerate}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Generate Report' }))
    expect(onGenerate).toHaveBeenCalledWith('VNM', 'equity')
  })

  it('keeps ticker symbol and tier badge visible during generation', () => {
    const steps = new Map<string, StepStatus>()
    render(
      <TickerCard
        ticker={baseTicker}
        isGenerating={true}
        steps={steps}
        onGenerate={() => {}}
      />
    )
    expect(screen.getByText('VNM')).toBeInTheDocument()
    // TierBadge should still be rendered (Favorable)
    expect(screen.getByText('Favorable')).toBeInTheDocument()
  })
})
