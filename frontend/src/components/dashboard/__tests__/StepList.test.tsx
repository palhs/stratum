import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StepList, STEP_ORDER } from '../StepList'
import type { StepStatus } from '@/lib/types'

describe('StepList', () => {
  it('renders all 7 steps with pending status by default', () => {
    const steps = new Map<string, StepStatus>()
    render(<StepList steps={steps} />)

    expect(screen.getByText('Macro Analysis')).toBeInTheDocument()
    expect(screen.getByText('Valuation')).toBeInTheDocument()
    expect(screen.getByText('Price Structure')).toBeInTheDocument()
    expect(screen.getByText('Conflict Check')).toBeInTheDocument()
    expect(screen.getByText('Entry Quality')).toBeInTheDocument()
    expect(screen.getByText('Grounding')).toBeInTheDocument()
    expect(screen.getByText('Compose Report')).toBeInTheDocument()
  })

  it('shows completed icon for completed steps', () => {
    const steps = new Map<string, StepStatus>([['macro_regime', 'completed']])
    render(<StepList steps={steps} />)

    const icon = screen.getByLabelText('Macro Analysis \u2014 completed')
    expect(icon).toBeInTheDocument()
  })

  it('shows spinner for in-progress step', () => {
    const steps = new Map<string, StepStatus>([['valuation', 'in_progress']])
    render(<StepList steps={steps} />)

    const icon = screen.getByLabelText('Valuation \u2014 in progress')
    expect(icon).toBeInTheDocument()
    expect(icon.classList.contains('animate-spin')).toBe(true)
  })

  it('shows error icon for failed step', () => {
    const steps = new Map<string, StepStatus>([['structure', 'failed']])
    render(<StepList steps={steps} />)

    const icon = screen.getByLabelText('Price Structure \u2014 failed')
    expect(icon).toBeInTheDocument()
  })

  it('exports STEP_ORDER with exactly 7 nodes', () => {
    expect(STEP_ORDER).toHaveLength(7)
    expect(STEP_ORDER[0]).toBe('macro_regime')
    expect(STEP_ORDER[6]).toBe('compose_report')
  })
})
