import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ReportSummaryCard } from '../ReportSummaryCard'

const defaultProps = {
  tier: 'Favorable',
  verdict: 'Strong entry quality with technical support.',
  macroAssessment: 'Positive',
  valuationAssessment: 'Fair',
  structureAssessment: 'Uptrend',
  isExpanded: false,
  onExpandToggle: vi.fn(),
}

describe('ReportSummaryCard', () => {
  it('renders TierBadge with given tier', () => {
    render(<ReportSummaryCard {...defaultProps} />)
    expect(screen.getByText('Favorable')).toBeInTheDocument()
  })

  it('renders sub-assessment labels: Macro, Valuation, Structure', () => {
    render(<ReportSummaryCard {...defaultProps} />)
    expect(screen.getByText('Macro')).toBeInTheDocument()
    expect(screen.getByText('Valuation')).toBeInTheDocument()
    expect(screen.getByText('Structure')).toBeInTheDocument()
  })

  it('renders verdict text', () => {
    render(<ReportSummaryCard {...defaultProps} />)
    expect(screen.getByText('Strong entry quality with technical support.')).toBeInTheDocument()
  })

  it('shows "Read full report" when isExpanded=false', () => {
    render(<ReportSummaryCard {...defaultProps} isExpanded={false} />)
    expect(screen.getByText('Read full report')).toBeInTheDocument()
  })

  it('shows "Collapse report" when isExpanded=true', () => {
    render(<ReportSummaryCard {...defaultProps} isExpanded={true} />)
    expect(screen.getByText('Collapse report')).toBeInTheDocument()
  })

  it('calls onExpandToggle when expand button is clicked', () => {
    const onExpandToggle = vi.fn()
    render(<ReportSummaryCard {...defaultProps} onExpandToggle={onExpandToggle} />)
    fireEvent.click(screen.getByRole('button'))
    expect(onExpandToggle).toHaveBeenCalledOnce()
  })
})
